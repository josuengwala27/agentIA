SELECT COUNT(*) AS document_count FROM documents;
SELECT id, title, status, organization_id FROM documents;
SELECT COUNT(*) AS total, COUNT(embedding) AS with_emb, COUNT(*) - COUNT(embedding) AS emb_null FROM chunks;
SELECT id, document_id, organization_id, length(content) AS len, (embedding IS NULL) AS emb_null FROM chunks LIMIT 5;
SELECT extname FROM pg_extension WHERE extname='vector';
