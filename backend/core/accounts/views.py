from datetime import date, datetime

from django.contrib.auth.hashers import check_password
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.accounts.factories import AccountFactory
from core.decorators import login_required
from core.http import fail, ok, read_payload
from core.models import Admin, Client, Doctor, Patient
from core.serializers import client_dict, doctor_dict


def _required(data, *fields):
    missing = [name for name in fields if not str(data.get(name, "")).strip()]
    if missing:
        raise ValueError("Missing required fields: " + ", ".join(missing))


def _optional_date(value, field_name: str):
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.") from exc


@csrf_exempt
@require_POST
def register_patient(request):
    try:
        data = read_payload(request)
        _required(data, "full_name", "email", "password")
        if "date_of_birth" in data:
            data["date_of_birth"] = _optional_date(data.get("date_of_birth"), "date_of_birth")
            if data["date_of_birth"] and data["date_of_birth"] > date.today():
                raise ValueError("date_of_birth cannot be in the future.")
        
        # Access through the Singleton instance getter
        client, patient = AccountFactory.get_instance().create_account("patient", **data)
        
        return ok(
            {"client": client_dict(client), "role": "patient", "p_id": patient.p_id},
            201,
        )
    except (ValueError, KeyError) as exc:
        return fail(str(exc), 400)
    except IntegrityError:
        return fail("The email is already registered.", 409)


@csrf_exempt
@require_POST
def register_doctor(request):
    try:
        data = read_payload(request)
        _required(data, "full_name", "email", "password", "licence_number")
        
        # Access through the Singleton instance getter
        client, doctor = AccountFactory.get_instance().create_account("doctor", **data)
        
        return ok(
            {"client": client_dict(client), "role": "doctor", "doctor": doctor_dict(doctor)},
            201,
        )
    except (ValueError, KeyError) as exc:
        return fail(str(exc), 400)
    except IntegrityError:
        return fail("The email or licence number is already registered.", 409)


@csrf_exempt
@require_POST
def login(request):
    try:
        data = read_payload(request)
        _required(data, "email", "password")
        client = Client.objects.get(email=data["email"].strip().lower())
    except ValueError as exc:
        return fail(str(exc), 400)
    except Client.DoesNotExist:
        return fail("Invalid email or password.", 401)

    if client.account_status.lower() != "active":
        return fail("This account is not active.", 403)
    if not check_password(data["password"], client.password_hash):
        return fail("Invalid email or password.", 401)

    role = None
    role_id = None
    try:
        admin = Admin.objects.get(user=client)
        role, role_id = "admin", admin.a_id
    except Admin.DoesNotExist:
        try:
            doctor = Doctor.objects.get(user=client)
            verification_status = (doctor.verification_status or "Pending").strip().title()
            if verification_status != "Approved":
                if verification_status == "Rejected":
                    return fail(
                        "Doctor registration was rejected by an administrator.",
                        403,
                        details={"verification_status": verification_status},
                    )
                return fail(
                    "Doctor account is awaiting administrator approval.",
                    403,
                    details={"verification_status": verification_status},
                )
            role, role_id = "doctor", doctor.d_id
        except Doctor.DoesNotExist:
            try:
                patient = Patient.objects.get(user=client)
                role, role_id = "patient", patient.p_id
            except Patient.DoesNotExist:
                return fail("Account has no role record.", 500)

    request.session.cycle_key()
    request.session["client_id"] = client.user_id
    request.session["role"] = role
    request.session["role_id"] = role_id
    return ok({"client": client_dict(client), "role": role, "role_id": role_id})


@csrf_exempt
@require_POST
def logout(request):
    request.session.flush()
    return ok({"message": "Logged out."})


def _profile_payload(request):
    data = {"client": client_dict(request.client), "role": request.role}
    if request.role == "patient":
        data["patient"] = {
            "p_id": request.patient.p_id,
            "date_of_birth": request.patient.date_of_birth.isoformat()
            if request.patient.date_of_birth
            else None,
            "blood_group": request.patient.blood_group,
            "address": request.patient.address,
        }
    elif request.role == "doctor":
        data["doctor"] = doctor_dict(request.doctor)
    else:
        data["admin"] = {"a_id": request.admin.a_id}
    return data


@require_GET
@login_required
def profile(request):
    return ok(_profile_payload(request))


@csrf_exempt
@require_POST
@login_required
def update_profile(request):
    try:
        data = read_payload(request)
        for field in ("full_name", "phone"):
            if field in data:
                setattr(request.client, field, (data.get(field) or "").strip() or None)
        if not request.client.full_name:
            return fail("full_name cannot be empty.", 400)
        request.client.save(update_fields=["full_name", "phone"])

        if request.role == "patient":
            if "date_of_birth" in data:
                parsed_dob = _optional_date(data.get("date_of_birth"), "date_of_birth")
                if parsed_dob and parsed_dob > date.today():
                    raise ValueError("date_of_birth cannot be in the future.")
                request.patient.date_of_birth = parsed_dob
            for field in ("blood_group", "address"):
                if field in data:
                    setattr(request.patient, field, data.get(field) or None)
            request.patient.save()
        elif request.role == "doctor":
            for field in ("degree", "field_of_expertise", "workplace"):
                if field in data:
                    setattr(request.doctor, field, (data.get(field) or "").strip() or None)
            request.doctor.save()
        return ok(_profile_payload(request))
    except ValueError as exc:
        return fail(str(exc), 400)