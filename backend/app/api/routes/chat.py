from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ChatResponse, ConversationOut, MessageOut
from app.services.ollama import OllamaError
from app.services.rag import answer_with_rag

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Conversation)
        .filter(
            Conversation.organization_id == user.organization_id,
            Conversation.user_id == user.id,
        )
        .order_by(Conversation.created_at.desc())
        .all()
    )


@router.delete("/conversations", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convs = (
        db.query(Conversation)
        .filter(
            Conversation.organization_id == user.organization_id,
            Conversation.user_id == user.id,
        )
        .all()
    )
    for conv in convs:
        db.delete(conv)
    db.commit()


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
            Conversation.organization_id == user.organization_id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    db.delete(conv)
    db.commit()


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
            Conversation.organization_id == user.organization_id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.conversation_id:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == user.id,
                Conversation.organization_id == user.organization_id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
    else:
        title = payload.message[:60] + ("…" if len(payload.message) > 60 else "")
        conv = Conversation(
            organization_id=user.organization_id,
            user_id=user.id,
            title=title,
        )
        db.add(conv)
        db.flush()

    # Commit the user turn early so a long Ollama call / reload doesn't lose it.
    db.add(Message(conversation_id=conv.id, role="user", content=payload.message))
    db.commit()
    db.refresh(conv)

    try:
        answer, citations = await answer_with_rag(
            db,
            user.organization_id,
            payload.message,
            document_id=payload.document_id,
        )
    except OllamaError as exc:
        db.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=f"Erreur IA : {exc}. Vérifiez qu'Ollama tourne avec llama3.2.",
                citations=[],
            )
        )
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        db.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=f"Erreur technique pendant la génération : {exc}",
                citations=[],
            )
        )
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            content=answer,
            citations=citations,
        )
    )
    db.commit()
    return ChatResponse(conversation_id=conv.id, answer=answer, citations=citations)
