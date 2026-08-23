import json
from typing import Any

from django.http import HttpRequest, JsonResponse


def read_payload(request: HttpRequest) -> dict[str, Any]:
    content_type = request.content_type or ""
    if "application/json" in content_type:
        try:
            body = request.body.decode("utf-8") if request.body else "{}"
            data = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must contain valid JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON request body must be an object.")
        return data
    return request.POST.dict()


def parse_json_list(value: Any, field_name: str) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        result = value
    elif isinstance(value, str):
        try:
            result = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be a valid JSON array.") from exc
    else:
        raise ValueError(f"{field_name} must be a JSON array.")
    if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
        raise ValueError(f"{field_name} must be an array of objects.")
    return result


def ok(data: Any = None, status: int = 200) -> JsonResponse:
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    return JsonResponse(payload, status=status, safe=True)


def fail(message: str, status: int = 400, *, details: Any = None) -> JsonResponse:
    payload: dict[str, Any] = {"ok": False, "error": message}
    if details is not None:
        payload["details"] = details
    return JsonResponse(payload, status=status)
