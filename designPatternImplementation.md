# Mediবাক্স Backend — Complete Guide to the 6 Design Patterns

## Purpose of this document

This document explains **all six design patterns implemented in the Mediবাক্স backend**, exactly where they are used, the classes and methods involved, how the request flows through them, why each implementation qualifies as that pattern, how the patterns interact with the Django backend and database, and what to say about them in a viva/presentation.

The six patterns are:

1. **Strategy Pattern** — AI provider switching
2. **Observer Pattern** — approval notifications
3. **Factory Method / Registry Factory Pattern** — account creation by role
4. **Proxy Pattern** — protected access to the chatbot service
5. **Builder Pattern** — construction of prescriptions with optional child records
6. **Facade Pattern** — simplified medical-record workflows

The explanations below are verified against the uploaded backend source snapshot and the Mediবাক্স UML/design documents.

---

# 1. Quick architecture map

| Pattern | Category | Main purpose in Mediবাক্স | Main implementation file | Main class(es) |
|---|---|---|---|---|
| Strategy | Behavioral | Allow the chatbot to use different AI providers without changing `ChatbotService` | `core/chatbot/strategies.py`, `core/chatbot/service.py` | `AIProviderStrategy`, `OpenRouterStrategy`, `HuggingFaceStrategy`, `ChatbotService` |
| Observer | Behavioral | Notify users when doctor registrations or medicine submissions are approved/rejected | `core/approvals/observer.py`, `core/approvals/services.py` | `Observer`, `UserNotificationObserver`, `ApprovalService` |
| Factory | Creational | Create patient, doctor, and admin accounts using role-specific creator objects | `core/accounts/factories.py` | `AccountCreator`, `PatientAccountCreator`, `DoctorAccountCreator`, `AdminAccountCreator`, `AccountFactory` |
| Proxy | Structural | Protect chatbot access with authorization, validation, and rate limiting before forwarding to the real chatbot service | `core/chatbot/proxy.py` | `ChatbotProxy` |
| Builder | Creational | Build a prescription step-by-step together with medicines, tests, and images | `core/records/builders.py` | `PrescriptionBuilder` |
| Facade | Structural | Give views one simple entry point for complex medical-record operations | `core/records/facades.py` | `MedicalRecordFacade` |

A useful way to remember the entire design is:

```text
ACCOUNT CREATION
HTTP request
   -> AccountFactory
      -> PatientAccountCreator / DoctorAccountCreator / AdminAccountCreator
         -> Client + role table records

CHATBOT
HTTP request
   -> ChatbotProxy
      -> ChatbotService
         -> AIProviderStrategy
            -> OpenRouterStrategy OR HuggingFaceStrategy

APPROVALS
Admin request
   -> ApprovalService
      -> database update
      -> notify_observers()
         -> UserNotificationObserver
            -> notifications.jsonl

MEDICAL RECORD CREATION
HTTP request
   -> MedicalRecordFacade
      -> PrescriptionBuilder
         -> Prescription
         -> PrescriptionMedicine records
         -> PrescriptionTest records
         -> PrescriptionImage record
```

---

# 2. Strategy Design Pattern

## 2.1 Pattern category

**Behavioral design pattern.**

A behavioral pattern is mainly about **how objects communicate and how behavior can be changed**.

The Strategy Pattern is used when one task can be performed using multiple interchangeable algorithms or implementations.

In Mediবাক্স, the task is:

> Generate an AI answer using the patient's medical-record context.

The interchangeable implementations are:

- OpenRouter
- Hugging Face

Instead of writing all provider-specific API logic inside the chatbot service, each provider is placed in its own strategy class.

---

## 2.2 Files used

Primary files:

```text
backend/core/chatbot/strategies.py
backend/core/chatbot/service.py
```

The Strategy Pattern is called from:

```text
backend/core/chatbot/views.py
```

Related protection layer:

```text
backend/core/chatbot/proxy.py
```

Regression test:

```text
backend/tests/test_patterns.py
```

---

## 2.3 Main participants

### Strategy interface / abstract strategy

```python
class AIProviderStrategy(ABC):
    @abstractmethod
    def generate_response(self, question: str, context: str) -> str:
        raise NotImplementedError
```

`AIProviderStrategy` defines the common contract that every AI provider must follow.

It says:

> Any AI provider used by the chatbot must provide a `generate_response(question, context)` method and return a string.

Important details:

- It inherits from Python's `ABC` — Abstract Base Class.
- `@abstractmethod` marks `generate_response()` as a method subclasses are required to implement.
- The abstract strategy does **not** contain OpenRouter or Hugging Face API details.
- The rest of the system can work with the common `AIProviderStrategy` type instead of knowing which provider is active.

### Concrete Strategy 1 — OpenRouter

```python
class OpenRouterStrategy(AIProviderStrategy):
```

Constructor:

```python
def __init__(self, api_key: str, model_name: str):
    self.api_key = api_key
    self.model_name = model_name
```

The object stores:

- OpenRouter API key
- model name

Its main operation is:

```python
def generate_response(self, question: str, context: str) -> str:
```

It performs these steps:

1. Checks that an API key exists.
2. Sends a POST request to OpenRouter's chat-completions API.
3. Adds a system instruction telling the model to act as the Mediবাক্স record assistant.
4. Sends the patient's record context plus the user's question.
5. Uses a low temperature (`0.2`) for more controlled answers.
6. Checks the HTTP response for failure with `raise_for_status()`.
7. Reads JSON from the API response.
8. Extracts the returned assistant message.
9. Returns the final string to `ChatbotService`.

The important architectural point is that **OpenRouter-specific HTTP formatting exists only inside this strategy**.

### Concrete Strategy 2 — Hugging Face

```python
class HuggingFaceStrategy(AIProviderStrategy):
```

Constructor:

```python
def __init__(self, api_key: str, model_name: str, api_url: str = ""):
```

The object stores:

- Hugging Face API key
- model name
- API URL

If an explicit API URL is not supplied, the strategy builds one from the model name.

Its `generate_response()` method:

1. Checks the Hugging Face API key.
2. Builds a text prompt containing the Mediবাক্স safety instruction, record context, and question.
3. Sends the prompt to the Hugging Face inference endpoint.
4. Requests a limited number of generated tokens.
5. Checks HTTP errors.
6. Handles multiple possible response shapes.
7. Removes the original prompt from `generated_text` when the provider echoes it back.
8. Returns the generated answer as a string.

Again, the Hugging Face response format is hidden from the rest of the chatbot.

### Context class — `ChatbotService`

File:

```text
core/chatbot/service.py
```

Core structure:

```python
class ChatbotService:
    def __init__(self, provider: AIProviderStrategy):
        self.provider = provider

    def set_provider(self, provider: AIProviderStrategy) -> None:
        self.provider = provider

    def answer_question(self, patient: Patient, question: str) -> str:
        return self.provider.generate_response(
            question,
            self._build_patient_context(patient)
        )
```

In Strategy terminology, `ChatbotService` is the **Context**.

The context does not implement provider-specific AI algorithms. It owns a reference to an object following `AIProviderStrategy` and delegates the generation operation to that object.

---

## 2.4 How the strategy is selected

`build_chatbot_service()` in `core/chatbot/service.py` reads the configured provider from Django settings.

Conceptually:

```text
settings.AI_PROVIDER
      |
      +-- "huggingface" -> HuggingFaceStrategy(...)
      |
      +-- otherwise ----> OpenRouterStrategy(...)
```

The selected strategy is passed into:

```python
ChatbotService(strategy)
```

This is **dependency injection**: `ChatbotService` receives the behavior it should use rather than constructing every provider internally.

The service also provides:

```python
set_provider(...)
```

so a provider can be replaced at runtime.

Example conceptually:

```python
service = ChatbotService(openrouter_strategy)
service.set_provider(huggingface_strategy)
```

No change is required to `answer_question()`.

---

## 2.5 Patient context construction

Before an AI provider is called, `ChatbotService` builds a patient-specific context.

The method is:

```python
_build_patient_context(patient)
```

In the uploaded backend snapshot it retrieves:

- the patient's disease records
- recent prescriptions
- related disease information
- facility information
- doctor name
- advice

The database relationships used include:

```text
Patient
  -> disease_records
      -> PatientDisease
          -> Disease

PatientDisease
  -> Prescription
      -> MedicalFacility
```

The generated text starts with patient information, then disease records, then recent prescriptions.

This context is passed to whichever strategy is active.

Important separation of responsibility:

```text
ChatbotService responsibility:
Build medical-record context.

AIProviderStrategy responsibility:
Generate an answer from question + context.
```

That separation is the reason adding another provider does not require rewriting record-query logic.

---

## 2.6 Complete chatbot request flow

The HTTP endpoint is:

```text
POST /api/chatbot/ask/
```

The flow is:

