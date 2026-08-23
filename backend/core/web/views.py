"""Browser (server-rendered) views.

Every view translates backend success/error results into normal pages and
Django messages. Views call the existing design-pattern implementations
directly (AccountFactory, MedicalRecordFacade/PrescriptionBuilder,
ApprovalService/Observer, ChatbotProxy/Service) instead of making HTTP
requests back into the same process. No pattern logic is duplicated here.
"""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from core.accounts.factories import AccountFactory
from core.approvals.observer import UserNotificationObserver
from core.approvals.services import ApprovalService
from core.chatbot.proxy import ChatbotProxy
from core.chatbot.service import build_chatbot_service
from core.models import (
    Admin,
    Client,
    Disease,
    Doctor,
    DoctorAvailability,
    MedicalFacility,
    MedicalFacilityType,
    MedicalTest,
    Medicine,
    MedicineBrand,
    MedicineSubmission,
    MedicineType,
    Patient,
    PatientDisease,
    Prescription,
    TestCategory,
)
from core.records.facades import MedicalRecordFacade
from core.web.forms import (
    BLOOD_GROUPS,
    AdminProfileForm,
    AvailabilityForm,
    ChatbotForm,
    DiseaseRecordForm,
    DoctorProfileForm,
    DoctorRegistrationForm,
    LoginForm,
    MedicineApprovalForm,
    MedicineSubmissionForm,
    PatientProfileForm,
    PatientRegistrationForm,
)
from core.web.helpers import (
    ROLE_DISPLAY,
    render_403,
    web_login_required,
    web_role_required,
)

logger = logging.getLogger(__name__)

ROW_COUNT = 5  # fixed repeatable medicine/test rows (no JavaScript)


def _approval_service() -> ApprovalService:
    return ApprovalService([UserNotificationObserver()])


def _dashboard_url(role: str) -> str:
    return {
        "patient": "/patient/dashboard/",
        "doctor": "/doctor/dashboard/",
        "admin": "/admin-panel/dashboard/",
    }.get(role, "/")


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------


def home(request):
    return render(request, "public/home.html")


