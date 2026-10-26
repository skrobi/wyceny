"""Mała, fikcyjna migawka odwzorowująca strukturę prawdziwych danych (zapytanie z konsultacjami DTTW)."""
from datetime import date

import pandas as pd

from wyceny.migawka import Migawka

M = "aaaaaaaa-0000-0000-0000-000000000001"   # główny workflow zapytania
F1 = "bbbbbbbb-0000-0000-0000-000000000001"  # konsultacja do zadania DTK (nigdy niezamknięta)
F2 = "bbbbbbbb-0000-0000-0000-000000000002"  # konsultacja do zadania DTTW (poziom 1)
F3 = "bbbbbbbb-0000-0000-0000-000000000003"  # konsultacja z konsultacji (poziom 2, dwie rundy)
G = "cccccccc-0000-0000-0000-000000000001"   # workflow zapytania spoza zakresu (Id < 758)
N = "aaaaaaaa-0000-0000-0000-000000000002"   # drugie zapytanie – zamknięte, z rundą zbierania danych
H = "cccccccc-0000-0000-0000-000000000002"   # workflow bez żadnego zapytania
N2 = "aaaaaaaa-0000-0000-0000-000000000003"  # trzecie zapytanie – DJ czeka na DTTW, brak daty przekazania
K = "bbbbbbbb-0000-0000-0000-000000000009"   # konsultacja z obiegu sprzed daty granicznej
STARY = "eeeeeeee-0000-0000-0000-000000000001"

T = pd.Timestamp
INSTANCJA = {1: M, 2: F1, 3: F2, 4: F3, 5: G, 6: N, 7: H, 8: K, 9: N2}