```text
1. Patient sends question
        |
2. core/chatbot/views.py -> ask(request)
        |
3. build_chatbot_service()
        |
4. Configuration chooses an AI strategy
        |
5. ChatbotService(strategy) is created
        |
6. ChatbotProxy wraps ChatbotService
        |
7. Proxy validates user/question/rate limit
        |
8. Proxy calls ChatbotService.answer_question()
        |
9. ChatbotService builds patient's DB context
        |
10. ChatbotService calls provider.generate_response()
        |
11. OpenRouterStrategy OR HuggingFaceStrategy sends external request
        |
12. Provider returns generated text
        |
13. Service returns answer
        |
14. Proxy returns answer
        |
15. View returns JSON response to frontend
```

Notice that **Strategy and Proxy are both used in the same chatbot workflow**, but they solve different problems:

- Strategy = which AI behavior/provider should perform generation?
- Proxy = is this request allowed and valid before reaching the real service?

---

## 2.7 Why this is actually Strategy Pattern

It satisfies the defining properties:

1. There is a common strategy abstraction: `AIProviderStrategy`.
2. There are multiple interchangeable implementations.
3. The context stores a strategy reference.
4. The context delegates behavior to the strategy.
5. The strategy can be changed without rewriting the context's main operation.

The critical line is effectively:

```python
self.provider.generate_response(...)
```

`ChatbotService` does not care whether `self.provider` is OpenRouter, Hugging Face, or another future strategy.

---

## 2.8 Extending the system with another AI provider

Suppose Mediবাক্স later uses another provider.

The correct Strategy approach is:

```python
class NewProviderStrategy(AIProviderStrategy):
    def generate_response(self, question: str, context: str) -> str:
        ...
```

The chatbot service itself does not need a new version of `answer_question()`.

This follows the **Open/Closed Principle**:

> Software should be open for extension but closed for unnecessary modification.

---

## 2.9 UML representation

The Mediবাক্স UML represents this pattern with four boxes:

```text
AIProviderStrategy        <<interface>>
OpenRouterStrategy
HuggingFaceStrategy
ChatbotService
```

Relationships:

```text
OpenRouterStrategy  - - - -▷ AIProviderStrategy
HuggingFaceStrategy - - - -▷ AIProviderStrategy

ChatbotService ◇------------ AIProviderStrategy
```

The dashed hollow-triangle relationships mean the concrete strategies implement/realize the strategy interface.

The hollow diamond at `ChatbotService` means the chatbot service uses/aggregates an `AIProviderStrategy` object.

---

## 2.10 Strategy regression test

`backend/tests/test_patterns.py` contains:

```python
def test_strategy_can_be_switched(self):
```

The test creates two fake strategy objects, gives the first to `ChatbotService`, calls `set_provider(second)`, and verifies that the provider reference changes.

What this proves:

- the service does not depend permanently on one concrete provider
- runtime replacement works
- the pattern's central interchangeability requirement is preserved

---

## 2.11 Benefits in Mediবাক্স

- OpenRouter and Hugging Face logic are separated.
- API-specific response parsing stays inside the provider strategy.
- `ChatbotService` remains focused on patient context and delegation.
- New AI providers can be added with minimal impact.
- Provider selection can be configuration-driven.
- Testing is easier because a fake strategy can replace the real external provider.
- A provider failure/change does not require redesigning the medical-record system.

---

## 2.12 Limitations / implementation notes

- `build_chatbot_service()` currently contains the configuration choice between Hugging Face and OpenRouter. That does not invalidate the Strategy Pattern; it is simply the composition/configuration point.
- External provider calls still depend on network/API availability.
- API keys must be configured in settings/environment variables.
- The current abstraction expects every provider to return a string.
- Provider-specific exceptions are allowed to propagate to the chatbot view, which converts a general provider failure into HTTP 503.

---

## 2.13 Viva answer

**Short version:**

> We used Strategy Pattern in the AI chatbot. `AIProviderStrategy` is the common interface, while `OpenRouterStrategy` and `HuggingFaceStrategy` are concrete strategies. `ChatbotService` stores an `AIProviderStrategy` and calls `generate_response()`. This lets us switch the AI provider without changing the chatbot's record-building logic.

---

# 3. Observer Design Pattern

## 3.1 Pattern category

**Behavioral design pattern.**

Observer is used when one object performs an important state change and other objects should be notified without tightly coupling the state-changing object to every notification implementation.

In Mediবাক্স, the important events are approval decisions:

- doctor approved
- doctor rejected
- medicine submission approved
- medicine submission rejected

The `ApprovalService` performs the state change and then notifies registered observers.

---

## 3.2 Files used

Primary files:

```text
backend/core/approvals/observer.py
backend/core/approvals/services.py
```

Used by HTTP endpoints in:

```text
backend/core/approvals/views.py
```

Regression test:

```text
backend/tests/test_patterns.py
```

---

## 3.3 Pattern participants

### Observer interface

```python
class Observer(ABC):
    @abstractmethod
    def update(self, message: str, user: Client) -> None:
        raise NotImplementedError
```

This is the common observer contract.

Any notification mechanism that wants to receive approval events must implement:

```python
update(message, user)
```

### Concrete Observer — `UserNotificationObserver`

```python
class UserNotificationObserver(Observer):
```

This observer converts approval events into persistent in-system notification records stored in a JSON-lines file.

Default file:

```text
settings.LOG_DIR / "notifications.jsonl"
```

When `update()` runs, it builds an event containing:

```text
user_id
message
created_at
```

It then appends one JSON object per line to the file.

Example conceptual event:

```json
{
  "user_id": 17,
  "message": "Your doctor registration was approved.",
  "created_at": "2026-08-09T...+00:00"
}
```

### Subject / Publisher — `ApprovalService`

There is no separate abstract `Subject` class.

`ApprovalService` directly acts as the Observer Pattern's **subject/publisher**.

Constructor:

```python
def __init__(self, observers: Iterable[Observer] | None = None):
    self._observers = list(observers or [])
```

It stores registered observers in:

```python
self._observers
```

The three core observer-management methods are:

```python
attach(observer)
detach(observer)
notify_observers(message, user)
```

---

## 3.4 `attach()`

```python
def attach(self, observer: Observer) -> None:
    if observer not in self._observers:
        self._observers.append(observer)
```

Purpose:

- subscribes an observer to future approval events
- prevents the same object from being added twice

Observer terminology:

```text
attach = subscribe
```

---

## 3.5 `detach()`

```python
def detach(self, observer: Observer) -> None:
    if observer in self._observers:
        self._observers.remove(observer)
```

Purpose:

- unsubscribes an observer
- that observer will no longer receive later events

Observer terminology:

```text
detach = unsubscribe
```

---

## 3.6 `notify_observers()`

```python
def notify_observers(self, message: str, user) -> None:
    for observer in tuple(self._observers):
        observer.update(message, user)
```

This is the key Observer Pattern operation.

The service does not say:

```text
"write this exact file"
```

Instead, it says:

```text
"every registered observer, update yourself"
```

That means the subject depends on the `Observer` abstraction rather than a single notification implementation.

The tuple copy helps iterate over a stable snapshot of the observer collection.

---

## 3.7 How the concrete observer is registered

In `core/approvals/views.py`:

```python
def _service():
    return ApprovalService([UserNotificationObserver()])
```

Every approval endpoint obtains an `ApprovalService` containing a `UserNotificationObserver`.

Conceptually:

```text
ApprovalService
      |
      +---- registered observer ----> UserNotificationObserver
```

So the approval workflow does not need to directly know the details of JSON serialization/file writing.

---

## 3.8 Doctor approval workflow

HTTP endpoint:

```text
POST /api/approvals/doctors/<doctor_id>/approve/
```

Flow:

```text
1. Admin sends approval request
        |
2. approvals/views.py loads Doctor
        |
3. _service() creates ApprovalService + UserNotificationObserver
        |
4. ApprovalService.approve_doctor(admin, doctor, comments)
        |
5. Verify doctor is still Pending
        |
6. Set verification_status = Approved
        |
7. Store verified_by_admin
        |
8. Store verified_at timestamp
        |
9. Save Doctor record
        |
10. notify_observers(..., doctor.user)
        |
11. UserNotificationObserver.update()
        |
12. Notification event appended to notifications.jsonl
```

`approve_doctor()` is wrapped by:

```python
@transaction.atomic
```

So the database part of the approval operation runs atomically.

---

## 3.9 Doctor rejection workflow

HTTP endpoint:

```text
POST /api/approvals/doctors/<doctor_id>/reject/
```

The process is almost the same, but:

```text
verification_status = Rejected
```

The notification starts with:

```text
Your doctor registration was rejected.
```

If the admin supplied comments, they are appended as a reason.

---

## 3.10 Medicine approval workflow

HTTP endpoint:

```text
POST /api/approvals/medicines/<submission_id>/approve/
```

`ApprovalService.approve_medicine()` performs a more complex workflow.

Steps:

