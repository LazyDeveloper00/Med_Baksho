from collections import defaultdict, deque
from time import monotonic

from core.chatbot.service import ChatbotService
from core.models import Client, Patient


class ChatbotProxy:
    """Proxy Pattern: protects the external chatbot service."""

    _request_times: dict[int, deque[float]] = defaultdict(deque)

    def __init__(self, service: ChatbotService, max_requests: int = 5, window_seconds: int = 60):
        self.service = service
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def answer(self, client: Client, patient: Patient, question: str) -> str:
        if client.account_status.lower() != "active":
            raise PermissionError("Inactive accounts cannot use the chatbot.")
        if patient.user_id != client.user_id:
            raise PermissionError("Patient account mismatch.")
        cleaned = " ".join(question.split())
        if not cleaned:
            raise ValueError("Question cannot be empty.")
        if len(cleaned) > 500:
            raise ValueError("Question cannot exceed 500 characters.")
        self._enforce_rate_limit(client.user_id)
        return self.service.answer_question(patient, cleaned)

    def _enforce_rate_limit(self, user_id: int) -> None:
        now = monotonic()
        history = self._request_times[user_id]
        while history and now - history[0] > self.window_seconds:
            history.popleft()
        if len(history) >= self.max_requests:
            raise PermissionError("Too many chatbot requests. Wait one minute and try again.")
        history.append(now)
