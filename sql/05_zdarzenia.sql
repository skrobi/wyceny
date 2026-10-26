-- Opublikowane decyzje użytkowników – EventTime to moment kliknięcia decyzji.
SELECT
    ev.EventKey,
    ev.EventTime,
    ev.IsProcessed
FROM wfc.Event ev
WHERE ev.EventName = 'UserAction'
  AND ev.EventTime >= ?;