1. Check that the submission is `Pending`.
2. Resolve the required `MedicineType`.
3. Resolve an existing medicine brand by `brand_id`, or create/find a brand using `brand_name`.
4. Create or retrieve the corresponding `Medicine` record.
5. Change the `MedicineSubmission` status to `Approved`.
6. Store the reviewing admin.
7. Store the approved medicine relationship.
8. Store review timestamp and comments.
9. Save the submission.
10. Publish an approval notification through `notify_observers()`.

Notification example:

```text
Your medicine submission 'Example Medicine' was approved.
```

---

## 3.11 Medicine rejection workflow

HTTP endpoint:

```text
POST /api/approvals/medicines/<submission_id>/reject/
```

Steps:

1. Check submission is `Pending`.
2. Set status to `Rejected`.
3. Save reviewing admin.
4. Save review time.
5. Save optional comments.
6. Save the record.
7. Notify the patient through the observer.

---

## 3.12 Reading notifications

The Observer Pattern is used to **produce** events during approvals.

The notifications endpoint is:

```text
GET /api/approvals/notifications/
```

It calls:

```python
UserNotificationObserver().read_for_user(request.client.user_id)
```

`read_for_user()`:

1. opens the JSON-lines notification file
2. parses each line
3. ignores malformed JSON lines
4. keeps only events whose `user_id` matches the current user
5. returns the newest records first
6. limits the number of returned events, defaulting to 50

This gives the frontend a simple in-system notification list.

---

## 3.13 Why this is actually Observer Pattern

It contains all essential Observer roles:

```text
Subject / Publisher:
ApprovalService

Observer abstraction:
Observer

Concrete observer:
UserNotificationObserver

Subscription operations:
attach(), detach()

Broadcast operation:
notify_observers()

Callback:
observer.update(...)
```

Most importantly, `ApprovalService` does not have to implement every possible notification behavior itself.

---

## 3.14 How the pattern can be extended

A future implementation could add:

```python
class EmailObserver(Observer):
    def update(self, message, user):
        ...
```

or:

```python
class PushNotificationObserver(Observer):
    def update(self, message, user):
        ...
```

Then multiple observers could be registered:

```text
ApprovalService
   |
   +--> UserNotificationObserver
   +--> EmailObserver
   +--> PushNotificationObserver
```

The approval logic itself would not need to be rewritten.

---

## 3.15 UML representation

The UML uses three pattern boxes:

```text
Observer                  <<interface>>
UserNotificationObserver
ApprovalService
```

Relationships:

```text
UserNotificationObserver - - - -▷ Observer
ApprovalService ◇---------------- 0..* Observer
UserNotificationObserver - - - -> User/Client
```

The UML deliberately does not add a separate abstract Subject class. `ApprovalService` performs that role directly.

---

## 3.16 Observer regression test

Test method:

```python
test_observer_attach_detach_and_notify
```

It uses a fake observer that stores received events.

The test verifies:

1. `attach()` registers it.
2. `notify_observers()` calls its `update()` method.
3. `detach()` removes it.
4. Later notifications are not delivered after detachment.

That directly validates Observer behavior.

---

## 3.17 Benefits

- Approval logic is separated from notification output logic.
- More notification channels can be added later.
- The subject depends on an interface instead of a concrete delivery mechanism.
- Approval methods remain easier to read.
- Observer objects are testable independently.

---

## 3.18 Limitations / implementation notes

- The current concrete observer stores notifications in a JSONL file rather than a database table.
- `threading.Lock` protects writes/reads between threads inside the same Python process, but it is not a distributed multi-server locking system.
- The approval view constructs a new `ApprovalService` per request. The subscription list is therefore configuration for that service instance, not a global persistent subscriber registry.
- Notification file writing occurs after the model save inside the approval method. Database transaction semantics and filesystem writes are not one single cross-system transaction.

These are implementation choices, not reasons the design stops being Observer Pattern.

---

## 3.19 Viva answer

> We used Observer Pattern in the approval module. `ApprovalService` is the subject, `Observer` is the interface, and `UserNotificationObserver` is the concrete observer. When an admin approves or rejects a doctor or medicine submission, `ApprovalService` changes the database state and calls `notify_observers()`. Each registered observer receives `update(message, user)`. Our current observer writes an in-system notification event to a JSONL file.

---

# 4. Factory Design Pattern

## 4.1 Pattern category

**Creational design pattern.**

The implementation combines two closely related ideas:

1. **Factory Method** through the `AccountCreator` hierarchy.
2. A **registry-based factory dispatcher** through `AccountFactory`.

For course/presentation purposes, it can be called the **Factory Pattern**, with `AccountCreator` providing the Factory Method behavior.

Its purpose is to centralize account construction and remove role-specific object-creation logic from the HTTP views.

---

## 4.2 Files used

Main implementation:

```text
backend/core/accounts/factories.py
```

Used in:

```text
backend/core/accounts/views.py
backend/core/management/commands/create_admin.py
```

Regression tests:

```text
backend/tests/test_patterns.py
```

---

## 4.3 Why a factory is needed

Mediবাক্স has a common account table:

```text
Client
```

and separate role tables:

```text
Patient
Doctor
Admin
```

Creating an account therefore means more than constructing one object.

For example, registering a patient requires:

```text
1. Create Client
2. Hash password
3. Normalize name/email/phone
4. Set account status
5. Create Patient linked to Client
6. Copy patient-specific fields
```

Registering a doctor shares step 1 but has different role-specific fields and a default verification status.

If all of this were written directly in each view, the code would be duplicated and tightly coupled to model construction.

---

## 4.4 Base creator — `AccountCreator`

```python
class AccountCreator(ABC):
```

It defines the shared creation algorithm.

The main method is:

```python
@transaction.atomic
def create(self, *, password: str, **data: Any):
```

It creates the common `Client` record:

- trims full name
- lowercases and trims email
- trims optional phone
- hashes password using Django `make_password()`
- sets status to `Active`

Then it calls:

```python
self.create_role(client=client, **data)
```

That call is the key Factory Method idea.

The base creator knows that a role record must be created, but it lets the subclass decide **which role object** and **how**.

Abstract method:

```python
@abstractmethod
def create_role(self, *, client: Client, **data: Any):
    raise NotImplementedError
```

---

## 4.5 `PatientAccountCreator`

```python
class PatientAccountCreator(AccountCreator):
```

Implements:

```python
def create_role(...) -> Patient:
```

It creates a `Patient` linked to the new `Client`.

Patient-specific data:

- date of birth
- blood group
- address

So the shared algorithm remains in `AccountCreator.create()`, while patient construction is in the patient creator.

---

## 4.6 `DoctorAccountCreator`

```python
class DoctorAccountCreator(AccountCreator):
```

Creates a `Doctor` linked to the new `Client`.

Doctor-specific fields:

- licence number
- degree
- field of expertise
- workplace
- verification status

The initial verification status is:

```text
Pending
```

That integrates account creation with the later admin approval workflow.

---

## 4.7 `AdminAccountCreator`

```python
class AdminAccountCreator(AccountCreator):
```

Creates an `Admin` linked to the `Client`.

The normal public account routes expose patient and doctor registration. Admin creation is performed through the Django management command:

```text
core/management/commands/create_admin.py
```

That command also uses the same factory:

```python
AccountFactory.create_account("admin", ...)
```

Therefore the factory is reused by both HTTP workflows and command-line administration.

---

## 4.8 Registry dispatcher — `AccountFactory`

The factory maintains this registry:

```python
_creators = {
    "patient": PatientAccountCreator,
    "doctor": DoctorAccountCreator,
    "admin": AdminAccountCreator,
}
```

The public factory entry point is:

```python
AccountFactory.create_account(role, password=..., **data)
```

The role is normalized:

```text
strip whitespace
convert to lowercase
```

Then the factory performs a dictionary lookup to obtain the appropriate creator class.

Conceptually:

```text
"patient" -> PatientAccountCreator
"doctor"  -> DoctorAccountCreator
"admin"   -> AdminAccountCreator
```

Then it executes:

```python
creator_class().create(...)
```

---

## 4.9 Why the registry matters

A naive implementation might contain:

```text
if role == patient
else if role == doctor
else if role == admin
```

This project intentionally avoids that inside the factory module.

Instead, role selection is data-driven through the dictionary registry.

That means adding a new creator primarily requires:

1. create a new `AccountCreator` subclass
2. register its name in `_creators`

The dispatcher itself does not need a growing `if/elif/switch` chain.

---

## 4.10 Important faculty constraint: no conditional branching in the factory module

The test suite explicitly protects this requirement.

Test:

```python
test_factory_module_has_no_conditional_branch_nodes
```

It parses `factories.py` with Python's `ast` module and rejects these syntax-tree node types:

```text
ast.If
ast.IfExp
ast.Match
```

That means the factory implementation has no:

```text
if
ternary if-expression
match/case
```

for role selection.

Instead, it uses:

```python
creator_class = cls._creators[normalized_role]
```

and catches a `KeyError` to report an unsupported role.

This is an important detail to mention in a viva because it is not accidental; it is enforced by a regression test.

---

## 4.11 Transaction safety

`AccountCreator.create()` is decorated with:

