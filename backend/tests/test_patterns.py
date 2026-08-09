import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medibaksho_backend.settings")

import django

django.setup()


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

    def test_factory_module_has_no_conditional_branch_nodes(self):
        import core.accounts.factories as factory_module

        source = Path(factory_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = (ast.If, ast.IfExp, ast.Match)
        found = [
            node.__class__.__name__
            for node in ast.walk(tree)
            if isinstance(node, forbidden)
        ]
        self.assertEqual(found, [])

    def test_factory_registry_contains_all_roles(self):
        from core.accounts.factories import AccountFactory

        self.assertEqual(set(AccountFactory._creators), {"patient", "doctor", "admin"})

    def test_builder_collects_optional_parts_with_fluent_interface(self):
        from core.records.builders import PrescriptionBuilder

        patient_disease = SimpleNamespace(patient_disease_id=4)
        builder = PrescriptionBuilder(patient_disease)

        self.assertIs(
            builder.set_base(
                prescription_date="2026-08-09",
                doctor_name="Dr Test",
                custom_facility_name="Clinic",
            ),
            builder,
        )
        self.assertIs(
            builder.add_medicine(
                medicine_id=1,
                dosage="1 tablet",
                times_per_day=2,
                duration_days=5,
            ),
            builder,
        )
        self.assertIs(builder.add_test(test_id=2), builder)
        self.assertIs(builder.add_image(file_path="prescriptions/test.png"), builder)
        self.assertEqual(len(builder.medicines), 1)
        self.assertEqual(len(builder.tests), 1)
        self.assertEqual(len(builder.images), 1)

    def test_facade_delegates_complex_creation_to_builder(self):
        from core.records.facades import MedicalRecordFacade

        patient = SimpleNamespace(p_id=3)
        patient_disease = SimpleNamespace(patient_disease_id=9)
        built_prescription = SimpleNamespace(prescription_id=11)
        builder = Mock()
        builder.set_base.return_value = builder
        builder.build.return_value = built_prescription

        with patch(
            "core.records.facades.PatientDisease.objects.get",
            return_value=patient_disease,
        ) as get_record, patch(
            "core.records.facades.PrescriptionBuilder",
            return_value=builder,
        ) as builder_class:
            result = MedicalRecordFacade.create_prescription(
                patient=patient,
                patient_disease_id=9,
                base_data={
                    "prescription_date": "2026-08-09",
                    "doctor_name": "Dr Test",
                    "custom_facility_name": "Clinic",
                },
                medicines=[{"medicine_id": 1}],
                tests=[{"test_id": 2}],
            )

        self.assertIs(result, built_prescription)
        get_record.assert_called_once_with(patient_disease_id=9, patient=patient)
        builder_class.assert_called_once_with(patient_disease)
        builder.add_medicine.assert_called_once_with(medicine_id=1)
        builder.add_test.assert_called_once_with(test_id=2)
        builder.build.assert_called_once_with()


class ValidationRegressionTests(unittest.TestCase):
    def test_builder_string_false_is_false(self):
        from core.records.builders import _as_bool

        self.assertFalse(_as_bool("false"))
        self.assertTrue(_as_bool("true"))

    def test_availability_rejects_invalid_boolean(self):
        from core.doctors.views import _parse_bool

        with self.assertRaises(ValueError):
            _parse_bool("maybe")


if __name__ == "__main__":
    unittest.main()
