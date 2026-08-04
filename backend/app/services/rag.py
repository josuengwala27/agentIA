from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.services.ollama import chat_completion, embed_texts


async def retrieve_chunks(
    db: Session,
    organization_id: str,
    query: str,
    document_id: str | None = None,
    top_k: int = 5,
) -> list[Chunk]:
    vectors = await embed_texts([query])
    embedding = vectors[0]
    embedding_literal = "[" + ",".join(str(float(x)) for x in embedding) + "]"

    sql = """
        SELECT id
        FROM chunks
        WHERE organization_id = :org_id
          AND embedding IS NOT NULL
    """
    params: dict = {"org_id": organization_id, "embedding": embedding_literal, "top_k": top_k}
    if document_id:
        sql += " AND document_id = :document_id"
        params["document_id"] = document_id
    sql += " ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :top_k"

    rows = db.execute(text(sql), params).fetchall()
    chunk_ids = [row[0] for row in rows]
    if not chunk_ids:
        return []
    chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    by_id = {c.id: c for c in chunks}
    return [by_id[cid] for cid in chunk_ids if cid in by_id]


async def answer_with_rag(
    db: Session,
    organization_id: str,
    question: str,
    document_id: str | None = None,
) -> tuple[str, list[dict]]:
    chunks = await retrieve_chunks(db, organization_id, question, document_id=document_id)
    if not chunks:
        return (
            "Je n'ai trouvé aucun contenu indexé pour répondre. "
            "Demandez à un formateur d'importer des supports pédagogiques.",
            [],
        )

    context_parts = []
    citations = []
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

    system = (
        "Tu es un tuteur pédagogique. Réponds UNIQUEMENT à partir du contexte fourni. "
        "Si l'information manque, dis-le clairement. Cite les sources avec [n]."
    )
    user = f"Contexte:\n{chr(10).join(context_parts)}\n\nQuestion: {question}"
    answer = await chat_completion(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )
    return answer, citations
