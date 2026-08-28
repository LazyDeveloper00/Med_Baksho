import logging

logger = logging.getLogger("medibaksho.audit")


class RequestAuditMiddleware:
    """Record basic system activity without adding another database table."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        session = getattr(request, "session", None)
        client_id = session.get("client_id") if session is not None else None
        role = session.get("role") if session is not None else None
        logger.info(
            "method=%s path=%s status=%s client_id=%s role=%s",
            request.method,
            request.path,
            response.status_code,
            client_id,
            role,
        )
        return response
