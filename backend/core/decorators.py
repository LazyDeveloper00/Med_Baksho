from functools import wraps
from typing import Callable

from django.http import HttpRequest

from core.http import fail
from core.models import Admin, Client, Doctor, Patient


def _attach_identity(request: HttpRequest) -> bool:
    client_id = request.session.get("client_id")
    role = request.session.get("role")
    role_id = request.session.get("role_id")
    if not client_id or not role or not role_id:
        return False

    try:
        request.client = Client.objects.get(user_id=client_id)
        if request.client.account_status.lower() != "active":
            request.session.flush()
            return False
        if role == "patient":
            request.patient = Patient.objects.get(p_id=role_id, user=request.client)
        elif role == "doctor":
            request.doctor = Doctor.objects.get(d_id=role_id, user=request.client)
        elif role == "admin":
            request.admin = Admin.objects.get(a_id=role_id, user=request.client)
        else:
            return False
        request.role = role
        return True
    except (Client.DoesNotExist, Patient.DoesNotExist, Doctor.DoesNotExist, Admin.DoesNotExist):
        request.session.flush()
        return False


def login_required(view: Callable):
    @wraps(view)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not _attach_identity(request):
            return fail("Authentication required.", 401)
        return view(request, *args, **kwargs)

    return wrapper


def role_required(*allowed_roles: str):
    def decorator(view: Callable):
        @wraps(view)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not _attach_identity(request):
                return fail("Authentication required.", 401)
            if request.role not in allowed_roles:
                return fail("You do not have permission for this action.", 403)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
