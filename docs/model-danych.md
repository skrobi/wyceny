# Model danych – wnioski z kroku 0

Ustalenia na podstawie próbki pełnego przebiegu jednego zapytania (nr 2178) z bazy WYCENY.
Tabele `wfc.*` to WorkflowCore (persystencja SQL Server); czasy w nich są w **UTC**.

## Struktura

| Element | Gdzie w bazie | Uwagi |
|---|---|---|
| Zapytanie | `dbo.TenderEnquiry` | `WorkflowId` wskazuje główny workflow |
| Workflow główny | `wfc.Workflow`, `WorkflowDefinitionId = TenderEnquiryWorkflow` | `Reference` = NULL |
| Konsultacja | `wfc.Workflow`, `WorkflowDefinitionId = ForwardWorkflow` | `Reference = <InstanceId rodzica>.<Id przekazanego kroku>` |
| Krok | `wfc.ExecutionPointer` | także kroki automatyczne (powiadomienia, rozgałęzienia) |
| Zadanie użytkownika | krok z `EventName = 'UserAction'` (`StepName = UserTask`) | decyzja w `EventData` (`User`, `OutcomeValue`) |
| Atrybuty zadania | `wfc.ExtensionAttribute` | `AssignedPrincipal`, `Prompt`, `UserOptions`, `ActionUser` (wartości w JSON) |
| Moment decyzji | `wfc.Event.EventTime` (po `EventKey`) | gdy brak: `EndTime` kroku, a dalej start kroku następnego (`PredecessorId`) |

`AssignedPrincipal` to grupa AD (`RMS.APP_WYCENY_<grupa>`) dla zadań w workflow głównym
albo konkretna osoba (`Nazwisko Imię | eID`) dla konsultacji.

Stan zadania:

| Stan | Warunek |
|---|---|
| Zakończone | `EventPublished = 1` |
| Otwarte | krok `Status = 5` (WaitingForEvent) i workflow `Status = 0` (Runnable) |
| Wstrzymane | krok `Status = 5` i workflow `Status = 1` (Suspended) |
| Anulowane | pozostałe (np. krok anulowany, workflow zakończony bez decyzji) |

## Przebieg konsultacji („Przekaż do”)

1. Użytkownik w zadaniu wybiera „Przekaż do” (`OutcomeValue = "Przekazano do konsultacji"`) i wskazuje osobę.
2. Powstaje `ForwardWorkflow`: `ForwardTaskNotification` → `UserTask` z `Prompt = "Konsultacja"`
   (opcje: Zatwierdź / Anuluj / Przekaż do).
3. Po decyzji konsultanta: `ForwardTaskResponseNotification` (odpowiedź do przekazującego).
4. Konsultant może przekazać dalej – powstaje `ForwardWorkflow` potomny (**poziom 2, 3…**).
5. W jednym `ForwardWorkflow` może być **kilka rund** (`UserTask` uruchamiany ponownie, np. 24.09→29.09 i 29.09→19.10).

### Ważne obserwacje

- **Konsultacja nie blokuje zadania głównego.** Zadanie DTK zatwierdzono 20.08, a konsultacja przekazana z niego
  17.08 wciąż jest otwarta. Podobnie przy rozeznaniu produkcyjnym: konsultacja poziomu 1 otwarta od 2.09, choć
  poziom 2 odpowiedział 7.09, a zadanie główne zatwierdzono 10.09.
  Takie konsultacje nazywamy **zawieszonymi**. Zawyżają liczbę otwartych zadań i obciążenie konsultantów
  (dotyczy to także obecnego pulpitu w Excelu).
- **Zbieranie danych to faza równoległa.** Po kroku `DataCollection` startują jednocześnie zadania grup DTTW, DJ, DZ,
  DF_P, DLS, PROGRAM, EKSPEDYCJA (po niej TRANSPORT), ITCK oraz zadania wyjścia z obiegu (DS, DTK).
  Czas fazy wyznacza **najwolniejsza gałąź** – to podstawa analizy ścieżki krytycznej (krok 4).
- Zadania w workflow głównym po decyzji pozostają `Status = 2` (Running, kontener) bez `EndTime`;
  zadania w gałęziach równoległych i konsultacjach dostają `Status = 3` i `EndTime`.

## Fazy procesu (krok 2)

Zadania workflow głównego są przypisane do faz po początku opisu (`wyceny/proces.py`, lista `FAZY`):

| Faza | Zadania |
|---|---|
| Tworzenie RFQ | Utworzenie RFQ, Uzupełnienie Zapytania |
| Weryfikacja ITC | Weryfikacja ITC |
| Weryfikacja RFQ | Weryfikacja RFQ |
| Weryfikacja dokumentacji | Weryfikacja dokumentacji technicznej |
| Uzupełnienie BOM | Uzupełnienie BOM |
| Rozeznanie produkcyjne | Rozeznanie produkcyjne |
| Zbieranie danych (równolegle) | Uzupełnienie technologii, Uzupełnienie kosztów…, Weryfikacja klasyfikacji i autoryzacji (ITC), Pozostałe koszty |
| Kalkulacja finansowa | Kalkulacja finansowa (DF-W) |
| Przygotowanie oferty | Przygotowanie oferty do klienta |
| Inne | pozostałe (np. Wymagana akcja serwisowa, Anulowane RFQ) |

Czas w fazie to suma przedziałów, w których było otwarte co najmniej jedno zadanie fazy (równoległe liczone raz).
Zadania fazy nakładające się w czasie tworzą rundę – powrót po cofnięciu to kolejna runda.

## Grupy zaobserwowane w próbce

DS, ITCC, DTK, DTTW, DJ, DZ, DF_P, DLS, PROGRAM, EKSPEDYCJA, TRANSPORT, ITCK.

## Zakres i wykluczenia

- Zapytania od `TenderEnquiryId` = 758 (`pierwsze_zapytanie_id`); wcześniejsze to głównie testy.
- Workflow, kroki i zdarzenia pobierane od daty granicznej `data_startu` (2026-04-01) – obiegi zapytań z zakresu powstały po niej.
- Pomijane są zadania wyjścia z obiegu: opis zaczyna się od „Ewentualne zmiany w RFQ” lub
  „Ewentualne zmiany w BOM” – razem z konsultacjami uruchomionymi z nich.
- Daty zapytania sprzed 1900 r. (np. `0001-01-01`, „pusta” data z .NET) traktowane są jako brak.

## Pytania otwarte

1. Czy przekazujący powinien czekać na odpowiedź konsultanta? Jeśli tak – zatwierdzanie przed odpowiedzią
   jest problemem procesu; jeśli nie – zawieszone konsultacje powinny zamykać się automatycznie (zmiana w aplikacji).
2. Czy zadanie w workflow głównym może dostać kilka konsultacji równolegle (do różnych osób)? Model to obsługuje,
   ale warto potwierdzić na danych.
