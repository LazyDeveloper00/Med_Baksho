from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.decorators import role_required
from core.http import fail, ok, read_payload
from core.models import DoctorAvailability
from core.serializers import availability_dict


def _parse_date(value, field_name: str = "available_date") -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.") from exc


def _parse_time(value, field_name: str) -> time:
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must use HH:MM or HH:MM:SS format.") from exc


def _parse_fee(value) -> Decimal:
    try:
        fee = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("visiting_fee must be a valid number.") from exc
    if fee < 0:
        raise ValueError("visiting_fee cannot be negative.")
    return fee


def _parse_bool(value, field_name: str = "is_active") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{field_name} must be true or false.")


def _validate_slot(available_date: date, start_time: time, end_time: time, *, allow_past=False):
    if not allow_past and available_date < date.today():
        raise ValueError("available_date cannot be in the past.")
    if end_time <= start_time:
        raise ValueError("end_time must be later than start_time.")


@require_GET
def availability_list(request):
    """Public list: only future active slots belonging to approved active doctors."""
    queryset = DoctorAvailability.objects.select_related("doctor__user").filter(
        is_active=True,
        doctor__verification_status="Approved",
        doctor__user__account_status="Active",
        available_date__gte=date.today(),
    )
    doctor_id = request.GET.get("doctor_id")
    available_date = request.GET.get("date")
    if doctor_id:
        try:
            doctor_id = int(doctor_id)
        except (TypeError, ValueError):
            return fail("doctor_id must be an integer.", 400)
        queryset = queryset.filter(doctor_id=doctor_id)
    if available_date:
        try:
            queryset = queryset.filter(available_date=_parse_date(available_date, "date"))
        except ValueError as exc:
            return fail(str(exc), 400)
    return ok(
        [
            availability_dict(item)
            for item in queryset.order_by("available_date", "start_time")
        ]
    )


@require_GET
@role_required("doctor")
def my_availability_list(request):
    """Doctor dashboard list: includes the logged-in doctor's own past/inactive slots."""
    queryset = DoctorAvailability.objects.select_related("doctor__user").filter(
        doctor=request.doctor
    )

    if "is_active" in request.GET:
        try:
            queryset = queryset.filter(is_active=_parse_bool(request.GET.get("is_active")))
        except ValueError as exc:
            return fail(str(exc), 400)

    if request.GET.get("date_from"):
        try:
            queryset = queryset.filter(
                available_date__gte=_parse_date(request.GET["date_from"], "date_from")
            )
        except ValueError as exc:
            return fail(str(exc), 400)

    if request.GET.get("date_to"):
        try:
            queryset = queryset.filter(
                available_date__lte=_parse_date(request.GET["date_to"], "date_to")
            )
        except ValueError as exc:
            return fail(str(exc), 400)

    return ok(
        [
            availability_dict(item)
            for item in queryset.order_by("-available_date", "start_time")
        ]
    )


@csrf_exempt
@require_POST
@role_required("doctor")
def availability_create(request):
    try:
        data = read_payload(request)
        available_date = _parse_date(data["available_date"])
        start_time = _parse_time(data["start_time"], "start_time")
        end_time = _parse_time(data["end_time"], "end_time")
        visiting_fee = _parse_fee(data.get("visiting_fee", "0"))
        _validate_slot(available_date, start_time, end_time)

        item = DoctorAvailability.objects.create(
            doctor=request.doctor,
            available_date=available_date,
            start_time=start_time,
            end_time=end_time,
            visiting_fee=visiting_fee,
            is_active=True,
        )
        return ok(availability_dict(item), 201)
    except KeyError as exc:
        return fail(f"Missing required field: {exc.args[0]}", 400)
    except ValueError as exc:
        return fail(str(exc), 400)
    except IntegrityError:
        return fail("The availability slot already exists or violates a database constraint.", 409)


@csrf_exempt
@require_POST
@role_required("doctor")
def availability_update(request, availability_id: int):
    try:
        item = DoctorAvailability.objects.select_related("doctor__user").get(
            availability_id=availability_id,
            doctor=request.doctor,
        )
        data = read_payload(request)

        new_date = (
            _parse_date(data["available_date"])
            if "available_date" in data
            else item.available_date
        )
        new_start = (
            _parse_time(data["start_time"], "start_time")
            if "start_time" in data
            else item.start_time
        )
        new_end = (
            _parse_time(data["end_time"], "end_time")
            if "end_time" in data
            else item.end_time
        )
        new_fee = _parse_fee(data["visiting_fee"]) if "visiting_fee" in data else item.visiting_fee
        new_active = _parse_bool(data["is_active"]) if "is_active" in data else item.is_active

        # Existing past slots may still be deactivated/edited for record management, but a
        # request cannot move a slot to a past date or reactivate a past slot.
        date_changed = "available_date" in data
        reactivating = "is_active" in data and new_active and not item.is_active
        _validate_slot(
            new_date,
            new_start,
            new_end,
            allow_past=not (date_changed or reactivating),
        )

        item.available_date = new_date
        item.start_time = new_start
        item.end_time = new_end
        item.visiting_fee = new_fee
        item.is_active = new_active
        item.save()
        return ok(availability_dict(item))
    except DoctorAvailability.DoesNotExist:
        return fail("Availability entry not found.", 404)
    except ValueError as exc:
        return fail(str(exc), 400)
    except IntegrityError:
        return fail("The availability slot already exists or violates a database constraint.", 409)


@csrf_exempt
@require_POST
@role_required("doctor")
def availability_deactivate(request, availability_id: int):
    updated = DoctorAvailability.objects.filter(
        availability_id=availability_id,
        doctor=request.doctor,
    ).update(is_active=False)
    if not updated:
        return fail("Availability entry not found.", 404)
    return ok({"availability_id": availability_id, "is_active": False})
