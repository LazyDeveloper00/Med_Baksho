from pathlib import Path

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.approvals.observer import UserNotificationObserver
from core.approvals.services import ApprovalService
from core.decorators import login_required, role_required
from core.http import fail, ok, read_payload
from core.models import Admin, Client, Doctor, MedicineBrand, MedicineSubmission, MedicineType, Patient
from core.serializers import doctor_dict, submission_dict


def _service():
    return ApprovalService([UserNotificationObserver()])


@require_GET
@role_required("admin")
def pending_doctors(request):
    queryset = Doctor.objects.select_related("user").filter(verification_status="Pending")
    return ok([doctor_dict(item) for item in queryset.order_by("d_id")])


@csrf_exempt
@require_POST
@role_required("admin")
def approve_doctor(request, doctor_id: int):
    try:
        doctor = Doctor.objects.select_related("user").get(d_id=doctor_id)
        data = read_payload(request)
        doctor = _service().approve_doctor(
            request.admin, doctor, comments=(data.get("comments") or "").strip()
        )
        return ok(doctor_dict(doctor))
    except Doctor.DoesNotExist:
        return fail("Doctor not found.", 404)
    except ValueError as exc:
        return fail(str(exc), 400)


@csrf_exempt
@require_POST
@role_required("admin")
def reject_doctor(request, doctor_id: int):
    try:
        doctor = Doctor.objects.select_related("user").get(d_id=doctor_id)
        data = read_payload(request)
        doctor = _service().reject_doctor(
            request.admin, doctor, comments=(data.get("comments") or "").strip()
        )
        return ok(doctor_dict(doctor))
    except Doctor.DoesNotExist:
        return fail("Doctor not found.", 404)
    except ValueError as exc:
        return fail(str(exc), 400)


@require_GET
@role_required("admin")
def pending_medicines(request):
    queryset = MedicineSubmission.objects.select_related("patient__user").filter(status="Pending")
    return ok([submission_dict(item) for item in queryset.order_by("submitted_at")])


@csrf_exempt
@require_POST
@role_required("admin")
def approve_medicine(request, submission_id: int):
    try:
        submission = MedicineSubmission.objects.select_related("patient__user").get(
            submission_id=submission_id
        )
        data = read_payload(request)
        if not data.get("med_type_id"):
            return fail("med_type_id is required by the current SQL schema.", 400)
        medicine = _service().approve_medicine(
            request.admin,
            submission,
            med_type_id=int(data["med_type_id"]),
            brand_id=int(data["brand_id"]) if data.get("brand_id") else None,
            brand_name=(data.get("brand_name") or "").strip() or None,
            comments=(data.get("comments") or "").strip(),
        )
        return ok(
            {
                "submission": submission_dict(
                    MedicineSubmission.objects.select_related("patient__user").get(
                        submission_id=submission_id
                    )
                ),
                "medicine": {
                    "medicine_id": medicine.medicine_id,
                    "medicine_name": medicine.medicine_name,
                },
            }
        )
    except MedicineSubmission.DoesNotExist:
        return fail("Medicine submission not found.", 404)
    except MedicineType.DoesNotExist:
        return fail("Medicine type not found.", 404)
    except MedicineBrand.DoesNotExist:
        return fail("Medicine brand not found.", 404)
    except (ValueError, TypeError) as exc:
        return fail(str(exc), 400)


@csrf_exempt
@require_POST
@role_required("admin")
def reject_medicine(request, submission_id: int):
    try:
        submission = MedicineSubmission.objects.select_related("patient__user").get(
            submission_id=submission_id
        )
        data = read_payload(request)
        submission = _service().reject_medicine(
            request.admin,
            submission,
            comments=(data.get("comments") or "").strip(),
        )
        return ok(submission_dict(submission))
    except MedicineSubmission.DoesNotExist:
        return fail("Medicine submission not found.", 404)
    except ValueError as exc:
        return fail(str(exc), 400)


@require_GET
@role_required("admin")
def users(request):
    results = []
    for client in Client.objects.all().order_by("user_id"):
        role = "unassigned"
        if Admin.objects.filter(user=client).exists():
            role = "admin"
        elif Doctor.objects.filter(user=client).exists():
            role = "doctor"
        elif Patient.objects.filter(user=client).exists():
            role = "patient"
        results.append(
            {
                "user_id": client.user_id,
                "full_name": client.full_name,
                "email": client.email,
                "phone": client.phone,
                "account_status": client.account_status,
                "role": role,
            }
        )
    return ok(results)


@csrf_exempt
@require_POST
@role_required("admin")
def set_user_status(request, user_id: int):
    try:
        if request.client.user_id == user_id:
            return fail("An administrator cannot suspend their own active session.", 400)
        data = read_payload(request)
        status = str(data.get("account_status", "")).strip().title()
        if status not in {"Active", "Suspended"}:
            return fail("account_status must be Active or Suspended.", 400)
        client = Client.objects.get(user_id=user_id)
        client.account_status = status
        client.save(update_fields=["account_status"])
        return ok({"user_id": user_id, "account_status": status})
    except Client.DoesNotExist:
        return fail("User account not found.", 404)


@require_GET
@login_required
def notifications(request):
    events = UserNotificationObserver().read_for_user(request.client.user_id)
    return ok(events)


@require_GET
@role_required("admin")
def activity(request):
    path = Path(settings.LOG_DIR) / "medibaksho.log"
    if not path.exists():
        return ok([])
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return ok(lines[-200:][::-1])