def doctor_availability(request):
    queryset = (
        DoctorAvailability.objects.select_related("doctor__user")
        .filter(
            is_active=True,
            doctor__verification_status="Approved",
            doctor__user__account_status="Active",
            available_date__gte=date.today(),
        )
        .order_by("available_date", "start_time")
    )
    doctor_name = (request.GET.get("doctor") or "").strip()
    expertise = (request.GET.get("expertise") or "").strip()
    on_date = (request.GET.get("date") or "").strip()
    if doctor_name:
        queryset = queryset.filter(doctor__user__full_name__icontains=doctor_name)
    if expertise:
        queryset = queryset.filter(doctor__field_of_expertise__icontains=expertise)
    if on_date:
        queryset = queryset.filter(available_date=on_date)
    return render(
        request,
        "public/doctor_availability.html",
        {"slots": queryset, "filters": {"doctor": doctor_name, "expertise": expertise, "date": on_date}},
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def _resolve_role(client: Client):
    if Admin.objects.filter(user=client).exists():
        return "admin", Admin.objects.get(user=client).a_id
    if Doctor.objects.filter(user=client).exists():
        return "doctor", Doctor.objects.get(user=client).d_id
    if Patient.objects.filter(user=client).exists():
        return "patient", Patient.objects.get(user=client).p_id
    return None, None


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.session.get("client_id"):
        return redirect(_dashboard_url(request.session.get("role", "")))

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        password = form.cleaned_data["password"]
        try:
            client = Client.objects.get(email=email)
        except Client.DoesNotExist:
            messages.error(request, "Invalid email or password.")
            return render(request, "accounts/login.html", {"form": form})

        if client.account_status.lower() != "active":
            messages.error(request, "This account is not active. Please contact an administrator.")
            return render(request, "accounts/login.html", {"form": form})
        if not check_password(password, client.password_hash):
            messages.error(request, "Invalid email or password.")
            return render(request, "accounts/login.html", {"form": form})

        role, role_id = _resolve_role(client)
        if not role:
            messages.error(request, "This account has no role assigned. Contact an administrator.")
            return render(request, "accounts/login.html", {"form": form})

        request.session.cycle_key()
        request.session["client_id"] = client.user_id
        request.session["role"] = role
        request.session["role_id"] = role_id
        request.session["full_name"] = client.full_name

        if role == "doctor":
            doctor = Doctor.objects.get(d_id=role_id)
            if doctor.verification_status == "Pending":
                messages.info(request, "Your doctor account is pending administrator approval.")
            elif doctor.verification_status == "Rejected":
                messages.warning(request, "Your doctor registration was rejected. See notifications for details.")

        messages.success(request, f"Welcome back, {client.full_name}.")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect(_dashboard_url(role))

    return render(request, "accounts/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("/login/")


@require_http_methods(["GET", "POST"])
def register_patient(request):
    form = PatientRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            AccountFactory.create_account(
                "patient",
                password=data["password"],
                full_name=data["full_name"],
                email=data["email"],
                phone=data.get("phone"),
                date_of_birth=data.get("date_of_birth"),
                blood_group=data.get("blood_group"),
                address=data.get("address"),
            )
        except IntegrityError:
            form.add_error("email", "This email is already registered.")
        else:
            messages.success(request, "Account created. Please log in to continue.")
            return redirect("/login/")
    return render(
        request,
        "accounts/register_patient.html",
        {"form": form, "blood_groups": BLOOD_GROUPS},
    )


@require_http_methods(["GET", "POST"])
def register_doctor(request):
    form = DoctorRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            AccountFactory.create_account(
                "doctor",
                password=data["password"],
                full_name=data["full_name"],
                email=data["email"],
                phone=data.get("phone"),
                licence_number=data["licence_number"],
                degree=data.get("degree"),
                field_of_expertise=data.get("field_of_expertise"),
                workplace=data.get("workplace"),
            )
        except IntegrityError:
            form.add_error(None, "The email or licence number is already registered.")
        else:
            messages.success(
                request,
                "Registration submitted. Administrator approval is required before "
                "doctor features are available.",
            )
            return redirect("/login/")
    return render(request, "accounts/register_doctor.html", {"form": form})


# ---------------------------------------------------------------------------
# Common (all logged-in roles)
# ---------------------------------------------------------------------------


@web_login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    role = request.role
    client = request.client

    if role == "patient":
        form_class, template = PatientProfileForm, "accounts/profile.html"
        initial = {
            "full_name": client.full_name,
            "phone": client.phone,
            "date_of_birth": request.patient.date_of_birth,
            "blood_group": request.patient.blood_group or "",
            "address": request.patient.address,
        }
    elif role == "doctor":
        form_class, template = DoctorProfileForm, "accounts/profile.html"
        initial = {
            "full_name": client.full_name,
            "phone": client.phone,
            "degree": request.doctor.degree,
            "field_of_expertise": request.doctor.field_of_expertise,
            "workplace": request.doctor.workplace,
        }
    else:
        form_class, template = AdminProfileForm, "accounts/profile.html"
        initial = {"full_name": client.full_name, "phone": client.phone}

    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            client.full_name = data["full_name"].strip()
            client.phone = (data.get("phone") or "").strip() or None
            client.save(update_fields=["full_name", "phone"])
            request.session["full_name"] = client.full_name
            if role == "patient":
                request.patient.date_of_birth = data.get("date_of_birth") or None
                request.patient.blood_group = (data.get("blood_group") or "").strip() or None
                request.patient.address = (data.get("address") or "").strip() or None
                request.patient.save()
            elif role == "doctor":
                request.doctor.degree = (data.get("degree") or "").strip() or None
                request.doctor.field_of_expertise = (data.get("field_of_expertise") or "").strip() or None
                request.doctor.workplace = (data.get("workplace") or "").strip() or None
                request.doctor.save()
            messages.success(request, "Profile updated.")
            return redirect("/profile/")
    else:
        form = form_class(initial=initial)

    context = {
        "form": form,
        "role": role,
        "role_display": ROLE_DISPLAY.get(role, ""),
        "client": client,
        "doctor": getattr(request, "doctor", None),
        "patient": getattr(request, "patient", None),
    }
    return render(request, template, context)


@web_login_required
def notifications_view(request):
    events = UserNotificationObserver().read_for_user(request.client.user_id)
    return render(request, "common/notifications.html", {"events": events})


# ---------------------------------------------------------------------------
# Patient pages
# ---------------------------------------------------------------------------


@web_role_required("patient")
def patient_dashboard(request):
    patient = request.patient
    prescriptions = MedicalRecordFacade.patient_prescriptions(patient)
    diseases = PatientDisease.objects.select_related("disease").filter(patient=patient)
    notifications = UserNotificationObserver().read_for_user(patient.user_id)
    context = {
        "counts": {
            "diseases": diseases.count(),
            "prescriptions": prescriptions.count(),
            "pending_submissions": MedicineSubmission.objects.filter(
                patient=patient, status="Pending"
            ).count(),
            "notifications": len(notifications),
        },
        "recent_prescriptions": prescriptions.order_by("-prescription_date", "-prescription_id")[:5],
        "recent_diseases": diseases.order_by("-patient_disease_id")[:5],
    }
    return render(request, "patient/dashboard.html", context)


@web_role_required("patient")
def patient_diseases(request):
    items = (
        PatientDisease.objects.select_related("disease")
        .filter(patient=request.patient)
        .order_by("-patient_disease_id")
    )
    return render(request, "patient/diseases_list.html", {"diseases": items})


@web_role_required("patient")
@require_http_methods(["GET", "POST"])
def patient_disease_add(request):
    form = DiseaseRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            disease = Disease.objects.get(disease_id=data["disease_id"], is_active=True)
        except Disease.DoesNotExist:
            messages.error(request, "The selected disease was not found or is inactive.")
        else:
            PatientDisease.objects.create(
                patient=request.patient,
                disease=disease,
                diagnosed_date=data.get("diagnosed_date") or None,
                current_status=data.get("current_status") or "Active",
                custom_disease_name=(data.get("custom_disease_name") or "").strip() or None,
                notes=(data.get("notes") or "").strip() or None,
            )
            messages.success(request, "Disease record added.")
            return redirect("/patient/diseases/")
    return render(request, "patient/disease_form.html", {"form": form})


@web_role_required("patient")
def patient_prescriptions(request):
    items = MedicalRecordFacade.patient_prescriptions(request.patient).order_by(
        "-prescription_date", "-prescription_id"
    )
    return render(request, "patient/prescriptions_list.html", {"prescriptions": items})


def _prescription_dropdowns():
    return {
        "medicines": Medicine.objects.select_related("med_brand", "med_type")
        .filter(is_active=True)
        .order_by("medicine_name"),
        "tests": MedicalTest.objects.select_related("category").filter(is_active=True).order_by("test_name"),
        "facilities": MedicalFacility.objects.filter(is_active=True).order_by("facility_name"),
    }


def _collect_rows(post, prefix, key_field, fields):
    """Turn fixed repeatable POST rows into a list of dicts, ignoring blank rows."""
    rows = []
    for index in range(ROW_COUNT):
        key_value = (post.get(f"{prefix}-{index}-{key_field}") or "").strip()
        if not key_value:
            continue
        row = {key_field: key_value}
        for name in fields:
            value = post.get(f"{prefix}-{index}-{name}")
            if name in {"course_completed"}:
                row[name] = bool(value)
            else:
                row[name] = (value or "").strip() or None
        rows.append(row)
    return rows


@web_role_required("patient")
@require_http_methods(["GET", "POST"])
def patient_prescription_add(request):
    dropdowns = _prescription_dropdowns()
    patient_diseases = (
        PatientDisease.objects.select_related("disease")
        .filter(patient=request.patient)
        .order_by("-patient_disease_id")
    )
    context = {
        **dropdowns,
        "patient_diseases": patient_diseases,
        "row_indexes": list(range(ROW_COUNT)),
        "form_data": {},
    }

    if request.method == "POST":
        post = request.POST
        context["form_data"] = post
        medicines = _collect_rows(
            post,
            "medicine",
            "medicine_id",
            ["dosage", "times_per_day", "duration_days", "start_date", "end_date",
             "course_completed", "side_effects", "effectiveness"],
        )
        tests = _collect_rows(
            post,
            "test",
            "test_id",
            ["completion_status", "test_date", "diagnostic_center_name",
             "result_summary", "custom_test_name"],
        )
        base_data = {
            key: (post.get(key) or "").strip() or None
            for key in (
                "facility_id",
                "prescription_date",
                "doctor_name",
                "custom_facility_name",
                "illness_location",
                "advice",
                "additional_notes",
            )
        }
        try:
            patient_disease_id = int(post.get("patient_disease_id") or 0)
            if not patient_disease_id:
                raise ValueError("Select the disease this prescription is for.")
            prescription = MedicalRecordFacade.create_prescription(
                patient=request.patient,
                patient_disease_id=patient_disease_id,
                base_data=base_data,
                medicines=medicines,
                tests=tests,
                uploaded_file=request.FILES.get("image"),
            )
        except PatientDisease.DoesNotExist:
            messages.error(request, "The selected disease record was not found.")
        except (Medicine.DoesNotExist, MedicalTest.DoesNotExist, MedicalFacility.DoesNotExist):
            messages.error(request, "A selected medicine, test, or facility was not found or is inactive.")
        except (ValueError, IntegrityError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Prescription saved.")
            return redirect(f"/patient/prescriptions/{prescription.prescription_id}/")

    return render(request, "patient/prescription_form.html", context)


@web_role_required("patient")
def patient_prescription_detail(request, prescription_id: int):
    try:
        item = MedicalRecordFacade.patient_prescriptions(request.patient).get(
            prescription_id=prescription_id
        )
    except Prescription.DoesNotExist:
        messages.error(request, "Prescription not found.")
        return redirect("/patient/prescriptions/")
    context = {
        "prescription": item,
        "medicines": item.medicine_entries.select_related("medicine__med_brand", "medicine__med_type").all(),
        "tests": item.test_entries.select_related("test").all(),
        "images": item.images.all(),
    }
    return render(request, "patient/prescription_detail.html", context)


@web_role_required("patient")
def patient_search(request):
    results = MedicalRecordFacade.search(
        patient=request.patient,
        disease_id=request.GET.get("disease_id") or None,
        medicine_id=request.GET.get("medicine_id") or None,
        test_id=request.GET.get("test_id") or None,
        facility_id=request.GET.get("facility_id") or None,
    )
    context = {
        "results": results,
        "has_query": any(
            request.GET.get(key) for key in ("disease_id", "medicine_id", "test_id", "facility_id")
        ),
        "diseases": Disease.objects.filter(is_active=True).order_by("disease_name"),
        "medicines": Medicine.objects.filter(is_active=True).order_by("medicine_name"),
        "tests": MedicalTest.objects.filter(is_active=True).order_by("test_name"),
        "facilities": MedicalFacility.objects.filter(is_active=True).order_by("facility_name"),
        "selected": {
            "disease_id": request.GET.get("disease_id", ""),
            "medicine_id": request.GET.get("medicine_id", ""),
            "test_id": request.GET.get("test_id", ""),
            "facility_id": request.GET.get("facility_id", ""),
        },
    }
    return render(request, "patient/records_search.html", context)


@web_role_required("patient")
def patient_medicine_submissions(request):
    items = MedicineSubmission.objects.filter(patient=request.patient).order_by("-submitted_at")
    return render(request, "patient/medicine_submissions.html", {"submissions": items})


@web_role_required("patient")
@require_http_methods(["GET", "POST"])
def patient_medicine_submission_add(request):
    form = MedicineSubmissionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        MedicineSubmission.objects.create(
            patient=request.patient,
            proposed_medicine_name=data["proposed_medicine_name"].strip(),
            med_brand_name=(data.get("med_brand_name") or "").strip() or None,
            proposed_active_ingredient=(data.get("proposed_active_ingredient") or "").strip() or None,
            status="Pending",
        )
        messages.success(request, "Medicine submission sent for administrator review.")
        return redirect("/patient/medicine-submissions/")
    return render(request, "patient/medicine_submission_form.html", {"form": form})


@web_role_required("patient")
@require_http_methods(["GET", "POST"])
def patient_chatbot(request):
    form = ChatbotForm(request.POST or None)
    answer = None
    question = None
    if request.method == "POST" and form.is_valid():
        question = form.cleaned_data["question"]
        try:
            proxy = ChatbotProxy(build_chatbot_service())
            answer = proxy.answer(request.client, request.patient, question)
        except ValueError as exc:
            messages.error(request, str(exc))
        except PermissionError as exc:
            messages.warning(request, str(exc))
        except Exception:
            logger.exception("Chatbot provider request failed")
            messages.error(
                request,
                "The record assistant is temporarily unavailable. Please try again later.",
            )
    return render(
        request,
        "patient/chatbot.html",
        {"form": form, "answer": answer, "question": question},
    )


# ---------------------------------------------------------------------------
# Doctor pages
# ---------------------------------------------------------------------------


@web_role_required("doctor")
def doctor_dashboard(request):
    doctor = request.doctor
    upcoming = DoctorAvailability.objects.filter(
        doctor=doctor, is_active=True, available_date__gte=date.today()
    ).order_by("available_date", "start_time")[:5]
    return render(
        request,
        "doctor/dashboard.html",
        {
            "doctor": doctor,
            "is_approved": doctor.verification_status == "Approved",
            "upcoming": upcoming,
        },
    )


@web_role_required("doctor")
def doctor_profile(request):
    # Reuse the shared profile view for editing.
    return redirect("/profile/")


@web_role_required("doctor")
def doctor_availability_list(request):
    items = DoctorAvailability.objects.filter(doctor=request.doctor).order_by(
        "-available_date", "start_time"
    )
    return render(
        request,
        "doctor/availability_list.html",
        {"slots": items, "is_approved": request.doctor.verification_status == "Approved"},
    )


def _require_approved_doctor(request):
    if request.doctor.verification_status != "Approved":
        messages.warning(request, "Availability management is available after administrator approval.")
        return False
    return True


@web_role_required("doctor")
@require_http_methods(["GET", "POST"])
def doctor_availability_add(request):
    if not _require_approved_doctor(request):
        return redirect("/doctor/availability/")
    form = AvailabilityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            DoctorAvailability.objects.create(
                doctor=request.doctor,
                available_date=data["available_date"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                visiting_fee=data["visiting_fee"],
                is_active=True,
            )
        except IntegrityError:
            messages.error(request, "This availability slot already exists.")
        else:
            messages.success(request, "Availability slot added.")
            return redirect("/doctor/availability/")
    return render(request, "doctor/availability_form.html", {"form": form, "mode": "add"})


@web_role_required("doctor")
@require_http_methods(["GET", "POST"])
def doctor_availability_edit(request, availability_id: int):
    if not _require_approved_doctor(request):
        return redirect("/doctor/availability/")
    try:
        slot = DoctorAvailability.objects.get(availability_id=availability_id, doctor=request.doctor)
    except DoctorAvailability.DoesNotExist:
        messages.error(request, "Availability slot not found.")
        return redirect("/doctor/availability/")

    if request.method == "POST":
        form = AvailabilityForm(request.POST, allow_past=True)
        if form.is_valid():
            data = form.cleaned_data
            slot.available_date = data["available_date"]
            slot.start_time = data["start_time"]
            slot.end_time = data["end_time"]
            slot.visiting_fee = data["visiting_fee"]
            slot.is_active = data.get("is_active", False)
            try:
                slot.save()
            except IntegrityError:
                messages.error(request, "This availability slot conflicts with an existing one.")
            else:
                messages.success(request, "Availability slot updated.")
                return redirect("/doctor/availability/")
    else:
        form = AvailabilityForm(
            allow_past=True,
            initial={
                "available_date": slot.available_date,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "visiting_fee": slot.visiting_fee,
                "is_active": slot.is_active,
            },
        )
    return render(request, "doctor/availability_form.html", {"form": form, "mode": "edit", "slot": slot})


# ---------------------------------------------------------------------------
# Administrator pages
# ---------------------------------------------------------------------------


@web_role_required("admin")
def admin_dashboard(request):
    counts = {
        "users": Client.objects.count(),
        "patients": Patient.objects.count(),
        "doctors": Doctor.objects.count(),
        "pending_doctors": Doctor.objects.filter(verification_status="Pending").count(),
        "pending_medicines": MedicineSubmission.objects.filter(status="Pending").count(),
        "active_medicines": Medicine.objects.filter(is_active=True).count(),
        "diseases": Disease.objects.filter(is_active=True).count(),
        "tests": MedicalTest.objects.filter(is_active=True).count(),
    }
    context = {
        "counts": counts,
        "pending_doctors": Doctor.objects.select_related("user")
        .filter(verification_status="Pending")
        .order_by("d_id")[:5],
        "pending_medicines": MedicineSubmission.objects.select_related("patient__user")
        .filter(status="Pending")
        .order_by("submitted_at")[:5],
    }
    return render(request, "admin/dashboard.html", context)


@web_role_required("admin")
@require_http_methods(["GET", "POST"])
def admin_users(request):
    if request.method == "POST":
        user_id = int(request.POST.get("user_id") or 0)
        status = (request.POST.get("account_status") or "").strip().title()
        if request.client.user_id == user_id:
            messages.error(request, "You cannot suspend your own account.")
        elif status not in {"Active", "Suspended"}:
            messages.error(request, "Status must be Active or Suspended.")
        else:
            try:
                client = Client.objects.get(user_id=user_id)
                client.account_status = status
                client.save(update_fields=["account_status"])
                messages.success(request, f"{client.full_name} is now {status}.")
            except Client.DoesNotExist:
                messages.error(request, "User not found.")
        return redirect("/admin-panel/users/")

    rows = []
    admin_ids = set(Admin.objects.values_list("user_id", flat=True))
    doctor_ids = set(Doctor.objects.values_list("user_id", flat=True))
    patient_ids = set(Patient.objects.values_list("user_id", flat=True))
    for client in Client.objects.order_by("user_id"):
        if client.user_id in admin_ids:
            role = "Administrator"
        elif client.user_id in doctor_ids:
            role = "Doctor"
        elif client.user_id in patient_ids:
            role = "Patient"
        else:
            role = "Unassigned"
        rows.append({"client": client, "role": role, "is_self": client.user_id == request.client.user_id})
    return render(request, "admin/users.html", {"rows": rows})


@web_role_required("admin")
@require_http_methods(["GET", "POST"])
def admin_pending_doctors(request):
    if request.method == "POST":
        doctor_id = int(request.POST.get("doctor_id") or 0)
        decision = request.POST.get("decision")
        comments = (request.POST.get("comments") or "").strip()
        try:
            doctor = Doctor.objects.select_related("user").get(d_id=doctor_id)
        except Doctor.DoesNotExist:
            messages.error(request, "Doctor not found.")
            return redirect("/admin-panel/doctors/pending/")
        service = _approval_service()
        if decision == "approve":
            service.approve_doctor(request.admin, doctor, comments=comments)
            messages.success(request, f"Dr. {doctor.user.full_name} approved.")
        elif decision == "reject":
            service.reject_doctor(request.admin, doctor, comments=comments)
            messages.success(request, f"Dr. {doctor.user.full_name} rejected.")
        else:
            messages.error(request, "Unknown decision.")
        return redirect("/admin-panel/doctors/pending/")

    doctors = Doctor.objects.select_related("user").filter(verification_status="Pending").order_by("d_id")
    return render(request, "admin/pending_doctors.html", {"doctors": doctors})


@web_role_required("admin")
@require_http_methods(["GET", "POST"])
def admin_pending_medicines(request):
    if request.method == "POST":
        submission_id = int(request.POST.get("submission_id") or 0)
        decision = request.POST.get("decision")
        try:
            submission = MedicineSubmission.objects.select_related("patient__user").get(
                submission_id=submission_id
            )
        except MedicineSubmission.DoesNotExist:
            messages.error(request, "Submission not found.")
            return redirect("/admin-panel/medicines/pending/")
        service = _approval_service()
        comments = (request.POST.get("comments") or "").strip()
        if decision == "reject":
            try:
                service.reject_medicine(request.admin, submission, comments=comments)
                messages.success(request, "Medicine submission rejected.")
            except ValueError as exc:
                messages.error(request, str(exc))
        elif decision == "approve":
            form = MedicineApprovalForm(request.POST)
            if not form.is_valid():
                messages.error(request, "A medicine type is required to approve a submission.")
            else:
                data = form.cleaned_data
                try:
                    service.approve_medicine(
                        request.admin,
                        submission,
                        med_type_id=int(data["med_type_id"]),
                        brand_id=int(data["brand_id"]) if data.get("brand_id") else None,
                        brand_name=(data.get("brand_name") or "").strip() or None,
                        comments=(data.get("comments") or "").strip(),
                    )
                    messages.success(request, "Medicine submission approved.")
                except (ValueError, TypeError) as exc:
                    messages.error(request, str(exc))
                except (MedicineType.DoesNotExist, MedicineBrand.DoesNotExist):
                    messages.error(request, "Selected medicine type or brand not found.")
        else:
            messages.error(request, "Unknown decision.")
        return redirect("/admin-panel/medicines/pending/")

    submissions = MedicineSubmission.objects.select_related("patient__user").filter(
        status="Pending"
    ).order_by("submitted_at")
    context = {
        "submissions": submissions,
        "medicine_types": MedicineType.objects.order_by("med_type_name"),
        "brands": MedicineBrand.objects.order_by("brand_name"),
    }
    return render(request, "admin/pending_medicines.html", context)


def _create_master_data(entity, post):
    """Mirror the API master-data create logic for the admin browser page."""
    if entity == "disease":
        Disease.objects.create(disease_name=post["disease_name"].strip(), is_active=True)
    elif entity == "facility-type":
        MedicalFacilityType.objects.create(facility_type_name=post["facility_type_name"].strip())
    elif entity == "facility":
        facility_type = MedicalFacilityType.objects.get(facility_type_id=int(post["facility_type_id"]))
        MedicalFacility.objects.create(
            facility_name=post["facility_name"].strip(), facility_type=facility_type, is_active=True
        )
    elif entity == "medicine-brand":
        MedicineBrand.objects.create(brand_name=post["brand_name"].strip())
    elif entity == "medicine-type":
        MedicineType.objects.create(med_type_name=post["med_type_name"].strip())
    elif entity == "test-category":
        TestCategory.objects.create(category_name=post["category_name"].strip(), is_active=True)
    elif entity == "medical-test":
        category = TestCategory.objects.get(category_id=int(post["category_id"]))
        MedicalTest.objects.create(
            category=category,
            test_name=post["test_name"].strip(),
            description=(post.get("description") or "").strip() or None,
            is_active=True,
        )
    elif entity == "medicine":
        brand = MedicineBrand.objects.get(brand_id=int(post["brand_id"]))
        med_type = MedicineType.objects.get(med_type_id=int(post["med_type_id"]))
        Medicine.objects.create(
            medicine_name=post["medicine_name"].strip(),
            main_active_ingredient=(post.get("main_active_ingredient") or "").strip() or None,
            med_brand=brand,
            med_type=med_type,
            is_active=True,
        )
    else:
        raise ValueError("Unsupported master-data entity.")


TOGGLE_MODELS = {
    "disease": (Disease, "disease_id"),
    "facility": (MedicalFacility, "facility_id"),
    "medicine": (Medicine, "medicine_id"),
    "test-category": (TestCategory, "category_id"),
    "medical-test": (MedicalTest, "test_id"),
}


@web_role_required("admin")
@require_http_methods(["GET", "POST"])
def admin_master_data(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            entity = request.POST.get("entity", "")
            try:
                _create_master_data(entity, request.POST)
                messages.success(request, f"{entity.replace('-', ' ').title()} created.")
            except KeyError as exc:
                messages.error(request, f"Missing required field: {exc.args[0]}")
            except (ValueError, IntegrityError):
                messages.error(request, "Invalid or duplicate record.")
            except (
                MedicalFacilityType.DoesNotExist,
                TestCategory.DoesNotExist,
                MedicineBrand.DoesNotExist,
                MedicineType.DoesNotExist,
            ):
                messages.error(request, "A referenced record was not found.")
        elif action == "toggle":
            entity = request.POST.get("entity", "")
            model_info = TOGGLE_MODELS.get(entity)
            if not model_info:
                messages.error(request, "This entity does not support activation toggling.")
            else:
                model, pk_field = model_info
                value = (request.POST.get("is_active") or "").lower() in {"1", "true", "yes", "on"}
                updated = model.objects.filter(**{pk_field: request.POST.get("object_id")}).update(
                    is_active=value
                )
                if updated:
                    messages.success(request, f"{entity.replace('-', ' ').title()} updated.")
                else:
                    messages.error(request, "Record not found.")
        return redirect("/admin-panel/master-data/")

    context = {
        "diseases": Disease.objects.order_by("disease_name"),
        "facility_types": MedicalFacilityType.objects.order_by("facility_type_name"),
        "facilities": MedicalFacility.objects.select_related("facility_type").order_by("facility_name"),
        "medicine_brands": MedicineBrand.objects.order_by("brand_name"),
        "medicine_types": MedicineType.objects.order_by("med_type_name"),
        "medicines": Medicine.objects.select_related("med_brand", "med_type").order_by("medicine_name"),
        "test_categories": TestCategory.objects.order_by("category_name"),
        "medical_tests": MedicalTest.objects.select_related("category").order_by("test_name"),
    }
    return render(request, "admin/master_data.html", context)


@web_role_required("admin")
def admin_activity(request):
    from pathlib import Path

    from django.conf import settings

    path = Path(settings.LOG_DIR) / "medibaksho.log"
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:][::-1]
    return render(request, "admin/activity.html", {"lines": lines})


# ---------------------------------------------------------------------------
# Error handlers (used when DEBUG is False)
# ---------------------------------------------------------------------------


def error_400(request, exception=None):
    return render(request, "errors/400.html", status=400)


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