```python
@transaction.atomic
```

This is extremely important because account creation writes at least two related records:

```text
Client
+
Patient/Doctor/Admin
```

If creating the role record fails, Django can roll back the database transaction instead of leaving an incomplete Client with no corresponding role.

So the factory is also the correct place for transaction control over the complete creation workflow.

---

## 4.12 Patient registration flow

Endpoint:

```text
POST /api/accounts/register/patient/
```

Flow:

```text
1. accounts/views.py receives request
        |
2. read_payload()
        |
3. validate required fields
        |
4. parse date_of_birth if supplied
        |
5. AccountFactory.create_account("patient", ...)
        |
6. Registry selects PatientAccountCreator
        |
7. AccountCreator.create()
        |
8. Create Client
        |
9. PatientAccountCreator.create_role()
        |
10. Create Patient linked to Client
        |
11. Return client + p_id
```

---

## 4.13 Doctor registration flow

Endpoint:

```text
POST /api/accounts/register/doctor/
```

Flow:

```text
1. validate full_name, email, password, licence_number
2. AccountFactory.create_account("doctor", ...)
3. registry returns DoctorAccountCreator
4. common Client is created
5. Doctor role row is created
6. verification_status becomes Pending
7. response returns doctor details
```

The later Observer-based approval workflow can then approve or reject that pending doctor.

This is an example of two patterns cooperating without being the same pattern:

```text
Factory -> creates Doctor in Pending state
Observer workflow -> notifies Doctor after admin decision
```

---

## 4.14 Admin creation flow

Command:

```text
python manage.py create_admin --name ... --email ... --password ...
```

The command calls:

```python
AccountFactory.create_account("admin", ...)
```

The registry resolves `AdminAccountCreator`, which creates the common Client and Admin role row.

---

## 4.15 Why this is actually Factory Pattern

It centralizes object creation behind one interface:

```python
AccountFactory.create_account(...)
```

The caller does not manually instantiate role models.

Additionally, the base creator delegates role-specific construction to subclass implementations of:

```python
create_role(...)
```

That is the Factory Method aspect.

Pattern mapping:

```text
Creator:
AccountCreator

Factory Method:
create_role()

Concrete Creators:
PatientAccountCreator
DoctorAccountCreator
AdminAccountCreator

Dispatcher / factory entry point:
AccountFactory

Products:
Client + Patient
Client + Doctor
Client + Admin
```

---

## 4.16 Factory regression tests

Two tests are directly relevant.

### Test 1 — branch restriction

```python
test_factory_module_has_no_conditional_branch_nodes
```

Guarantees the factory module does not contain `if`, ternary-if, or `match` AST nodes.

### Test 2 — registry completeness

```python
test_factory_registry_contains_all_roles
```

Verifies that `_creators` contains exactly:

```text
patient
doctor
admin
```

---

## 4.17 Benefits

- Registration views remain thin.
- Shared Client creation is written once.
- Password hashing is centralized.
- Role-specific construction is separated by class.
- Account creation is atomic.
- Admin creation can reuse the same mechanism.
- The factory meets the branch-free requirement.
- Testing creator selection is straightforward.

---

## 4.18 Limitations / implementation notes

- The registry must be updated when a new role is introduced.
- The factory returns a tuple `(client, role_object)` rather than a single unified domain object.
- Field-level HTTP validation still happens partly in the views, while construction normalization happens in the factory.
- `try/except KeyError` is used to reject unknown roles; this is deliberately different from an `if/elif` role chain.

---

## 4.19 Viva answer

> We used Factory Pattern for account creation in `core/accounts/factories.py`. `AccountCreator` contains the common Client-creation workflow and defines the abstract factory method `create_role()`. `PatientAccountCreator`, `DoctorAccountCreator`, and `AdminAccountCreator` implement the role-specific part. `AccountFactory` uses a dictionary registry to select the creator by role. We deliberately use no if/else/match branching in the factory module, and a test checks that using Python AST.

---

# 5. Proxy Design Pattern

## 5.1 Pattern category

**Structural design pattern.**

A Proxy sits in front of another object and controls access to it.

In Mediবাক্স, the real service is:

```text
ChatbotService
```

The proxy is:

```text
ChatbotProxy
```

Before a request reaches the expensive/external-AI workflow, the proxy performs access and input checks.

---

## 5.2 Files used

Main implementation:

```text
backend/core/chatbot/proxy.py
```

Used in:

```text
backend/core/chatbot/views.py
```

Real service:

```text
backend/core/chatbot/service.py
```

Regression tests:

```text
backend/tests/test_patterns.py
```

---

## 5.3 Main proxy object

```python
class ChatbotProxy:
```

Constructor:

```python
def __init__(
    self,
    service: ChatbotService,
    max_requests: int = 5,
    window_seconds: int = 60
):
```

The proxy stores:

- the real `ChatbotService`
- maximum requests per time window
- rate-limit window length

The service is passed into the proxy:

```python
self.service = service
```

This is composition/wrapping:

```text
ChatbotProxy
   |
   +-- wraps --> ChatbotService
```

---

## 5.4 The proxy entry point

```python
def answer(self, client: Client, patient: Patient, question: str) -> str:
```

The frontend does not directly call `ChatbotService.answer_question()` through the HTTP view.

Instead the view calls:

```python
proxy.answer(...)
```

Only after the proxy's checks succeed does it forward the request to:

```python
self.service.answer_question(patient, cleaned)
```

That final forwarding line is the essence of the Proxy Pattern.

---

## 5.5 Check 1 — account status

```python
if client.account_status.lower() != "active":
    raise PermissionError(...)
```

Purpose:

- suspended/inactive accounts cannot consume chatbot resources
- unauthorized calls are stopped before external AI access

---

## 5.6 Check 2 — patient/client identity match

```python
if patient.user_id != client.user_id:
    raise PermissionError("Patient account mismatch.")
```

Purpose:

- prevents one authenticated client from using another patient's chatbot context
- adds a domain-level authorization check in front of the real service

This is particularly important because `ChatbotService` reads medical-record information.

---

## 5.7 Check 3 — input normalization

```python
cleaned = " ".join(question.split())
```

This:

- removes leading/trailing whitespace
- collapses repeated whitespace inside the question

Example:

```text
"   What   medicines   did I take?  "
```

becomes:

```text
"What medicines did I take?"
```

---

## 5.8 Check 4 — reject empty question

If normalization produces an empty string, the proxy raises:

```text
Question cannot be empty.
```

This prevents a pointless AI request.

---

## 5.9 Check 5 — maximum question length

If the normalized question exceeds 500 characters:

```text
Question cannot exceed 500 characters.
```

This protects the backend/provider from oversized user input.

---

## 5.10 Check 6 — rate limiting

The proxy maintains:

```python
_request_times: dict[int, deque[float]] = defaultdict(deque)
```

Key:

```text
client.user_id
```

Value:

```text
queue/deque of recent request times
```

Default limits:

```text
5 requests
per 60 seconds
```

The method:

```python
_enforce_rate_limit(user_id)
```

works as follows:

```text
1. Read monotonic current time.
2. Get that user's request-history deque.
3. Remove timestamps older than the current time window.
4. Count remaining timestamps.
5. If count >= maximum, reject request.
6. Otherwise append the new timestamp.
```

Why `monotonic()` is useful:

- rate limiting needs elapsed time
- monotonic time does not move backward if the system clock changes

---

## 5.11 Forwarding to the real subject

If every proxy rule passes:

```python
return self.service.answer_question(patient, cleaned)
```

So the object chain is:

```text
Caller
  -> Proxy
      -> Real Service
```

The proxy does not generate the AI answer itself.

---

## 5.12 HTTP request flow

Endpoint:

```text
POST /api/chatbot/ask/
```

View:

```python
proxy = ChatbotProxy(build_chatbot_service())
answer = proxy.answer(
    request.client,
    request.patient,
    question
)
```

Complete flow:

```text
Patient frontend
      |
      v
chatbot view
      |
      v
ChatbotProxy
      |
      +-- account active?
      +-- same patient/client?
      +-- normalize question
      +-- non-empty?
      +-- <= 500 chars?
      +-- within rate limit?
      |
      v
ChatbotService
      |
      v
AI strategy
      |
      v
external AI provider
```

---

## 5.13 Error mapping

The view converts proxy exceptions to HTTP responses:

```text
ValueError      -> HTTP 400
PermissionError -> HTTP 403
provider/general exception -> HTTP 503
```

This keeps proxy policy errors distinct from external-service failure.

---

## 5.14 Why this is actually Proxy Pattern

It has the standard participants:

```text
Client/caller:
chatbot view

Proxy:
ChatbotProxy

Real subject:
ChatbotService
```

The proxy exposes an operation that represents access to the real service, performs additional control logic, then forwards the valid request.

It is specifically similar to a **protection proxy**, because access control is a major responsibility. It also performs rate limiting and validation.

---

## 5.15 Proxy regression tests

### Empty-question test

```python
test_proxy_blocks_empty_question
```

