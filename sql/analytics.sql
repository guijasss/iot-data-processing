-- seleciona o evento que disparou o alerta de overheating
SELECT *
FROM (
	SELECT *, RANK() OVER (ORDER BY TIMESTAMP) AS rank
	FROM events
	WHERE (payload->>'temperature')::numeric > 45
)
WHERE rank = 1

-- seleciona o primeiro alerta de overheating
SELECT *
FROM (
	SELECT *, RANK() over (ORDER BY TIMESTAMP) as rank
	FROM alerts
	WHERE type = 'overheating'
)
WHERE rank = 1

-- análise de eventos e alertas
SELECT a."timestamp" - e."timestamp"
FROM events e
INNER JOIN alerts a
ON e.event_id = a.event_id
WHERE 1=1
AND e.event_id = 'f1acddd4-e9b7-452d-8446-66571a6bfb17'
AND a."type" = 'overheating'
