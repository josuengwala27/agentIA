SELECT id FROM chunks WHERE organization_id = 'eebbf935-c7c5-4b5a-8680-0c0ea12eb075' LIMIT 3;
SELECT id, embedding <=> (SELECT embedding FROM chunks WHERE embedding IS NOT NULL LIMIT 1) AS distance
FROM chunks
WHERE organization_id = 'eebbf935-c7c5-4b5a-8680-0c0ea12eb075' AND embedding IS NOT NULL
ORDER BY distance
LIMIT 3;