It verifies:

- an empty/whitespace-only question raises `ValueError`
- the wrapped service is **not called**

That second point is important: blocked requests never reach the real service.

### Forwarding test

```python
test_proxy_forwards_valid_question
```

It verifies:

- a valid question reaches the real service
- whitespace is normalized before forwarding
- the result from the real service is returned by the proxy

---

## 5.16 Benefits

- Protects medical-record chatbot access.
- Stops invalid requests before external API cost/network usage.
- Centralizes rate limiting.
- Keeps validation/security logic outside `ChatbotService`.
- Makes the real service easier to test and reason about.
- Allows future caching, logging, quota checking, or audit logic to be added at the access boundary.

---

## 5.17 Limitations / implementation notes

The current limiter is process-local memory:

```python
_request_times
```

Therefore:

- it resets when the Django process restarts
- separate worker processes do not automatically share the same rate-limit history
- it is suitable for a course/demo backend but not equivalent to a distributed Redis-backed production limiter

The proxy also assumes a valid `Client` and `Patient` object have already been attached to the request by the authentication/role layer.

---

## 5.18 Viva answer

> We used a protection Proxy in the chatbot. `ChatbotProxy` wraps `ChatbotService`. The view calls the proxy instead of calling the real chatbot service directly. The proxy checks account status, verifies the patient belongs to the logged-in client, normalizes and validates the question, enforces a per-user rate limit, and only then forwards the request to `ChatbotService.answer_question()`.

---

# 6. Builder Design Pattern

## 6.1 Pattern category

**Creational design pattern.**

Builder is useful when creating one object is a multi-step process with many optional parts.

In Mediবাক্স, a prescription is not just one database row. A complete prescription can contain:

```text
Prescription base record
+ zero or more medicines
+ zero or more medical tests
+ optional prescription image
```

That makes prescription creation a good Builder use case.

---

## 6.2 Files used

Main implementation:

```text
backend/core/records/builders.py
```

Used primarily by:

```text
backend/core/records/facades.py
```

The Facade is called from:

```text
backend/core/records/views.py
```

Regression test:

```text
backend/tests/test_patterns.py
```

---

## 6.3 Builder object

```python
@dataclass
class PrescriptionBuilder:
```

The builder stores the state of a prescription being assembled.

Fields:

```python
patient_disease
base_data
medicines
tests
images
```

Meaning:

### `patient_disease`

The `PatientDisease` record the prescription belongs to.

### `base_data`

Dictionary containing base Prescription fields such as:

- facility ID
- prescription date
- doctor name
- custom facility name
- illness location
- advice
- additional notes

### `medicines`

A list of medicine-entry dictionaries waiting to be created.

### `tests`

A list of test-entry dictionaries waiting to be created.

### `images`

A list of prescription-image metadata dictionaries waiting to be created.

---

## 6.4 Fluent builder methods

The Builder uses a **fluent interface**.

Every add/set method returns `self`.

### Set base fields

```python
def set_base(self, **data):
    self.base_data.update(data)
    return self
```

### Add a medicine part

```python
def add_medicine(self, **data):
    self.medicines.append(data)
    return self
```

### Add a test part

```python
def add_test(self, **data):
    self.tests.append(data)
    return self
```

### Add an image part

```python
def add_image(self, **data):
    self.images.append(data)
    return self
```

Because they return the same builder, calls can conceptually be chained:

```python
builder.set_base(...).add_medicine(...).add_test(...)
```

This is not mandatory for Builder Pattern, but it makes construction readable.

---

## 6.5 Validation before building

Private method:

```python
_validate()
```

Required base fields:

```text
prescription_date
doctor_name
```

Facility rule:

```text
Either facility_id must be supplied
OR custom_facility_name must be supplied.
```

If these requirements are not satisfied, the builder raises `ValueError` before creating the object graph.

---

## 6.6 Date helpers

The module contains helper functions for converting incoming values to Python `date` objects.

### `_as_optional_date()`

Accepts:

- `None` / empty string -> `None`
- a date object -> unchanged
- ISO date text -> converted using `date.fromisoformat()`

Otherwise it raises a field-specific validation error.

### `_as_required_date()`

Uses `_as_optional_date()` but rejects `None`.

These helpers let the builder accept request-derived values while keeping model writes consistent.

---

## 6.7 Boolean helper

`_as_bool()` recognizes values such as:

```text
True / False
1 / 0
"true" / "false"
"yes" / "no"
"on" / "off"
```

This is mainly used for `course_completed` in prescription-medicine entries.

---

## 6.8 The `build()` method

The final construction happens in:

```python
@transaction.atomic
def build(self) -> Prescription:
```

This method turns all the temporarily collected builder state into actual database rows.

Because it is `transaction.atomic`, the database changes for the prescription and its children are treated as one transaction.

If an exception occurs while constructing a later part, earlier database writes inside the transaction can be rolled back.

---

## 6.9 Build step 1 — validate

```python
self._validate()
```

Nothing is created until required base data is present.

---

## 6.10 Build step 2 — resolve medical facility

If `facility_id` was supplied, the builder retrieves an active `MedicalFacility`:

```text
MedicalFacility.objects.get(facility_id=..., is_active=True)
```

If there is no selected facility, the custom facility name can be stored in the Prescription instead.

---

## 6.11 Build step 3 — create base Prescription

The builder creates the main `Prescription` row.

Fields include:

- patient disease
- facility relationship
- prescription date
- doctor name
- custom facility name
- illness location
- advice
- additional notes

At this point the parent object exists, so child entries can reference it.

---

## 6.12 Build step 4 — create medicine children

For each pending medicine dictionary:

1. Retrieve an active `Medicine` by `medicine_id`.
2. Convert `times_per_day` to integer.
3. Convert `duration_days` to integer.
4. Ensure both values are greater than zero.
5. Parse optional start date.
6. Parse optional end date.
7. Ensure end date is not earlier than start date.
8. Create `PrescriptionMedicine`.

Stored medicine-entry fields include:

- medicine
- dosage
- times per day
- duration days
- start date
- end date
- course completed
- side effects
- effectiveness

This child table links the Prescription and Medicine while also storing medication-course details.

---

## 6.13 Build step 5 — create medical-test children

For each pending test dictionary:

1. Retrieve an active `MedicalTest` by `test_id`.
2. Parse optional test date.
3. Create `PrescriptionTest`.

Fields include:

- test
- completion status
- test date
- diagnostic center name
- result summary
- custom test name

---

## 6.14 Build step 6 — create image children

For every pending image metadata dictionary, create:

```text
PrescriptionImage
```

The builder stores:

- prescription relationship
- file path
- file size in KB

The actual PNG file validation and file storage are handled by the Facade before this builder step.

This separation is important:

```text
Facade -> manages high-level workflow and file handling
Builder -> creates the database object graph
```

---

## 6.15 Build step 7 — return final product

The builder returns:

```python
return prescription
```

The finished product is the Prescription root object with its related child records stored in the database.

---

## 6.16 Example construction flow

Conceptually:

```python
builder = PrescriptionBuilder(patient_disease)

builder.set_base(
    prescription_date="2026-08-09",
    doctor_name="Dr. Example",
    custom_facility_name="Example Clinic"
)

builder.add_medicine(
    medicine_id=1,
    dosage="1 tablet",
    times_per_day=2,
    duration_days=5
)

builder.add_test(test_id=2)

prescription = builder.build()
```

The caller does not have to manually create `Prescription`, then remember every foreign key and child table in a separate workflow.

---

## 6.17 Why this is actually Builder Pattern

The pattern separates:

```text
construction process
```

from:

```text
finished complex product
```

Pattern mapping:

```text
Builder:
PrescriptionBuilder

Construction steps:
set_base()
add_medicine()
add_test()
add_image()

Finalization:
build()

Product:
Prescription + child database records
```

The optional lists are especially important. A prescription can have different combinations of medicines, tests, and images without requiring a different constructor for every combination.

---

## 6.18 Builder regression test

Test:

```python
test_builder_collects_optional_parts_with_fluent_interface
```

It checks that:

- `set_base()` returns the same builder
- `add_medicine()` returns the same builder
- `add_test()` returns the same builder
- `add_image()` returns the same builder
- one medicine was collected
- one test was collected
- one image was collected

That verifies the fluent, step-by-step construction interface.

---

## 6.19 Benefits

- Avoids one giant prescription constructor.
- Supports optional medicines/tests/images cleanly.
- Centralizes creation validation.
- Keeps related database writes together.
- Uses database transaction atomicity.
- Improves readability.
- Simplifies the Facade and views.
- Makes testing the construction process possible without going through the HTTP layer.

---

## 6.20 Limitations / implementation notes

- The builder is stateful until `build()` is called; a builder instance should represent one prescription construction workflow.
- Duplicate medicine/test combinations may still be constrained by the underlying database schema/composite keys.
- File bytes are not saved by the builder; it receives file metadata from the Facade. This is intentional separation of concerns.
- The builder performs both construction and domain validation. For this project's scope that keeps the medical-record workflow centralized.

