# Mediবাক্স Project Update 1

**Date:** 3 August 2026  
**Project:** CSE327 - Mediবাক্স  
**Current overall estimate:** approximately 55% complete, approximately 45% still left  
**Current stage:** backend API, database connection, and initial verification are working; the user-facing frontend and complete end-to-end integration are not finished.

## 1. Work completed so far

### 1.1 Project and backend setup

- The Django backend was placed at:

  `D:\NSU\Summer2026_Semester8\CSE327 7\Medibaksho\backend`

- A Python virtual environment named `.venv` was created and activated.
- Python 3.14.0 is being used successfully.
- The required packages were installed from `requirements.txt`:
  - Django 5.2.16
  - PyMySQL 1.2.0
  - python-dotenv 1.2.2
  - requests 2.34.2
- `python manage.py check` passed with no system-check errors.
- The Django development server runs on port 5000.
- `GET /api/health/` returns HTTP 200 and confirms that the database is connected.

### 1.2 Database integration

- The backend is connected successfully to the shared Aiven MySQL database.
- The project uses the corrected 19-table schema as the source of truth.
- Django models use `managed = False`, so Django does not create, rename, or delete the project tables.
- Signed-cookie sessions are used, preventing Django from adding a twentieth `django_session` table.
- All 19 tables were confirmed from Django:
  1. `admin`
  2. `client`
  3. `disease`
  4. `doctor`
  5. `doctoravailability`
  6. `medicalfacility`
  7. `medicalfacilitytype`
  8. `medicaltest`
  9. `medicine`
  10. `medicinebrand`
  11. `medicinesubmission`
  12. `medicinetype`
  13. `patient`
  14. `patientdisease`
  15. `prescription`
  16. `prescriptionimage`
  17. `prescriptionmedicine`
  18. `prescriptiontest`
  19. `testcategory`

- Seed/master data was confirmed in the live database:
  - 90 diseases
  - 4 medical-facility types
  - 50 medical facilities
  - 6 medicine brands
  - 5 medicine types
  - 67 medicines
  - 6 test categories
  - 15 medical tests
- Before the first administrator was created, patient and doctor records were empty.
- The first administrator account was created successfully.
- Administrator login through the API succeeded.
- Authenticated administrator profile retrieval succeeded.

### 1.3 Backend modules and API functions

The backend currently contains working modules for:

- Account registration, login, logout, profile view, and profile update
- Patient disease records
- Prescription creation, listing, detail view, and search
- Prescription medicine, test, and PNG-image records
- Patient medicine submissions
- Doctor availability and visiting fees
- Administrator doctor approval and rejection
- Administrator medicine approval and rejection
- User suspension and reactivation
- Master-data retrieval and creation
- Master-data activation/deactivation for supported entities
- User notifications stored in `logs/notifications.jsonl`
- Request/activity auditing stored in `logs/medibaksho.log`
- AI chatbot endpoint structure

### 1.4 Six design patterns implemented in the backend

All six patterns are implemented in Python inside the backend. No pattern is implemented in HTML or CSS.

1. **Strategy Pattern**
   - `AIProviderStrategy`
   - `HuggingFaceStrategy`
   - `OpenRouterStrategy`
   - `ChatbotService`
   - Purpose: switch the chatbot provider without changing patient-record logic.

2. **Observer Pattern**
   - `Observer`
   - `UserNotificationObserver`
   - `ApprovalService`
   - Purpose: notify doctors and patients after approval or rejection.

3. **Factory Method Pattern**
   - `AccountCreator`
   - `PatientAccountCreator`
   - `DoctorAccountCreator`
   - `AdminAccountCreator`
   - `AccountFactory`
   - Purpose: create the shared `client` row and the correct role row.
   - The Factory implementation contains no `if`, `elif`, `else`, ternary, or `match` selection.

4. **Builder Pattern**
   - `PrescriptionBuilder`
   - Purpose: construct a prescription and its optional medicine, test, and image child records.

5. **Facade Pattern**
   - `MedicalRecordFacade`
   - Purpose: hide ownership checks, PNG validation/storage, Builder usage, transactions, and search query details.

