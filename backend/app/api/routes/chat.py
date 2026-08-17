import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ChatResponse, ConversationOut, MessageOut
from app.services.conversation_memory import HISTORY_LIMIT
from app.services.ollama import OllamaError, chat_completion_stream
from app.services.rag import answer_with_rag, plan_rag_answer

router = APIRouter(prefix="/chat", tags=["chat"])


def sse_pack(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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


def _open_conversation(db: Session, user: User, payload: ChatRequest) -> tuple[Conversation, list[dict[str, str]]]:
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

    db.add(Message(conversation_id=conv.id, role="user", content=payload.message))
    db.commit()
    db.refresh(conv)

    prior_rows = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .offset(1)
        .limit(HISTORY_LIMIT)
        .all()
    )
    history = [{"role": row.role, "content": row.content} for row in reversed(prior_rows)]
    return conv, history


def _save_assistant(db: Session, conversation_id: str, content: str, citations: list) -> None:
    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            citations=citations,
        )
    )
    db.commit()


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv, history = _open_conversation(db, user, payload)

    try:
        answer, citations = await answer_with_rag(
            db,
            user.organization_id,
            payload.message,
            document_id=payload.document_id,
            history=history,
        )
    except OllamaError as exc:
        _save_assistant(
            db,
            conv.id,
            f"Erreur IA : {exc}. Vérifiez qu'Ollama tourne avec llama3.2.",
            [],
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        _save_assistant(
            db,
            conv.id,
            f"Erreur technique pendant la génération : {exc}",
            [],
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _save_assistant(db, conv.id, answer, citations)
    return ChatResponse(conversation_id=conv.id, answer=answer, citations=citations)


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv, history = _open_conversation(db, user, payload)

    async def events() -> AsyncIterator[str]:
        yield sse_pack({"type": "meta", "conversation_id": conv.id})
        yield sse_pack({"type": "status", "message": "Recherche dans les supports…"})
        try:
            plan = await plan_rag_answer(
                db,
                user.organization_id,
                payload.message,
                document_id=payload.document_id,
                history=history,
            )
            yield sse_pack(
                {
                    "type": "meta",
                    "conversation_id": conv.id,
                    "citations": plan.citations,
                }
            )
            if plan.answer is not None:
                yield sse_pack({"type": "token", "text": plan.answer})
                _save_assistant(db, conv.id, plan.answer, plan.citations)
                yield sse_pack(
                    {
                        "type": "done",
                        "conversation_id": conv.id,
                        "answer": plan.answer,
                        "citations": plan.citations,
                    }
                )
                return

            yield sse_pack({"type": "status", "message": "Rédaction…"})
            parts: list[str] = []
            async for token in chat_completion_stream(plan.messages or [], temperature=0.2):
                parts.append(token)
                yield sse_pack({"type": "token", "text": token})
            answer = "".join(parts)
            _save_assistant(db, conv.id, answer, plan.citations)
            yield sse_pack(
                {
                    "type": "done",
                    "conversation_id": conv.id,
                    "answer": answer,
                    "citations": plan.citations,
                }
            )
        except OllamaError as exc:
            message = f"Erreur IA : {exc}. Vérifiez qu'Ollama tourne avec llama3.2."
            _save_assistant(db, conv.id, message, [])
            yield sse_pack({"type": "error", "message": str(exc)})
        except Exception as exc:
            message = f"Erreur technique pendant la génération : {exc}"
            _save_assistant(db, conv.id, message, [])
            yield sse_pack({"type": "error", "message": str(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
