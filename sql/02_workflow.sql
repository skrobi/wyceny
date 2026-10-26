-- Instancje workflow (główne, ForwardWorkflow i inne) utworzone od daty startu (parametr ?).
-- Reference podworkflow ma postać <InstanceId rodzica>.<Id kroku rodzica>.
SELECT
    w.PersistenceId,
    LOWER(CAST(w.InstanceId AS nvarchar(36))) AS InstanceId,
    w.WorkflowDefinitionId,
    w.Version,
    LOWER(w.Reference)                        AS Reference,
    w.CreateTime,
    w.CompleteTime,
    w.Status,
    CASE WHEN ISJSON(w.Data) = 1 THEN JSON_VALUE(w.Data, '$.UserNameFrom') END AS UserNameFrom,
    CASE WHEN ISJSON(w.Data) = 1 THEN JSON_VALUE(w.Data, '$.Comment') END      AS Comment
FROM wfc.Workflow w
WHERE w.CreateTime >= ?;
