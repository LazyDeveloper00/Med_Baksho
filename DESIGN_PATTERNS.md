# Six Design Patterns in Mediবাক্স

## 1. Strategy Pattern

**Files:** `core/chatbot/strategies.py`, `core/chatbot/service.py`

`AIProviderStrategy` defines one common `generate_response()` operation. `OpenRouterStrategy` and `HuggingFaceStrategy` implement it. `ChatbotService` can switch provider without changing patient-record or view code.

## 2. Observer Pattern

**Files:** `core/approvals/observer.py`, `core/approvals/services.py`

`ApprovalService` is the subject. It attaches `Observer` objects and notifies them after doctor or medicine approval/rejection. `UserNotificationObserver` stores an in-system notification event in `logs/notifications.jsonl` without adding a twentieth database table.

## 3. Factory Pattern

**File:** `core/accounts/factories.py`

`AccountFactory.create_account()` uses a role-to-creator registry and concrete creator classes: `PatientAccountCreator`, `DoctorAccountCreator`, and `AdminAccountCreator`. The factory contains no `if`, `elif`, `else`, `match`, or ternary selection. Each creator builds the shared `client` row and its matching role row in one transaction.

## 4. Builder Pattern

**File:** `core/records/builders.py`

`PrescriptionBuilder` creates the required `prescription` object first, then adds zero or more `prescriptionmedicine`, `prescriptiontest`, and `prescriptionimage` items. This fits a prescription because it has a required core and multiple optional child parts.

## 5. Facade Pattern

**File:** `core/records/facades.py`

`MedicalRecordFacade` gives views a small interface for creating and searching medical records. It hides ownership checks, PNG storage, the builder, database transactions, and nested query logic.

## 6. Proxy Pattern

**File:** `core/chatbot/proxy.py`

`ChatbotProxy` stands between a patient and `ChatbotService`. It blocks inactive accounts, non-patient users, empty/oversized questions, and excessive repeated requests before any external AI request is made.

## Why the other taught patterns were not selected

- Singleton was avoided because Django already manages database connections and application configuration; forcing another global singleton would add little value.
- Decorator is already heavily used by Django, but the project requirement is clearer when the six custom patterns are visible as project classes.
- Adapter would overlap with the Strategy implementation for AI providers.
- Iterator would be artificial because Django QuerySets already provide iteration over records.
