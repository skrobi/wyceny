-- Wszystkie kroki (ExecutionPointer) workflow utworzonych od daty startu (parametr ?),
-- także automatyczne – potrzebne do osi czasu i ustalania końca zadań.
SELECT
    e.PersistenceId,
    e.WorkflowId,
    LOWER(e.Id)            AS Id,
    e.StepId,
    e.StepName,
    e.Status,
    e.Active,
    e.StartTime,
    e.EndTime,
    e.EventName,
    e.EventKey,
    e.EventPublished,
    CASE WHEN ISJSON(e.EventData) = 1 THEN JSON_VALUE(e.EventData, '$.User') END         AS EventUser,
    CASE WHEN ISJSON(e.EventData) = 1 THEN JSON_VALUE(e.EventData, '$.OutcomeValue') END AS EventOutcome,
    LOWER(e.PredecessorId) AS PredecessorId
FROM wfc.ExecutionPointer e
JOIN wfc.Workflow w ON w.PersistenceId = e.WorkflowId
WHERE w.CreateTime >= ?;
