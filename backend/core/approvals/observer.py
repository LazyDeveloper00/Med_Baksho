from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock

from django.conf import settings

from core.models import Client


class Observer(ABC):
    @abstractmethod
    def update(self, message: str, user: Client) -> None:
        raise NotImplementedError


class UserNotificationObserver(Observer):
    """Observer implementation using a JSON-lines event file."""

    _lock = Lock()

    def __init__(self, path: Path | None = None):
        self.path = path or (settings.LOG_DIR / "notifications.jsonl")

    def update(self, message: str, user: Client) -> None:
        event = {
            "user_id": user.user_id,
            "message": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_for_user(self, user_id: int, limit: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        with self._lock, self.path.open("r", encoding="utf-8") as stream:
            events = []
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("user_id") == user_id:
                    events.append(event)
        return events[-limit:][::-1]
