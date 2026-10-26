-- Atrybuty zadań użytkowników: komu przypisano, opis zadania, kto wykonał.
-- Wartości są zapisane jako JSON (np. "RMS.APP_WYCENY_DS" w cudzysłowach) – rozpakowuje je Python.
SELECT
    a.ExecutionPointerId,
    a.AttributeKey,
    a.AttributeValue
FROM wfc.ExtensionAttribute a
JOIN wfc.ExecutionPointer e ON e.PersistenceId = a.ExecutionPointerId
JOIN wfc.Workflow w         ON w.PersistenceId = e.WorkflowId
WHERE w.CreateTime >= ?
  AND a.AttributeKey IN ('AssignedPrincipal', 'Prompt', 'ActionUser');