def migawka() -> Migawka:
    zapytania = pd.DataFrame([{
        "TenderEnquiryId": 410, "TenderEnquiryNumber": 2178, "EnquiryRevision": 0, "Client": "Klient A",
        "Synonym": "S", "Country": "USA", "TypeOfEnquiry": "RFQ", "Product": "P", "Classification": "Części",
        "StatusCode": 6, "OwnerName": "Właściciel Jan", "OwnerLMId": "e1", "OwnerUnit": "DSP",
        "WorkflowId": M.upper(), "DateRequestReceived": T("2026-08-13"), "StartDateOfDataCollection": pd.NaT,
        "DataCompletionDeadline": T("2026-10-22"), "StartDateOfValuation": pd.NaT,
        "ValuationCompletionDate": pd.NaT, "SubmissionDateRequired": T("2026-10-26"),
        "TransferToCustomerDate": pd.NaT, "DateCompleted": pd.NaT, "CancelReason": None,
    }, {
        "TenderEnquiryId": 411, "TenderEnquiryNumber": 2179, "EnquiryRevision": 0, "Client": "Klient B",
        "Synonym": None, "Country": "PL", "TypeOfEnquiry": "RFQ", "Product": "P", "Classification": "Części",
        "StatusCode": 9, "OwnerName": "Właściciel Jan", "OwnerLMId": "e1", "OwnerUnit": "DSP",
        "WorkflowId": N, "DateRequestReceived": T("2026-09-01"), "StartDateOfDataCollection": pd.NaT,
        "DataCompletionDeadline": pd.NaT, "StartDateOfValuation": pd.NaT, "ValuationCompletionDate": pd.NaT,
        "SubmissionDateRequired": T("2026-09-15"), "TransferToCustomerDate": T("2026-09-10"),
        "DateCompleted": pd.NaT, "CancelReason": None,
    }, {
        "TenderEnquiryId": 412, "TenderEnquiryNumber": 2180, "EnquiryRevision": 1, "Client": "Klient C",
        "Synonym": None, "Country": "PL", "TypeOfEnquiry": "RFQ", "Product": "P", "Classification": "Części",
        "StatusCode": 9, "OwnerName": "Właściciel Ewa", "OwnerLMId": "e10", "OwnerUnit": "DSP",
        "WorkflowId": N2, "DateRequestReceived": T("2026-09-01"), "StartDateOfDataCollection": pd.NaT,
        "DataCompletionDeadline": pd.NaT, "StartDateOfValuation": pd.NaT, "ValuationCompletionDate": pd.NaT,
        "SubmissionDateRequired": T("2026-09-06"), "TransferToCustomerDate": pd.NaT,
        "DateCompleted": pd.NaT, "CancelReason": None,
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
        {"PersistenceId": 6, "InstanceId": N, "WorkflowDefinitionId": "TenderEnquiryWorkflow", "Version": 1,
         "Reference": None, "CreateTime": T("2026-09-01 08:00"), "CompleteTime": T("2026-09-10 16:00"), "Status": 2,
         "UserNameFrom": None, "Comment": None},
        {"PersistenceId": 7, "InstanceId": H, "WorkflowDefinitionId": "TenderEnquiryWorkflow", "Version": 1,
         "Reference": None, "CreateTime": T("2026-09-02"), "CompleteTime": pd.NaT, "Status": 0,
         "UserNameFrom": None, "Comment": None},
        {"PersistenceId": 8, "InstanceId": K, "WorkflowDefinitionId": "ForwardWorkflow", "Version": 1,
         "Reference": f"{STARY}.x1", "CreateTime": T("2026-09-03"), "CompleteTime": pd.NaT, "Status": 0,
         "UserNameFrom": None, "Comment": None},
        {"PersistenceId": 9, "InstanceId": N2, "WorkflowDefinitionId": "TenderEnquiryWorkflow", "Version": 1,
         "Reference": None, "CreateTime": T("2026-09-01 08:00"), "CompleteTime": T("2026-09-06 10:00"), "Status": 2,
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
        # workflow zapytania spoza zakresu, workflow bez zapytania, konsultacja z obiegu sprzed daty granicznej
        krok(501, 5, "g1", 4, "UserTask", 5, "2026-09-01", event="UserAction"),
        krok(701, 7, "h1", 4, "UserTask", 5, "2026-09-02", event="UserAction"),
        krok(801, 8, "k1", 1, "UserTask", 5, "2026-09-03", event="UserAction"),
        # zapytanie 2179: RFQ -> zbieranie danych (4 grupy równolegle, DZ ostatnia) -> kalkulacja (cofnięcie)
        # -> druga runda zbierania (tylko DZ) -> kalkulacja -> oferta
        krok(601, 6, "n-rfq", 4, "UserTask", 3, "2026-09-01 08:00", "2026-09-01 10:00", event="UserAction", pub=1),
        krok(602, 6, "n-dj", 135, "UserTask", 3, "2026-09-01 12:00", "2026-09-03 12:00", event="UserAction", pub=1),
        krok(603, 6, "n-dz", 154, "UserTask", 3, "2026-09-01 12:00", "2026-09-06 12:00", event="UserAction", pub=1),
        krok(604, 6, "n-eks", 175, "UserTask", 3, "2026-09-01 12:00", "2026-09-02 12:00", event="UserAction",
             pub=1),
        krok(605, 6, "n-tra", 184, "UserTask", 3, "2026-09-02 12:00", "2026-09-04 12:00", event="UserAction",
             pub=1),
        krok(606, 6, "n-kal1", 200, "UserTask", 3, "2026-09-06 13:00", "2026-09-07 13:00", event="UserAction",
             pub=1, outcome="Zwrócono do poprawy"),
        krok(607, 6, "n-dz2", 154, "UserTask", 3, "2026-09-07 14:00", "2026-09-08 14:00", event="UserAction",
             pub=1),
        krok(608, 6, "n-kal2", 200, "UserTask", 3, "2026-09-08 15:00", "2026-09-09 15:00", event="UserAction",
             pub=1, outcome="Zatwierdzono"),
        krok(609, 6, "n-of", 300, "UserTask", 3, "2026-09-09 16:00", "2026-09-10 16:00", event="UserAction",
             pub=1, outcome="Zatwierdzono"),
        # zapytanie 2180: DTTW, DJ (kończy 2 h po DTTW, ta sama osoba) i DZ równolegle -> oferta
        krok(901, 9, "n2-dttw", 113, "UserTask", 3, "2026-09-01 12:00", "2026-09-05 12:00", event="UserAction",
             pub=1, outcome="Zatwierdzono"),
        krok(902, 9, "n2-dj", 135, "UserTask", 3, "2026-09-01 12:00", "2026-09-05 14:00", event="UserAction",
             pub=1, outcome="Zatwierdzono"),
        krok(903, 9, "n2-dz", 154, "UserTask", 3, "2026-09-01 12:00", "2026-09-03 12:00", event="UserAction",
             pub=1, outcome="Zatwierdzono"),
        krok(904, 9, "n2-of", 300, "UserTask", 3, "2026-09-05 15:00", "2026-09-06 10:00", event="UserAction",
             pub=1, outcome="Zatwierdzono"),
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
        (701, '"RMS.APP_WYCENY_DS"', '"Utworzenie RFQ"', None),
        (801, '"Konsultant D | e8"', '"Konsultacja"', None),
        (601, '"RMS.APP_WYCENY_DS"', '"Utworzenie RFQ"', None),
        (602, '"RMS.APP_WYCENY_DJ"', '"Uzupełnienie kosztów (DJ)"', None),
        (603, '"RMS.APP_WYCENY_DZ"', '"Uzupełnienie kosztów zakupowych (DZ)"', None),
        (604, '"RMS.APP_WYCENY_EKSPEDYCJA"', '"Uzupełnienie kosztów transportu (Ekspedycja)"', None),
        (605, '"RMS.APP_WYCENY_TRANSPORT"', '"Uzupełnienie kosztów transportu (Transport)"', None),
        (606, '"RMS.APP_WYCENY_DF_W"', '"Kalkulacja finansowa (DF-W)"', None),
        (607, '"RMS.APP_WYCENY_DZ"', '"Uzupełnienie kosztów zakupowych (DZ)"', None),
        (608, '"RMS.APP_WYCENY_DF_W"', '"Kalkulacja finansowa (DF-W)"', None),
        (609, '"RMS.APP_WYCENY_DS"', '"Przygotowanie oferty do klienta (DS)"', None),
        (901, '"RMS.APP_WYCENY_DTTW"', '"Uzupełnienie technologii (DTT/W)"', '"Technolog X | e9"'),
        (902, '"RMS.APP_WYCENY_DJ"', '"Uzupełnienie kosztów (DJ)"', '"Technolog X | e9"'),
        (903, '"RMS.APP_WYCENY_DZ"', '"Uzupełnienie kosztów zakupowych (DZ)"', '"Zakupy Y | e11"'),
        (904, '"RMS.APP_WYCENY_DS"', '"Przygotowanie oferty do klienta (DS)"', None),
    ]:
        atr.append({"ExecutionPointerId": pid, "AttributeKey": "AssignedPrincipal", "AttributeValue": grupa})
        atr.append({"ExecutionPointerId": pid, "AttributeKey": "Prompt", "AttributeValue": opis})
        if wykonal:
            atr.append({"ExecutionPointerId": pid, "AttributeKey": "ActionUser", "AttributeValue": wykonal})

    zdarzenia = pd.DataFrame([
        {"EventKey": f"{M}.p-dtk", "EventTime": T("2026-08-20 08:57"), "IsProcessed": 1},
    ])
    powiazania = pd.DataFrame([
        {"TenderEnquiryId": 300, "TenderEnquiryNumber": 1500, "WorkflowId": G, "DateRequestReceived": T("2026-03-01")},
        {"TenderEnquiryId": 410, "TenderEnquiryNumber": 2178, "WorkflowId": M, "DateRequestReceived": T("2026-08-13")},
        {"TenderEnquiryId": 411, "TenderEnquiryNumber": 2179, "WorkflowId": N, "DateRequestReceived": T("2026-09-01")},
        {"TenderEnquiryId": 412, "TenderEnquiryNumber": 2180, "WorkflowId": N2, "DateRequestReceived": T("2026-09-01")},
    ])
    return Migawka(data=date(2026, 10, 26), pobrano_utc=T("2026-10-26 08:00"), zapytania=zapytania,
                   workflow=workflow, kroki=kroki, atrybuty=pd.DataFrame(atr), zdarzenia=zdarzenia,
                   powiazania=powiazania)
