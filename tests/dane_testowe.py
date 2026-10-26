"""Mała, fikcyjna migawka odwzorowująca strukturę prawdziwych danych (zapytanie z konsultacjami DTTW)."""
from datetime import date

import pandas as pd

from wyceny.migawka import Migawka

M = "aaaaaaaa-0000-0000-0000-000000000001"   # główny workflow zapytania
F1 = "bbbbbbbb-0000-0000-0000-000000000001"  # konsultacja do zadania DTK (nigdy niezamknięta)
F2 = "bbbbbbbb-0000-0000-0000-000000000002"  # konsultacja do zadania DTTW (poziom 1)
F3 = "bbbbbbbb-0000-0000-0000-000000000003"  # konsultacja z konsultacji (poziom 2, dwie rundy)
G = "cccccccc-0000-0000-0000-000000000001"   # workflow bez zapytania

T = pd.Timestamp
INSTANCJA = {1: M, 2: F1, 3: F2, 4: F3, 5: G}


def migawka() -> Migawka:
    zapytania = pd.DataFrame([{
        "TenderEnquiryId": 410, "TenderEnquiryNumber": 2178, "EnquiryRevision": 0, "Client": "Klient A",
        "Synonym": "S", "Country": "USA", "TypeOfEnquiry": "RFQ", "Product": "P", "Classification": "Części",
        "StatusCode": 6, "OwnerName": "Właściciel Jan", "OwnerLMId": "e1", "OwnerUnit": "DSP",
        "WorkflowId": M.upper(), "DateRequestReceived": T("2026-08-13"), "StartDateOfDataCollection": pd.NaT,
        "DataCompletionDeadline": T("2026-10-22"), "StartDateOfValuation": pd.NaT,
        "ValuationCompletionDate": pd.NaT, "SubmissionDateRequired": T("2026-10-26"),
        "TransferToCustomerDate": pd.NaT, "DateCompleted": pd.NaT, "CancelReason": None,
    }])
    workflow = pd.DataFrame([
        {"PersistenceId": 1, "InstanceId": M, "WorkflowDefinitionId": "TenderEnquiryWorkflow", "Version": 1,
         "Reference": None, "CreateTime": T("2026-08-13 06:46"), "CompleteTime": pd.NaT, "Status": 0,
         "UserNameFrom": None, "Comment": None},
        {"PersistenceId": 2, "InstanceId": F1, "WorkflowDefinitionId": "ForwardWorkflow", "Version": 1,
         "Reference": f"{M}.p-dtk", "CreateTime": T("2026-08-17 12:37"), "CompleteTime": pd.NaT, "Status": 0,
         "UserNameFrom": None, "Comment": None},
        {"PersistenceId": 3, "InstanceId": F2, "WorkflowDefinitionId": "ForwardWorkflow", "Version": 1,
         "Reference": f"{M}.p-dttw", "CreateTime": T("2026-09-24 09:54"), "CompleteTime": pd.NaT, "Status": 0,
         "UserNameFrom": None, "Comment": None},
        {"PersistenceId": 4, "InstanceId": F3, "WorkflowDefinitionId": "ForwardWorkflow", "Version": 1,
         "Reference": f"{F2}.f2", "CreateTime": T("2026-09-24 10:13"), "CompleteTime": pd.NaT, "Status": 0,
         "UserNameFrom": None, "Comment": None},
        {"PersistenceId": 5, "InstanceId": G, "WorkflowDefinitionId": "TenderEnquiryWorkflow", "Version": 1,
         "Reference": None, "CreateTime": T("2026-09-01"), "CompleteTime": pd.NaT, "Status": 0,
         "UserNameFrom": None, "Comment": None},
    ])

    def krok(pid, wf, id_, step, nazwa, status, start, end=pd.NaT, event=None, pub=0, user=None, outcome=None,
             pred=None):
        return {"PersistenceId": pid, "WorkflowId": wf, "Id": id_, "StepId": step, "StepName": nazwa,
                "Status": status, "Active": 0, "StartTime": T(start), "EndTime": T(end) if end is not pd.NaT else end,
                "EventName": event, "EventKey": None if event is None else f"{INSTANCJA[wf]}.{id_}",
                "EventPublished": pub, "EventUser": user, "EventOutcome": outcome, "PredecessorId": pred}

    kroki = pd.DataFrame([
        # DS: kontener (status 2, bez EndTime, bez zdarzenia) – koniec = start kroku następnego
        krok(101, 1, "p-ds", 4, "UserTask", 2, "2026-08-13 06:46", event="UserAction", pub=1,
             user="Osoba DS | e2", outcome="Zatwierdzono"),
        krok(102, 1, "p-ds-next", 5, None, 2, "2026-08-13 10:54", pred="p-ds"),
        # DTK: koniec ze zdarzenia
        krok(103, 1, "p-dtk", 18, "UserTask", 2, "2026-08-13 11:05", event="UserAction", pub=1,
             user="Osoba DTK | e3", outcome="Zatwierdzono"),
        # DTTW: otwarte
        krok(104, 1, "p-dttw", 113, "UserTask", 5, "2026-09-10 12:21", event="UserAction"),
        # DJ: zakończone, koniec z EndTime
        krok(105, 1, "p-dj", 135, "UserTask", 3, "2026-09-10 12:21", "2026-09-10 14:25", event="UserAction",
             pub=1, user="Osoba DJ | e4", outcome="Zwrócono do poprawy"),
        # zadanie wyjścia z obiegu – pomijane
        krok(106, 1, "p-rfq", 47, "UserTask", 5, "2026-09-10 12:21", event="UserAction"),
        # konsultacja DTK – otwarta, choć zadanie DTK dawno zakończone
        krok(201, 2, "f1", 1, "UserTask", 5, "2026-08-17 12:37", event="UserAction"),
        # konsultacja DTTW poziom 1
        krok(301, 3, "f2", 1, "UserTask", 3, "2026-09-24 09:54", "2026-10-19 08:25", event="UserAction", pub=1,
             user="Konsultant B | e6", outcome="Zatwierdzono"),
        # konsultacja DTTW poziom 2 – dwie rundy w tym samym obiegu
        krok(401, 4, "f3a", 1, "UserTask", 3, "2026-09-24 10:13", "2026-09-29 07:00", event="UserAction", pub=1,
             user="Konsultant C | e7", outcome="Zatwierdzono"),
        krok(402, 4, "f3b", 1, "UserTask", 3, "2026-09-29 08:26", "2026-10-19 08:14", event="UserAction", pub=1,
             user="Konsultant C | e7", outcome="Zatwierdzono"),
        # workflow bez zapytania
        krok(501, 5, "g1", 4, "UserTask", 5, "2026-09-01", event="UserAction"),
    ])

    atr = []
    for pid, grupa, opis, wykonal in [
        (101, '"RMS.APP_WYCENY_DS"', '"Utworzenie RFQ"', '"Osoba DS | e2"'),
        (103, '"RMS.APP_WYCENY_DTK"', '"Weryfikacja dokumentacji technicznej"', '"Osoba DTK | e3"'),
        (104, '"RMS.APP_WYCENY_DTTW"', '"Uzupełnienie technologii (DTT/W)"', None),
        (105, '"RMS.APP_WYCENY_DJ"', '"Uzupełnienie kosztów (DJ)"', '"Osoba DJ | e4"'),
        (106, '"RMS.APP_WYCENY_DS"', '"Ewentualne zmiany w RFQ (DS)"', None),
        (201, '"Konsultant A | e5"', '"Konsultacja"', None),
        (301, '"Konsultant B | e6"', '"Konsultacja"', '"Konsultant B | e6"'),
        (401, '"Konsultant C | e7"', '"Konsultacja"', '"Konsultant C | e7"'),
        (402, '"Konsultant C | e7"', '"Konsultacja"', '"Konsultant C | e7"'),
        (501, '"RMS.APP_WYCENY_DS"', '"Utworzenie RFQ"', None),
    ]:
        atr.append({"ExecutionPointerId": pid, "AttributeKey": "AssignedPrincipal", "AttributeValue": grupa})
        atr.append({"ExecutionPointerId": pid, "AttributeKey": "Prompt", "AttributeValue": opis})
        if wykonal:
            atr.append({"ExecutionPointerId": pid, "AttributeKey": "ActionUser", "AttributeValue": wykonal})

    zdarzenia = pd.DataFrame([
        {"EventKey": f"{M}.p-dtk", "EventTime": T("2026-08-20 08:57"), "IsProcessed": 1},
    ])
    return Migawka(data=date(2026, 10, 26), pobrano_utc=T("2026-10-26 08:00"), zapytania=zapytania,
                   workflow=workflow, kroki=kroki, atrybuty=pd.DataFrame(atr), zdarzenia=zdarzenia)