---

## 6.21 Viva answer

> We used Builder Pattern for prescription creation. A prescription can have base information plus a variable number of medicines, tests, and an optional image. `PrescriptionBuilder` collects those parts through `set_base()`, `add_medicine()`, `add_test()`, and `add_image()`. These methods return `self`, so it has a fluent interface. When `build()` is called, it validates the data and creates the Prescription and all child records inside an atomic database transaction.

---

# 7. Facade Design Pattern

## 7.1 Pattern category

**Structural design pattern.**

A Facade provides one simplified interface to a more complicated group of classes/subsystems.

In Mediবাক্স, medical-record operations involve several concerns:

- patient ownership checking
- database queries
- Prescription Builder
- file validation
- file storage
- cleanup on failure
- search-filter validation
- related-model filtering

The HTTP view should not need to know every low-level step.

Therefore Mediবাক্স uses:

```text
MedicalRecordFacade
```

---

## 7.2 Files used

Main implementation:

```text
backend/core/records/facades.py
```

Uses:

```text
backend/core/records/builders.py
Django default_storage
Django ORM models
Django settings
```

Called from:

```text
backend/core/records/views.py
```

Regression test:

```text
backend/tests/test_patterns.py
```

---

## 7.3 Facade class

```python
class MedicalRecordFacade:
```

Its public high-level operations are:

```text
create_prescription(...)
patient_prescriptions(patient)
search(...)
```

It also has private/internal helper behavior:

```text
_validate_png(uploaded_file)
```

and module helper:

```text
_optional_positive_int(...)
```

---

# 7.4 Facade operation 1 — `create_prescription()`

Signature conceptually:

```python
create_prescription(
    patient,
    patient_disease_id,
    base_data,
    medicines,
    tests,
    uploaded_file=None
)
```

The caller gives the Facade high-level request data. The Facade coordinates all lower-level work.

---

## 7.5 Step 1 — ownership-scoped PatientDisease lookup

The Facade retrieves:

```python
PatientDisease.objects.get(
    patient_disease_id=patient_disease_id,
    patient=patient
)
```

Notice it filters by both:

```text
record ID
AND current patient
```

This prevents a patient from creating a prescription under another patient's disease record merely by guessing an ID.

---

## 7.6 Step 2 — create the Builder

```python
builder = PrescriptionBuilder(patient_disease).set_base(**base_data)
```

The Facade does not itself create every Prescription child row.

Instead it delegates the construction problem to the Builder.

This is a direct example of two patterns cooperating:

```text
Facade simplifies the workflow
Builder constructs the complex product
```

---

## 7.7 Step 3 — transfer medicine parts to Builder

```python
for medicine in medicines:
    builder.add_medicine(**medicine)
```

The Facade understands the high-level request list and feeds each item into the Builder.

---

## 7.8 Step 4 — transfer test parts to Builder

```python
for test in tests:
    builder.add_test(**test)
```

Same principle for tests.

---

## 7.9 Step 5 — optional PNG handling

If a file was uploaded:

```text
uploaded_file is not None
```

then the Facade:

1. validates that it is an acceptable PNG
2. creates a unique path using `uuid4()`
3. saves the file through Django `default_storage`
4. calculates approximate KB size
5. gives image metadata to the Builder

The generated storage path follows the form:

```text
prescriptions/<random-uuid>.png
```

Using a UUID prevents users with the same original filename from overwriting each other.

---

## 7.10 PNG validation

The internal method:

```python
_validate_png(uploaded_file)
```

checks:

### File extension

Must be:

```text
.png
```

### Content type

Accepted content types:

```text
image/png
application/octet-stream
```

### Maximum size

Computed using:

```text
settings.MAX_PNG_MB * 1024 * 1024
```

If invalid:

```text
Only PNG prescription images are accepted.
```

or:

```text
PNG file must be at most <configured size> MB.
```

---

## 7.11 Step 6 — delegate final DB creation to Builder

After all parts are prepared:

```python
return builder.build()
```

At that point, the Builder performs the actual multi-table prescription creation.

---

## 7.12 Step 7 — cleanup if construction fails

File storage and database transactions are separate systems.

Suppose:

1. uploaded PNG is successfully saved
2. later `builder.build()` fails because of invalid medicine data

Without cleanup, the server would contain an orphaned PNG that has no Prescription record.

The Facade handles this:

```text
try builder.build()
except failure:
    if saved file exists:
        delete it
    re-raise error
```

This is a very important high-level workflow responsibility and a strong reason for the Facade to exist.

---

# 7.13 Facade operation 2 — `patient_prescriptions()`

```python
patient_prescriptions(patient)
```

This method returns a QuerySet already scoped to the specified patient.

It also uses `select_related()` for related disease/facility data.

Conceptually:

```text
Prescription
where prescription.patient_disease.patient = current patient
```

The views use this method for:

- prescription list
- prescription detail
- search base query

This centralizes patient scoping.

---

# 7.14 Facade operation 3 — `search()`

The search facade accepts optional filters:

```text
disease_id
medicine_id
test_id
facility_id
```

The first step is:

```python
queryset = MedicalRecordFacade.patient_prescriptions(patient)
```

Therefore every search begins from the current patient's records only.

Then each optional filter is parsed as a positive integer.

Invalid examples:

```text
"abc"
0
-5
```

produce a `ValueError` instead of silently creating a malformed query.

Possible ORM filtering:

```text
disease filter
medicine-entry filter
test-entry filter
facility filter
```

Finally:

```text
distinct()
order by newest prescription date and ID
```

`distinct()` matters because joining a prescription to child medicine/test rows can otherwise duplicate the same Prescription in query results.

---

## 7.15 HTTP endpoints using the Facade

### List prescriptions

```text
GET /api/records/prescriptions/
```

Uses:

```python
MedicalRecordFacade.patient_prescriptions(request.patient)
```

### Create prescription

```text
POST /api/records/prescriptions/create/
```

Uses:

```python
MedicalRecordFacade.create_prescription(...)
```

### Get prescription detail

```text
GET /api/records/prescriptions/<prescription_id>/
```

Uses the patient-scoped QuerySet from the Facade before retrieving by ID.

### Search medical records

```text
GET /api/records/search/
```

Uses:

```python
MedicalRecordFacade.search(...)
```

---

## 7.16 How the view is simplified

Without a Facade, `prescription_create()` would need to contain logic for:

```text
PatientDisease ownership lookup
Builder creation
loop over medicines
loop over tests
PNG extension checking
PNG content-type checking
PNG size checking
unique filename generation
file storage
Builder image metadata
Builder execution
file cleanup if Builder fails
```

Instead the view mainly performs request parsing and calls one high-level operation:

```python
MedicalRecordFacade.create_prescription(...)
```

That is exactly what a Facade is meant to achieve.

---

## 7.17 Why this is actually Facade Pattern

Pattern mapping:

```text
Client:
records/views.py

Facade:
MedicalRecordFacade

Subsystems hidden/organized behind Facade:
PrescriptionBuilder
PatientDisease ORM
Prescription ORM
Django default_storage
settings-based PNG rules
search/filter ORM logic
```

The Facade does not necessarily replace access to every subsystem. It provides a simpler preferred entry point for important workflows.

---

## 7.18 Facade regression test

Test:

```python
test_facade_delegates_complex_creation_to_builder
```

It mocks:

- `PatientDisease.objects.get`
- `PrescriptionBuilder`

Then it calls:

```python
MedicalRecordFacade.create_prescription(...)
```

The test verifies that the Facade:

1. retrieves the correct patient's disease record
2. creates `PrescriptionBuilder` with that record
3. adds medicine data
4. adds test data
5. calls `builder.build()`
6. returns the result produced by the Builder

This directly checks the Facade-to-Builder delegation.

---

## 7.19 Benefits

- Keeps Django views small.
- Centralizes medical-record workflow rules.
- Ensures ownership scoping is reused.
- Hides file-storage complexity from views.
- Hides Builder coordination from views.
- Prevents orphaned uploaded files when DB construction fails.
- Centralizes search behavior.
- Makes the application service layer easier to test.

---

## 7.20 Limitations / implementation notes

- `MedicalRecordFacade` uses static methods; there is no instance state or dependency container.
- It is intentionally application-specific rather than a generic repository abstraction.
- It coordinates multiple concerns, so it should remain focused on medical-record workflows rather than becoming a universal "god class".
- The Builder is still responsible for detailed object construction; the Facade should not duplicate Builder internals.

---

## 7.21 Viva answer

> We used Facade Pattern in `MedicalRecordFacade`. The record views call a small number of high-level methods instead of coordinating multiple ORM queries, the Prescription Builder, PNG validation, file storage, cleanup, and search logic themselves. For example, `create_prescription()` verifies the PatientDisease belongs to the patient, prepares the Builder, adds medicines and tests, validates and stores an optional PNG, calls `builder.build()`, and removes the file if construction fails.

---

# 8. How Builder and Facade work together