6. **Proxy Pattern**
   - `ChatbotProxy`
   - Purpose: check account status, patient ownership, question length, empty input, and request rate before calling the AI provider.

### 1.5 Regression tests completed

The following six tests passed:

- Factory module contains no conditional branch nodes.
- Factory registry contains patient, doctor, and admin creators.
- Observer attach, detach, and notification behavior works.
- Proxy blocks an empty question.
- Proxy forwards a valid question.
- Strategy provider can be switched.

Test result:

`Ran 6 tests ... OK`

### 1.6 Current Git/GitHub work

- The `FarhanRafid` branch was cloned locally from:

  `https://github.com/LazyDeveloper00/Med_Baksho`

- The backend folder was copied into the cloned repository.
- `.env`, `.venv`, Python cache files, log files, and uploaded media are excluded by `.gitignore`.
- The backend files were staged with Git.
- The first commit attempt failed because Git user identity was not configured.
- Git username/email configuration instructions were provided.
- A successful commit and push have not yet been confirmed in this conversation. The remaining commands are:

```powershell
git commit -m "Add MediBaksho Django backend with six design patterns"
git push origin FarhanRafid
```

## 2. Current backend routes

### Accounts

- `POST /api/accounts/register/patient/`
- `POST /api/accounts/register/doctor/`
- `POST /api/accounts/login/`
- `POST /api/accounts/logout/`
- `GET /api/accounts/profile/`
- `POST /api/accounts/profile/update/`

### Master data

- `GET /api/master-data/`
- `POST /api/master-data/<entity>/create/`
- `POST /api/master-data/<entity>/<id>/active/`

### Doctor availability

- `GET /api/doctors/availability/`
- `POST /api/doctors/availability/create/`
- `POST /api/doctors/availability/<id>/update/`
- `POST /api/doctors/availability/<id>/deactivate/`

### Patient records

- `GET /api/records/diseases/`
- `POST /api/records/diseases/create/`
- `GET /api/records/prescriptions/`
- `POST /api/records/prescriptions/create/`
- `GET /api/records/prescriptions/<id>/`
- `GET /api/records/search/`
- `POST /api/records/medicine-submissions/create/`
- `GET /api/records/medicine-submissions/`

### Administrator approvals

- `GET /api/approvals/users/`
- `POST /api/approvals/users/<id>/status/`
- `GET /api/approvals/doctors/pending/`
- `POST /api/approvals/doctors/<id>/approve/`
- `POST /api/approvals/doctors/<id>/reject/`
- `GET /api/approvals/medicines/pending/`
- `POST /api/approvals/medicines/<id>/approve/`
- `POST /api/approvals/medicines/<id>/reject/`
- `GET /api/approvals/notifications/`
- `GET /api/approvals/activity/`

### Chatbot

- `POST /api/chatbot/ask/`

## 3. Work still left - mandatory for the final project

### 3.1 Complete frontend

No HTML/CSS frontend currently exists. The following must be created:

- Landing page
- Patient registration page
- Doctor registration page
- Login page
- Role-based navigation
- Patient dashboard
- Doctor dashboard
- Administrator dashboard
- Profile pages
- Disease-record pages
- Prescription creation, history, search, and detail pages
- Medicine-submission pages
- Doctor-availability pages
- Administrator approval pages
- User-management pages
- Master-data management pages
- Activity-log page
- Notification page
- AI chatbot page
- Error pages
- Responsive CSS

### 3.2 Django web-integration layer

HTML and CSS alone cannot render database data or call backend classes. Thin Django page views and forms must be added.

Required integration files:

- `core/web/urls.py`
- `core/web/views.py`
- `core/web/forms.py`
- `core/web/helpers.py`
- `templates/`
- `static/css/`

These web views must only connect forms/templates to existing backend services and models. They must not implement new design patterns.

### 3.3 Hugging Face chatbot completion

The chatbot structure exists, but the following are still required:

- Create or obtain a valid Hugging Face access token.
- Add the token to `.env` as `HUGGINGFACE_API_KEY`.
- Confirm a working model and inference endpoint.
- Test an actual patient question with real patient records.
- Confirm provider failure handling.
- Add the chatbot HTML page and disclaimer.
- Confirm the 500-character limit and five-requests-per-minute limit in the UI.
- Confirm that no API key appears in HTML, Git, screenshots, or reports.

