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


async def answer_with_rag(
    db: Session,
    organization_id: str,
    question: str,
    document_id: str | None = None,
) -> tuple[str, list[dict]]:
    # Fast path: no indexed docs at all
    indexed_count = (
        db.query(Document)
        .filter(
            Document.organization_id == str(organization_id),
            Document.status == "indexed",
        )
        .count()
    )
    if indexed_count == 0:
        return (
            "Je n'ai trouvé aucun contenu indexé pour répondre. "
            "Demandez à un formateur d'importer des supports pédagogiques.",
            [],
        )

    chunks = await retrieve_chunks(db, organization_id, question, document_id=document_id)
    if not chunks:
        return (
            "Le document est indexé mais aucun passage pertinent n'a pu être récupéré. "
            "Réessayez, ou ré-importez le support.",
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