These two are easy to confuse.

They are not duplicates.

## Facade question

> How can the caller use this complicated medical-record subsystem through one simple API?

Answer:

```text
MedicalRecordFacade
```

## Builder question

> How do we construct a Prescription that may contain many optional child parts?

Answer:

```text
PrescriptionBuilder
```

The relationship is:

```text
records view
    |
    v
MedicalRecordFacade
    |
    +-- ownership check
    +-- file validation/storage
    +-- high-level coordination
    |
    v
PrescriptionBuilder
    |
    +-- set base
    +-- add medicine(s)
    +-- add test(s)
    +-- add image metadata
    +-- build DB object graph
```

A concise viva distinction:

> The Facade simplifies access to a subsystem; the Builder constructs a complex object step by step.

---

# 9. How Strategy and Proxy work together

These are also easy to confuse because both are in the chatbot module.

## Proxy responsibility

```text
Can this request reach the chatbot service?
```

Checks:

- active account
- correct patient
- valid question
- length
- rate limit

## Strategy responsibility

```text
Which AI provider should generate the answer?
```

Options:

- OpenRouter
- Hugging Face

Combined flow:

```text
frontend
   |
   v
ChatbotProxy        <-- access control
   |
   v
ChatbotService      <-- patient context
   |
   v
AIProviderStrategy  <-- interchangeable behavior
   |
   +--> OpenRouter
   |
   +--> Hugging Face
```

A concise viva distinction:

> Proxy controls access to the real service. Strategy changes the algorithm/provider used by the real service.

---

# 10. How Factory and Observer connect in the doctor lifecycle

The patterns are independent, but they form a natural workflow.

```text
Doctor registration
      |
      v
AccountFactory
      |
      v
DoctorAccountCreator
      |
      v
Doctor created with Pending status
      |
      v
Admin reviews doctor
      |
      v
ApprovalService
      |
      +-- status = Approved/Rejected
      |
      +-- notify_observers()
             |
             v
       UserNotificationObserver
```

Factory solves **creation**.

Observer solves **reaction to a later state change**.

---

# 11. End-to-end pattern interaction map

```text
                         MEDIবাক্স BACKEND

  ACCOUNT MODULE                      CHATBOT MODULE
  --------------                      --------------

  Register request                    Ask question
        |                                  |
        v                                  v
  [FACTORY] AccountFactory            [PROXY] ChatbotProxy
        |                                  |
        v                                  v
  role-specific creator              ChatbotService
        |                                  |
        v                                  v
  Client + role row                  [STRATEGY] AIProviderStrategy
                                           |
                              +------------+------------+
                              |                         |
                              v                         v
                       OpenRouterStrategy       HuggingFaceStrategy


  APPROVAL MODULE                     RECORD MODULE
  ---------------                     -------------

  Admin decision                      Create prescription
        |                                  |
        v                                  v
  ApprovalService                     [FACADE] MedicalRecordFacade
        |                                  |
        | database state                   +-- patient ownership
        | change                           +-- PNG workflow
        |                                  +-- search API
        v                                  |
  [OBSERVER] notify_observers()             v
        |                            [BUILDER] PrescriptionBuilder
        v                                  |
  UserNotificationObserver                 +-- Prescription
        |                                  +-- Medicine children
        v                                  +-- Test children
  notifications.jsonl                     +-- Image child
```

---

# 12. Exact backend file map for the six patterns

```text
backend/
│
├── core/
│   │
│   ├── accounts/
│   │   ├── factories.py          <-- FACTORY implementation
│   │   ├── views.py              <-- Factory used for patient/doctor registration
│   │   └── urls.py
│   │
│   ├── management/
│   │   └── commands/
│   │       └── create_admin.py    <-- Factory used for admin creation
│   │
│   ├── chatbot/
│   │   ├── strategies.py         <-- STRATEGY implementations
│   │   ├── service.py            <-- Strategy Context
│   │   ├── proxy.py              <-- PROXY implementation
│   │   ├── views.py              <-- Proxy + Strategy workflow entry point
│   │   └── urls.py
│   │
│   ├── approvals/
│   │   ├── observer.py           <-- OBSERVER interface + concrete observer
│   │   ├── services.py           <-- Observer subject/publisher + approval workflow
│   │   ├── views.py              <-- Registers observer and calls ApprovalService
│   │   └── urls.py
│   │
│   ├── records/
│   │   ├── builders.py           <-- BUILDER implementation
│   │   ├── facades.py            <-- FACADE implementation
│   │   ├── views.py              <-- Calls Facade
│   │   └── urls.py
│   │
│   └── models.py                 <-- Database model classes manipulated by patterns
│
└── tests/
    └── test_patterns.py          <-- Pattern regression tests
```

---

# 13. Pattern-specific API endpoint map

## Factory-related

```text
POST /api/accounts/register/patient/
POST /api/accounts/register/doctor/
```

Admin uses the management command instead of a public registration route.

## Proxy + Strategy related

```text
POST /api/chatbot/ask/
```

## Observer related

```text
GET  /api/approvals/doctors/pending/
POST /api/approvals/doctors/<doctor_id>/approve/
POST /api/approvals/doctors/<doctor_id>/reject/

GET  /api/approvals/medicines/pending/
POST /api/approvals/medicines/<submission_id>/approve/
POST /api/approvals/medicines/<submission_id>/reject/

GET  /api/approvals/notifications/
```

## Builder + Facade related

```text
GET  /api/records/prescriptions/
POST /api/records/prescriptions/create/
GET  /api/records/prescriptions/<prescription_id>/
GET  /api/records/search/
```

---

# 14. Regression tests for the design patterns

File:

```text
backend/tests/test_patterns.py
```

Pattern-related tests in the uploaded snapshot:

| Test | Pattern | What it verifies |
|---|---|---|
| `test_strategy_can_be_switched` | Strategy | `ChatbotService` can replace its provider strategy |
| `test_observer_attach_detach_and_notify` | Observer | Subscribe, notify, unsubscribe behavior |
| `test_proxy_blocks_empty_question` | Proxy | Invalid requests are blocked before the real service |
| `test_proxy_forwards_valid_question` | Proxy | Valid normalized requests are forwarded and result returned |
| `test_factory_module_has_no_conditional_branch_nodes` | Factory | No `if`, ternary-if, or `match` in factory module |
| `test_factory_registry_contains_all_roles` | Factory | Patient, doctor, admin registry entries exist |
| `test_builder_collects_optional_parts_with_fluent_interface` | Builder | Fluent methods return self and collect optional parts |
| `test_facade_delegates_complex_creation_to_builder` | Facade | Facade resolves patient disease and delegates parts/build to Builder |

The file also contains validation regression tests unrelated to proving the six pattern structures directly.

---

# 15. What each pattern prevents

## Strategy prevents

```text
One giant chatbot class containing every provider API implementation.
```

## Observer prevents

```text
ApprovalService being permanently hard-coded to one notification mechanism.
```

## Factory prevents

```text
Registration views manually duplicating Client + role construction logic.
```

## Proxy prevents

```text
Every chatbot request directly reaching the real service/external AI without protection.
```

## Builder prevents

```text
A huge constructor/function with every possible Prescription child combination.
```

## Facade prevents

```text
Django views having to coordinate ORM ownership checks, Builder calls, files, cleanup, and search internals themselves.
```

---

# 16. SOLID principles supported by the design

The project was built around design-pattern requirements, but the patterns also support several SOLID ideas.

## Single Responsibility Principle

Examples:

```text
OpenRouterStrategy -> OpenRouter generation logic
HuggingFaceStrategy -> Hugging Face generation logic
ChatbotProxy -> access protection
PrescriptionBuilder -> object construction
MedicalRecordFacade -> workflow simplification/orchestration
UserNotificationObserver -> notification persistence
```

## Open/Closed Principle

Most visible in Strategy and Observer.

New strategy:

```text
add another AIProviderStrategy subclass
```

New observer:

```text
add another Observer implementation
```

Core calling code can remain mostly unchanged.

## Dependency Inversion Principle

`ChatbotService` depends on the `AIProviderStrategy` abstraction rather than directly depending on only OpenRouter or only Hugging Face.

`ApprovalService` stores `Observer` objects rather than being defined only around `UserNotificationObserver`.

---

# 17. Creational vs Structural vs Behavioral — using only our six patterns

## Creational

Concerned with how objects are created.

Mediবাক্স examples:

```text
Factory
Builder
```

### Factory

Chooses the appropriate account creator/product based on role.

### Builder

Constructs a complex prescription step-by-step.

---

## Structural

Concerned with how classes/objects are arranged or wrapped to form a larger structure.

Mediবাক্স examples:

```text
Proxy
Facade
```

### Proxy

Wraps the chatbot service to control access.

### Facade

Places a simplified interface in front of the medical-record subsystem.

---

## Behavioral

Concerned with communication and interchangeable behavior.

Mediবাক্স examples:

```text
Strategy
Observer
```

### Strategy

Swaps AI-generation behavior/provider.

