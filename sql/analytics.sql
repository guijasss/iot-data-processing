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

-- simulação contínua de alertas
with base_alerts as (
	select
		event_id,
		timestamp,
		CONCAT(EXTRACT(HOUR FROM "timestamp"), EXTRACT(MINUTE FROM "timestamp")) as simulation_id
	from alerts
	where type = 'overheating'
),

ranked_alerts as (
	select
		*,
		rank() over (partition by simulation_id order by timestamp asc) as rank
	from base_alerts
)

select
	ra.event_id,
	ra."timestamp" as alert_timestamp,
	a."timestamp" as event_timestamp,
	ra."timestamp" - a."timestamp" as difference
from ranked_alerts ra
inner join events a
on ra.event_id = a.event_id
where rank = 1