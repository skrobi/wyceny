-- Zapytania ofertowe od pierwszego analizowanego zapytania: TenderEnquiryId >= ? (wcześniejsze to głównie testy).
-- Daty sprzed 1900 (np. 0001-01-01 zapisywane przez .NET jako „brak”) zwracane jako NULL.
SELECT
    te.TenderEnquiryId,
    te.TenderEnquiryNumber,
    te.EnquiryRevision,
    te.Client,
    te.Synonym,
    c.Name                  AS Country,
    toe.Description         AS TypeOfEnquiry,
    prod.Name               AS Product,
    coe.Name                AS Classification,
    te.Status               AS StatusCode,
    rp.FullName             AS OwnerName,
    rp.LMId                 AS OwnerLMId,
    rp.OrganisationalUnit   AS OwnerUnit,
    LOWER(te.WorkflowId)    AS WorkflowId,
    CASE WHEN te.DateRequestReceived       >= '19000101' THEN te.DateRequestReceived END       AS DateRequestReceived,
    CASE WHEN te.StartDateOfDataCollection >= '19000101' THEN te.StartDateOfDataCollection END AS StartDateOfDataCollection,
    CASE WHEN te.DataCompletionDeadline    >= '19000101' THEN te.DataCompletionDeadline END    AS DataCompletionDeadline,
    CASE WHEN te.StartDateOfValuation      >= '19000101' THEN te.StartDateOfValuation END      AS StartDateOfValuation,
    CASE WHEN te.ValuationCompletionDate   >= '19000101' THEN te.ValuationCompletionDate END   AS ValuationCompletionDate,
    CASE WHEN te.SubmissionDateRequired    >= '19000101' THEN te.SubmissionDateRequired END    AS SubmissionDateRequired,
    CASE WHEN te.TransferToCustomerDate    >= '19000101' THEN te.TransferToCustomerDate END    AS TransferToCustomerDate,
    CASE WHEN te.DateCompleted             >= '19000101' THEN te.DateCompleted END             AS DateCompleted,
    te.CancelReason
FROM dbo.TenderEnquiry te
LEFT JOIN dbo.Country c                   ON c.Id = te.CountryId
LEFT JOIN dbo.TypeOfEnquiry toe           ON toe.Id = te.TypeOfEnquiryId
LEFT JOIN dbo.Product prod                ON prod.Id = te.ProductId
LEFT JOIN dbo.ClassificationOfEnquiry coe ON coe.Id = te.ClassificationId
LEFT JOIN dbo.ResponsiblePerson rp        ON rp.Id = te.ResponsiblePersonId
WHERE te.TenderEnquiryId >= ?;