### Observer

Broadcasts approval events to subscribed observers.

---

# 18. Common viva traps and correct answers

## Q: Why is `ChatbotService` not the Strategy?

Because `ChatbotService` is the **Context**. It owns an `AIProviderStrategy` and delegates generation to it.

Concrete strategies are `OpenRouterStrategy` and `HuggingFaceStrategy`.

---

## Q: Why is the chatbot Proxy not Strategy?

Because the Proxy does not choose an AI algorithm. It controls access to another object and forwards valid calls to it.

---

## Q: Why is `ApprovalService` called the Subject even though there is no `Subject` class?

A separate abstract Subject class is optional. `ApprovalService` contains the required subject behavior itself:

```text
observer list
attach
detach
notify
```

Therefore it is the concrete subject/publisher.

---

## Q: Why is `UserNotificationObserver` an Observer?

Because it implements the common `update(message, user)` callback and receives events from `ApprovalService` without the service having to implement the notification storage details itself.

---

## Q: Is `AccountFactory` a pure GoF Factory Method implementation?

The complete account module combines a Factory Method hierarchy with a registry dispatcher.

- `AccountCreator.create_role()` is the overridable factory method.
- Its subclasses are concrete creators.
- `AccountFactory` provides the branch-free public role-to-creator registry.

For the project it is referred to as the Factory Pattern.

---

## Q: Why use `try/except KeyError` in the factory?

Because role selection is performed by dictionary lookup. An unknown role produces `KeyError`, which is converted to a meaningful `ValueError`.

It avoids an `if/elif/match` role-selection chain.

---

## Q: What is the difference between Builder and Factory?

Factory decides **which creator/product type to create**.

Builder handles **how a complex product is assembled step by step**.

In this project:

```text
Factory -> patient/doctor/admin account creation
Builder -> prescription + optional child records
```

---

## Q: What is the difference between Facade and Proxy?

Both can stand in front of another subsystem, but their intent is different.

```text
Proxy -> controls access to an object while representing that service
Facade -> simplifies a complicated subsystem with a higher-level interface
```

Mediবাক্স:

```text
ChatbotProxy -> permission/validation/rate limit
MedicalRecordFacade -> simplified records workflow
```

---

## Q: Does Facade hide the Builder completely?

It hides Builder usage from the view, but the Builder still exists as a separate class and can be tested independently.

---

## Q: Why is `@transaction.atomic` useful in Factory and Builder/Approval operations?

Because each workflow changes multiple related database rows. If a later step fails, the database should not be left partially updated.

---

## Q: Which pattern is most directly visible in the UML?

The moderate class diagram explicitly represents the Strategy and Observer structures. The Factory, Proxy, Builder, and Facade are backend implementation patterns and are verified in the actual source/test files.

---

# 19. One-minute viva summary of all six

> We implemented six design patterns in the Mediবাক্স Django backend. Strategy is in the chatbot: `AIProviderStrategy` is implemented by `OpenRouterStrategy` and `HuggingFaceStrategy`, and `ChatbotService` can switch between them. Observer is in approvals: `ApprovalService` is the subject, and `UserNotificationObserver` receives approval or rejection events. Factory is in account creation: `AccountFactory` uses a branch-free registry of `PatientAccountCreator`, `DoctorAccountCreator`, and `AdminAccountCreator`; the common creator handles Client creation and the subclasses create role rows. Proxy is also in the chatbot: `ChatbotProxy` validates authorization, input length, empty questions, and rate limits before forwarding to `ChatbotService`. Builder is in medical records: `PrescriptionBuilder` constructs a prescription step-by-step with optional medicines, tests, and images. Facade is `MedicalRecordFacade`, which gives the views simple methods for prescription creation, patient-scoped querying, searching, PNG validation/storage, cleanup, and delegation to the Builder.

---

# 20. Ultra-short memory table

| Pattern | Remember this sentence |
|---|---|
| Strategy | **Switch the AI provider without changing the chatbot service.** |
| Observer | **Approval event happens; subscribed notification objects are updated.** |
| Factory | **Ask for a role; the correct account creator constructs Client + role.** |
| Proxy | **Check the chatbot request before allowing it to reach the real service.** |
| Builder | **Assemble one complex prescription step by step.** |
| Facade | **Give views one simple interface to a complicated record subsystem.** |

---

# 21. Pattern identification by code signature

If the faculty shows you code and asks which pattern it is, look for these shapes.

## Strategy signature

```text
interface/abstract strategy
+ several concrete strategies
+ context stores one strategy
+ context delegates behavior to it
```

Mediবাক্স names:

```text
AIProviderStrategy
OpenRouterStrategy
HuggingFaceStrategy
ChatbotService
```

## Observer signature

```text
observer interface
+ list of observers
+ attach/detach
+ notify loop
+ observer.update()
```

Mediবাক্স names:

```text
Observer
UserNotificationObserver
ApprovalService
```

## Factory signature

```text
creator abstraction
+ concrete creators
+ central creation entry point
+ caller does not instantiate role products manually
```

Mediবাক্স names:

```text
AccountCreator
PatientAccountCreator
DoctorAccountCreator
AdminAccountCreator
AccountFactory
```

## Proxy signature

```text
wrapper has reference to real service
+ performs checks
+ forwards call to real service
```

Mediবাক্স names:

```text
ChatbotProxy
ChatbotService
```

## Builder signature

```text
state collected across multiple add/set methods
+ methods return builder/self
+ build() creates final product
```

Mediবাক্স name:

```text
PrescriptionBuilder
```

## Facade signature

```text
one high-level service class
+ caller uses simple methods
+ class coordinates several lower-level components
```

Mediবাক্স name:

```text
MedicalRecordFacade
```

---

# 22. Design-document alignment

The moderate UML class-diagram specification explicitly models the Strategy and Observer patterns.

## Strategy in the UML

The UML specifies:

```text
AIProviderStrategy
OpenRouterStrategy
HuggingFaceStrategy
ChatbotService
```

and shows:

```text
OpenRouterStrategy implements AIProviderStrategy
HuggingFaceStrategy implements AIProviderStrategy
ChatbotService aggregates/uses AIProviderStrategy
ChatbotService depends on Patient to retrieve records
```

## Observer in the UML

The UML specifies:

```text
Observer
UserNotificationObserver
ApprovalService
```

and shows:

```text
UserNotificationObserver implements Observer
ApprovalService aggregates a list of Observers
ApprovalService reviews MedicineSubmission
ApprovalService verifies Doctor
ApprovalService's decision is made by Admin
```

The UML intentionally stays moderate in size, so it does not add every backend implementation/service class. The remaining four required patterns are represented in the backend source and pattern regression tests.

---

# 23. Final pattern checklist

## Strategy

- [x] Abstract/common strategy
- [x] Multiple concrete strategies
- [x] Context object
- [x] Delegation to selected strategy
- [x] Runtime switching method
- [x] Regression test

## Observer

- [x] Observer abstraction
- [x] Concrete observer
- [x] Subject/publisher
- [x] Observer collection
- [x] Attach
- [x] Detach
- [x] Notify
- [x] Actual approval-event usage
- [x] Regression test

## Factory

- [x] Creator abstraction
- [x] Concrete role creators
- [x] Shared creation algorithm
- [x] Central factory entry point
- [x] Registry-based creator selection
- [x] No if/else/match in factory module
- [x] Patient, doctor, admin support
- [x] Atomic creation
- [x] Regression tests

## Proxy

- [x] Proxy wraps real service
- [x] Access/account check
- [x] Identity check
- [x] Input validation
- [x] Rate limit
- [x] Forward valid request
- [x] Block invalid request before real service
- [x] Regression tests

## Builder

- [x] Builder object
- [x] Step-by-step methods
- [x] Fluent returns
- [x] Optional medicines
- [x] Optional tests
- [x] Optional images
- [x] Validation
- [x] Atomic build
- [x] Final product returned
- [x] Regression test

## Facade

- [x] Simple high-level API
- [x] Patient ownership scoping
- [x] Builder coordination
- [x] File validation
- [x] File storage
- [x] Cleanup on failure
- [x] Patient prescription query
- [x] Search filters
- [x] Regression test

---

# 24. Final conclusion

The six patterns are not decorative classes added only for grading. Each one is attached to a concrete backend responsibility:

```text
Strategy -> interchangeable external AI behavior
Observer -> approval-event notification
Factory  -> role-based account construction
Proxy    -> protected chatbot access
Builder  -> complex prescription construction
Facade   -> simplified medical-record workflows
```

Together they split a large Django backend into smaller responsibilities while preserving a clear request flow:

```text
views -> application pattern layer -> models/external services
```

For viva purposes, the most important thing is not merely memorizing the pattern definitions. Be able to answer four questions for every pattern:

1. **What problem did we have?**
2. **Which class plays which pattern role?**
3. **What exact method call demonstrates the pattern?**
4. **What would become harder if we removed the pattern?**

If those four points are clear, you can explain the implementation rather than only reciting definitions.
