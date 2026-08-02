import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medibaksho_backend.settings")

import django
django.setup()

import unittest
from types import SimpleNamespace
from unittest.mock import Mock


class FakeStrategy:
    def generate_response(self, question, context):
        return f"{question}|{context}"


class FakeObserver:
    def __init__(self):
        self.events = []

    def update(self, message, user):
        self.events.append((message, user.user_id))


class PatternRegressionTests(unittest.TestCase):
    def test_strategy_can_be_switched(self):
        from core.chatbot.service import ChatbotService

        first = FakeStrategy()
        second = FakeStrategy()
        service = ChatbotService(first)
        self.assertIs(service.provider, first)
        service.set_provider(second)
        self.assertIs(service.provider, second)

    def test_observer_attach_detach_and_notify(self):
        from core.approvals.services import ApprovalService

        observer = FakeObserver()
        service = ApprovalService()
        service.attach(observer)
        user = SimpleNamespace(user_id=7)
        service.notify_observers("approved", user)
        self.assertEqual(observer.events, [("approved", 7)])
        service.detach(observer)
        service.notify_observers("ignored", user)
        self.assertEqual(observer.events, [("approved", 7)])

    def test_proxy_blocks_empty_question(self):
        from core.chatbot.proxy import ChatbotProxy

        service = Mock()
        proxy = ChatbotProxy(service)
        client = SimpleNamespace(user_id=1, account_status="Active")
        patient = SimpleNamespace(user_id=1)
        with self.assertRaises(ValueError):
            proxy.answer(client, patient, "   ")
        service.answer_question.assert_not_called()

    def test_proxy_forwards_valid_question(self):
        from core.chatbot.proxy import ChatbotProxy

        service = Mock()
        service.answer_question.return_value = "answer"
        proxy = ChatbotProxy(service, max_requests=100)
        client = SimpleNamespace(user_id=99991, account_status="Active")
        patient = SimpleNamespace(user_id=99991)
        result = proxy.answer(client, patient, " What happened? ")
        self.assertEqual(result, "answer")
        service.answer_question.assert_called_once_with(patient, "What happened?")


if __name__ == "__main__":
    unittest.main()

class FactoryStructureRegressionTests(unittest.TestCase):
    def test_factory_module_has_no_conditional_branch_nodes(self):
        import ast
        from pathlib import Path
        import core.accounts.factories as factory_module

        source = Path(factory_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = (ast.If, ast.IfExp, ast.Match)
        found = [node.__class__.__name__ for node in ast.walk(tree) if isinstance(node, forbidden)]
        self.assertEqual(found, [])

    def test_factory_registry_contains_all_roles(self):
        from core.accounts.factories import AccountFactory

        self.assertEqual(set(AccountFactory._creators), {"patient", "doctor", "admin"})
