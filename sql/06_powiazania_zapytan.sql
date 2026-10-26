-- Powiązanie WSZYSTKICH zapytań z ich workflow (bez filtra daty, tylko identyfikatory).
-- Pozwala odróżnić workflow zapytań spoza zakresu (Id < pierwszego analizowanego, np. testy) od workflow bez zapytania.
-- Parametr ? jest wymagany przez program, ale tu nieużywany.
SELECT
    te.TenderEnquiryId,
    te.TenderEnquiryNumber,
    LOWER(te.WorkflowId) AS WorkflowId,
    CASE WHEN te.DateRequestReceived >= '19000101' THEN te.DateRequestReceived END AS DateRequestReceived
FROM dbo.TenderEnquiry te
WHERE ? IS NOT NULL;
