from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.decorators import role_required
from core.http import fail, ok, read_payload
from core.models import DoctorAvailability
from core.serializers import availability_dict


@require_GET
def availability_list(request):
    queryset = DoctorAvailability.objects.select_related("doctor__user").filter(
        is_active=True,
        doctor__verification_status="Approved",
        doctor__user__account_status="Active",
        available_date__gte=date.today(),
    )
    doctor_id = request.GET.get("doctor_id")
    available_date = request.GET.get("date")
    if doctor_id:
        queryset = queryset.filter(doctor_id=doctor_id)
    if available_date:
        queryset = queryset.filter(available_date=available_date)
    return ok([availability_dict(item) for item in queryset.order_by("available_date", "start_time")])


@csrf_exempt
@require_POST
@role_required("doctor")
def availability_create(request):
    try:
        data = read_payload(request)
        item = DoctorAvailability.objects.create(
            doctor=request.doctor,
            available_date=data["available_date"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            visiting_fee=Decimal(str(data.get("visiting_fee", "0"))),
            is_active=True,
        )
        return ok(availability_dict(item), 201)
    except KeyError as exc:
        return fail(f"Missing required field: {exc.args[0]}", 400)
    except (ValueError, InvalidOperation) as exc:
        return fail(str(exc), 400)
    except IntegrityError as exc:
        return fail("The availability slot is invalid or already exists.", 409, details=str(exc))


@csrf_exempt
@require_POST
@role_required("doctor")
def availability_update(request, availability_id: int):
    try:
        item = DoctorAvailability.objects.get(availability_id=availability_id, doctor=request.doctor)
        data = read_payload(request)
        for field in ("available_date", "start_time", "end_time", "is_active"):
            if field in data:
                setattr(item, field, data[field])
        if "visiting_fee" in data:
            item.visiting_fee = Decimal(str(data["visiting_fee"]))
        item.save()
        return ok(availability_dict(item))
    except DoctorAvailability.DoesNotExist:
        return fail("Availability entry not found.", 404)
    except (ValueError, InvalidOperation, IntegrityError) as exc:
        return fail("Invalid availability data.", 400, details=str(exc))


@csrf_exempt
@require_POST
@role_required("doctor")
def availability_deactivate(request, availability_id: int):
    updated = DoctorAvailability.objects.filter(
        availability_id=availability_id, doctor=request.doctor
    ).update(is_active=False)
    if not updated:
        return fail("Availability entry not found.", 404)
    return ok({"availability_id": availability_id, "is_active": False})
