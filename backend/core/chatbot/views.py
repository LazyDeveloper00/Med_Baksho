import logging

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.chatbot.proxy import ChatbotProxy
from core.chatbot.service import build_chatbot_service
from core.decorators import role_required
from core.http import fail, ok, read_payload

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
@role_required("patient")
def ask(request):
    try:
        data = read_payload(request)
        proxy = ChatbotProxy(build_chatbot_service())
        answer = proxy.answer(request.client, request.patient, str(data.get("question", "")))
        return ok({"answer": answer})
    except ValueError as exc:
        return fail(str(exc), 400)
    except PermissionError as exc:
        return fail(str(exc), 403)
    except Exception as exc:
        logger.exception("Chatbot provider request failed")
        return fail("The chatbot provider is unavailable or not configured.", 503, details=str(exc))
