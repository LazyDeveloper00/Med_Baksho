# Mediবাক্স Django Backend

This backend is mapped directly to the corrected 19-table MySQL schema. The Django models use the existing lowercase table names and do not create, rename, or delete project tables.

## Design patterns implemented

1. Strategy — switch between OpenRouter and Hugging Face chatbot providers.
2. Observer — notify a doctor or patient when an approval decision is made.
3. Factory — create Patient, Doctor, or Admin accounts through one account-creation interface.
4. Builder — construct a prescription containing optional medicine, test, and PNG-image records.
5. Facade — expose simple medical-record operations while hiding builder, validation, storage, and transaction details.
6. Proxy — validate access and input before allowing a patient to call the external AI chatbot.

See `DESIGN_PATTERNS.md` for the exact files and class names.

## Important database rule

Do not run `makemigrations` for the `core` app. Its models are `managed = False` because Aritra's/corrected SQL file is the database source of truth.

Django signed-cookie sessions are used, so the backend does not add a `django_session` table. This keeps the project database at the same 19 tables.

## Windows setup

Open PowerShell in:

```text
D:\NSU\Summer2026_Semester8\CSE327 7\Medibaksho\backend
```

Run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Fill the actual Aiven/MySQL values in `.env`.

The corrected schema is included at `database/medbaksho_corrected.sql`. Import it only into an empty/test database or after backing up existing data, because the script drops and recreates all 19 project tables.

Check the project and run it:

```powershell
py manage.py check
py manage.py create_admin --name "System Admin" --email "admin@example.com" --password "ChangeMe123!"
py manage.py runserver
```

Do not run `py manage.py migrate` for this database design.

## Main routes

```text
GET    /api/health/
POST   /api/accounts/register/patient/
POST   /api/accounts/register/doctor/
POST   /api/accounts/login/
POST   /api/accounts/logout/
GET    /api/accounts/profile/
POST   /api/accounts/profile/update/

GET    /api/master-data/
POST   /api/master-data/<entity>/create/
POST   /api/master-data/<entity>/<id>/active/
GET    /api/doctors/availability/
POST   /api/doctors/availability/create/
POST   /api/doctors/availability/<id>/update/
POST   /api/doctors/availability/<id>/deactivate/

GET    /api/records/diseases/
POST   /api/records/diseases/create/
GET    /api/records/prescriptions/
POST   /api/records/prescriptions/create/
GET    /api/records/prescriptions/<id>/
GET    /api/records/search/?disease_id=&medicine_id=&test_id=&facility_id=
POST   /api/records/medicine-submissions/create/
GET    /api/records/medicine-submissions/

GET    /api/approvals/users/
POST   /api/approvals/users/<id>/status/
GET    /api/approvals/doctors/pending/
POST   /api/approvals/doctors/<id>/approve/
POST   /api/approvals/doctors/<id>/reject/
GET    /api/approvals/medicines/pending/
POST   /api/approvals/medicines/<id>/approve/
POST   /api/approvals/medicines/<id>/reject/
GET    /api/approvals/notifications/
GET    /api/approvals/activity/

POST   /api/chatbot/ask/
```

## Request format notes

Most POST endpoints accept JSON. Prescription creation can also accept `multipart/form-data` with a PNG file under the key `image`; send `medicines` and `tests` as JSON arrays encoded as strings.

Medicine approval requires `med_type_id` because the SQL `medicine.med_type_id` field is mandatory. It accepts either an existing `brand_id` or a `brand_name`.

## Quick login example

```powershell
$body = @{
  email = "patient@example.com"
  password = "Patient123!"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/accounts/login/" `
  -ContentType "application/json" `
  -Body $body `
  -SessionVariable session
```

Use `-WebSession $session` on later requests so the signed session cookie is preserved.

## Regression testing

The final package includes **68 offline regression tests** covering the pattern contracts (including the current `AccountFactory` Singleton behavior), request/validation helpers, chatbot provider contracts with mocked HTTP, approval/observer workflows, Builder/Facade behavior, forms, serializers, important URL routes, referenced templates/static files, and the 19-table SQL schema structure. The suite does not write to the shared team database and does not call real AI APIs.

Fastest Windows option:

```powershell
RUN_REGRESSION_TESTS.bat
```

Or run manually:

```powershell
py manage.py check
py -m unittest discover -s tests -v
```

Expected result: `Ran 68 tests ... OK`. For destructive/database-write regression testing, use a separate test database loaded from the corrected SQL file. Never run destructive tests against the shared team database.
