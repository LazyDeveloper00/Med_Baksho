from django.db import connection
from django.views.decorators.http import require_GET

from core.http import fail, ok


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return fail("Database connection failed.", 503, details=str(exc))
    return ok({"service": "Mediবাক্স backend", "database": "connected"})
