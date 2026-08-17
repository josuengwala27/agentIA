from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.services.ollama import chat_completion, embed_texts
from app.services.conversation_memory import build_tutor_messages, retrieval_query
from app.services.question_language import (
    detect_thread_language,
    fallback_message,
    language_display_name,
)


async def retrieve_chunks(
    db: Session,
    organization_id: str,
    query: str,
    document_id: str | None = None,
    top_k: int = 5,
) -> list[Chunk]:
    vectors = await embed_texts([query])
    embedding = vectors[0]
    # pgvector literal: [0.1,0.2,...]
    embedding_literal = "[" + ",".join(f"{float(x):.8f}" for x in embedding) + "]"
    limit = max(1, min(int(top_k), 20))

    # Bind limit as literal (safe int) — some drivers mishandle LIMIT params.
    # Cast embedding via explicit vector typmod-free cast.
    sql = f"""
        SELECT id
        FROM chunks
        WHERE organization_id = :org_id
          AND embedding IS NOT NULL
    """
    params: dict = {"org_id": str(organization_id), "embedding": embedding_literal}
    if document_id:
        sql += " AND document_id = :document_id"
        params["document_id"] = str(document_id)
    sql += f" ORDER BY embedding <=> CAST(:embedding AS vector) ASC LIMIT {limit}"

    rows = db.execute(text(sql), params).fetchall()
    chunk_ids = [str(row[0]) for row in rows]

    # Fallback: if vector search returns nothing but chunks exist for the org,
    # return the first chunks (avoids false "no content" on driver/cast quirks).
    if not chunk_ids:
        q = db.query(Chunk.id).filter(
            Chunk.organization_id == str(organization_id),
            Chunk.embedding.isnot(None),
        )
        if document_id:
            q = q.filter(Chunk.document_id == str(document_id))
        chunk_ids = [str(r[0]) for r in q.limit(limit).all()]

    if not chunk_ids:
        return []

    chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    by_id = {str(c.id): c for c in chunks}
    return [by_id[cid] for cid in chunk_ids if cid in by_id]


@dataclass
class RagPlan:
    citations: list[dict] = field(default_factory=list)
    answer: str | None = None
    messages: list[dict[str, str]] | None = None


async def plan_rag_answer(
    db: Session,
    organization_id: str,
    question: str,
    document_id: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> RagPlan:
    indexed_count = (
        db.query(Document)
        .filter(
            Document.organization_id == str(organization_id),
            Document.status == "indexed",
        )
        .count()
    )
    if indexed_count == 0:
        return RagPlan(answer=fallback_message("no_indexed", question, history))

    query = retrieval_query(question, history)
    chunks = await retrieve_chunks(db, organization_id, query, document_id=document_id)
    if not chunks:
        return RagPlan(answer=fallback_message("no_chunks", question, history))

    context_parts = []
    citations: list[dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        doc = db.get(Document, chunk.document_id)
        title = doc.title if doc else "Document"
        context_parts.append(f"[{idx}] ({title}) {chunk.content}")
        citations.append(
            {
                "document_id": chunk.document_id,
                "document_title": title,
                "chunk_index": chunk.chunk_index,
                "excerpt": chunk.content[:220] + ("…" if len(chunk.content) > 220 else ""),
            }
        )

    reply_lang = language_display_name(detect_thread_language(question, history))
    system = (
        "You are a pedagogical tutor. Answer ONLY from the provided context. "
        "Use the conversation history to resolve follow-ups (examples, pronouns, "
        "'explain more') without inventing facts outside the excerpts. "
        "Always reply in the SAME language as the learner's question, "
        "even if the source excerpts or this instruction are in another language. "
        "If information is missing, say so clearly in that same language. "
        "Cite sources with [n]."
    )
    messages = build_tutor_messages(
        system=system,
        context=chr(10).join(context_parts),
        question=question,
        history=history,
        reply_lang=reply_lang,
    )
    return RagPlan(citations=citations, messages=messages)


async def answer_with_rag(
    db: Session,
    organization_id: str,
    question: str,
    document_id: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, list[dict]]:
    plan = await plan_rag_answer(db, organization_id, question, document_id, history)
    if plan.answer is not None:
        return plan.answer, plan.citations
    assert plan.messages is not None
    answer = await chat_completion(plan.messages, temperature=0.2)
    return answer, plan.citations