### 3.4 Important backend gaps to fix before final submission

1. **Doctor approval gate:** a pending or rejected doctor can currently log in because login only checks `client.account_status`. Doctor login or doctor-only operations must also require `verification_status == "Approved"`.
2. **Doctor availability management list:** the public availability endpoint only returns future, active slots for approved doctors. A separate authenticated endpoint/page is needed so a doctor can see their own active and inactive slots for editing.
3. **Availability validation:** ensure the date is not in the past, start time is earlier than end time, and visiting fee is not negative.
4. **Disease record management:** only create/list exists. Add update and deactivate/delete behavior if the final interpretation of "manage disease records" requires it.
5. **Prescription updates/outcomes:** no endpoint currently updates medicine course completion, side effects, effectiveness, test completion, test date, or result summary after creation.
6. **Prescription correction/deletion:** no edit or delete endpoint exists. Decide whether the project requires them; at minimum, add a safe correction method if demonstration requires it.
7. **Multiple images:** the current creation endpoint accepts one PNG file per request even though the schema supports multiple image rows.
8. **Master-data editing:** current backend supports create and activation toggles, but not renaming/editing existing records.
9. **Dashboard summaries:** no dedicated summary endpoint exists. Thin Django views must calculate counts from existing models or a new summary endpoint must be added.
10. **Password functions:** no password-change or password-reset flow exists.
11. **Production error pages:** JSON errors exist, but browser-friendly 400/403/404/500 pages do not.
12. **Pagination:** large lists currently return all matching records.

### 3.5 Full end-to-end testing

The following workflows still need browser-based testing:

- Patient registration -> login -> dashboard
- Doctor registration -> pending state -> admin approval -> doctor login
- Profile updates for patient and doctor
- Add patient disease
- Add prescription with medicine/test/PNG image
- View prescription history and details
- Search by disease, medicine, test, and medical facility
- Submit new medicine -> admin approval/rejection -> patient notification
- Doctor availability create/update/deactivate
- User suspension -> blocked login/session
- Chatbot question -> patient context -> Hugging Face response
- Unauthorized access for every role
- Invalid input and duplicate data
- Database failure and AI-provider failure

### 3.6 Frontend quality and security testing

- All forms must use Django CSRF protection.
- Signed session cookies must remain enabled.
- The frontend must never connect directly to MySQL.
- The frontend must never contain API keys, passwords, or database credentials.
- `.env` must remain untracked.
- Uploaded files must be limited to valid PNG files and the configured maximum size.
- Each user must only see records allowed for their role.
- Pages must remain usable on desktop and mobile widths.
- No JavaScript or frontend design pattern should be added unless the faculty explicitly changes the rule.

### 3.7 Documentation and submission work

- Commit and push the backend to the `FarhanRafid` branch.
- Merge team frontend work safely.
- Update README with final browser setup instructions.
- Add screenshots of every major workflow.
- Add regression-test evidence.
- Add a design-pattern explanation with code locations.
- Ensure the UML, ERD, use-case, and sequence diagrams still match the final code.
- Prepare the final report and presentation.
- Confirm the GitHub repository link in the report.
- Make a clean final ZIP without `.env`, `.venv`, caches, logs, or private credentials.

## 4. Security actions that should be done soon

- Regenerate the Aiven database password because it was pasted into chat/terminal history.
- Change the demonstration administrator password because it was also displayed in terminal commands.
- Keep only placeholder credentials in `.env.example`.
- Never commit the real `.env` file.

## 5. Current conclusion

The backend installation and live database setup are working. The six backend design patterns are present and the Factory regression rule is enforced. The live database, all 19 tables, seeded dropdown data, administrator login, profile retrieval, and health endpoint have been verified.

The project is not submission-ready yet. The largest remaining block is the complete server-rendered HTML/CSS frontend and its Django integration. The Hugging Face chatbot must also be configured and tested with a real token, and the listed backend gaps and full workflows must be tested before 16 August 2026.
