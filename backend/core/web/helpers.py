"""Thin integration helpers for the browser (server-rendered) frontend.

These helpers reuse the existing session identity keys (``client_id``,
``role`` and ``role_id``) and the same ownership rules as the API views.
No design-pattern code lives here; views call the existing Factory, Builder,
Facade, Service, Proxy and Observer implementations directly.
"""

from functools import wraps
from typing import Callable

from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import redirect, render

from core.models import Admin, Client, Doctor, Patient

ROLE_DISPLAY = {
    "patient": "Patient",
    "doctor": "Doctor",
    "admin": "Administrator",
}


def attach_identity(request: HttpRequest) -> bool:
    """Populate request.client and the role-specific object from the session.

    Returns False (and flushes the session) when the visitor is not logged in
    or the account is no longer active. Mirrors ``core.decorators``.
    """
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


def render_403(request: HttpRequest):
    return render(request, "errors/403.html", status=403)


def web_login_required(view: Callable):
    @wraps(view)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not attach_identity(request):
            messages.error(request, "Authentication required. Please log in.")
            return redirect(f"/login/?next={request.path}")
        return view(request, *args, **kwargs)

    return wrapper


def web_role_required(*allowed_roles: str):
    def decorator(view: Callable):
        @wraps(view)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not attach_identity(request):
                messages.error(request, "Authentication required. Please log in.")
                return redirect(f"/login/?next={request.path}")
            if request.role not in allowed_roles:
                return render_403(request)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def navigation(request: HttpRequest) -> dict:
    """Context processor: expose lightweight nav state to every template.

    Reads only session values so it never adds a query to page rendering.
    """
    role = request.session.get("role")
    authenticated = bool(request.session.get("client_id") and role)
    return {
        "nav": {
            "authenticated": authenticated,
            "role": role,
            "role_display": ROLE_DISPLAY.get(role, ""),
            "full_name": request.session.get("full_name", ""),
            "show_sidebar": authenticated,
        }
    }
