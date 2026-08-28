"""Broad offline regression suite for the Mediবাক্স final package.

The suite intentionally avoids the shared/live MySQL database and external AI
network calls. Database managers, storage and HTTP calls are mocked where
needed, so it is safe to run on a teammate laptop.
"""

from __future__ import annotations

import ast
import json
import os
import re
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medibaksho_backend.settings")

import django

django.setup()

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from django.test import RequestFactory
from django.urls import resolve


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def json_payload(response):
    return json.loads(response.content.decode("utf-8"))


class FakeSession(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flushed = False
        self.cycled = False

    def flush(self):
        self.flushed = True
        self.clear()

    def cycle_key(self):
        self.cycled = True


class HttpRegressionTests(unittest.TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_read_payload_accepts_json_object(self):
        from core.http import read_payload

        request = self.rf.post("/x/", data=json.dumps({"a": 1}), content_type="application/json")
        self.assertEqual(read_payload(request), {"a": 1})

    def test_read_payload_rejects_invalid_json(self):
        from core.http import read_payload

        request = self.rf.post("/x/", data="{", content_type="application/json")
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            read_payload(request)

    def test_read_payload_rejects_json_array(self):
        from core.http import read_payload

        request = self.rf.post("/x/", data="[]", content_type="application/json")
        with self.assertRaisesRegex(ValueError, "must be an object"):
            read_payload(request)

    def test_read_payload_accepts_form_data(self):
        from core.http import read_payload

        request = self.rf.post("/x/", data={"name": "Rafid"})
        self.assertEqual(read_payload(request), {"name": "Rafid"})

    def test_parse_json_list_accepts_list_and_encoded_list(self):
        from core.http import parse_json_list

        value = [{"medicine_id": 1}]
        self.assertEqual(parse_json_list(value, "medicines"), value)
        self.assertEqual(parse_json_list(json.dumps(value), "medicines"), value)
        self.assertEqual(parse_json_list("", "medicines"), [])

    def test_parse_json_list_rejects_non_object_items(self):
        from core.http import parse_json_list

        with self.assertRaisesRegex(ValueError, "array of objects"):
            parse_json_list("[1, 2]", "medicines")

    def test_ok_and_fail_response_contract(self):
        from core.http import fail, ok

        success = ok({"x": 1}, 201)
        error = fail("bad", 422, details={"field": "x"})
        self.assertEqual(success.status_code, 201)
        self.assertEqual(json_payload(success), {"ok": True, "data": {"x": 1}})
        self.assertEqual(error.status_code, 422)
        self.assertEqual(
            json_payload(error),
            {"ok": False, "error": "bad", "details": {"field": "x"}},
        )


class ValidationHelperRegressionTests(unittest.TestCase):
    def test_account_required_and_optional_date(self):
        from core.accounts.views import _optional_date, _required

        _required({"a": " x "}, "a")
        with self.assertRaisesRegex(ValueError, "Missing required fields"):
            _required({"a": ""}, "a")
        self.assertEqual(_optional_date("2026-08-27", "d"), date(2026, 8, 27))
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            _optional_date("27/08/2026", "d")

    def test_doctor_parsers(self):
        from core.doctors.views import _parse_bool, _parse_date, _parse_fee, _parse_time

        self.assertEqual(_parse_date("2026-08-27"), date(2026, 8, 27))
        self.assertEqual(_parse_time("09:30", "start_time"), time(9, 30))
        self.assertEqual(_parse_fee("500.50"), Decimal("500.50"))
        self.assertTrue(_parse_bool("yes"))
        self.assertFalse(_parse_bool("off"))
        with self.assertRaises(ValueError):
            _parse_fee("x")
        with self.assertRaises(ValueError):
            _parse_bool("maybe")

    def test_doctor_slot_validation(self):
        from core.doctors.views import _validate_slot

        tomorrow = date.today() + timedelta(days=1)
        _validate_slot(tomorrow, time(9), time(10))
        with self.assertRaisesRegex(ValueError, "later than"):
            _validate_slot(tomorrow, time(10), time(9))
        with self.assertRaisesRegex(ValueError, "past"):
            _validate_slot(date.today() - timedelta(days=1), time(9), time(10))

    def test_masterdata_validation(self):
        from core.masterdata.views import _parse_bool, _required_text

        self.assertEqual(_required_text({"name": "  abc "}, "name"), "abc")
        self.assertTrue(_parse_bool(1))
        self.assertFalse(_parse_bool("false"))
        with self.assertRaises(ValueError):
            _required_text({"name": "   "}, "name")

    def test_builder_conversion_helpers(self):
        from core.records.builders import _as_bool, _as_optional_date, _as_required_date

        self.assertTrue(_as_bool("TRUE"))
        self.assertFalse(_as_bool("0"))
        self.assertEqual(_as_optional_date("2026-08-27", "d"), date(2026, 8, 27))
        self.assertIsNone(_as_optional_date("", "d"))
        with self.assertRaisesRegex(ValueError, "required"):
            _as_required_date("", "d")

    def test_facade_positive_integer_parser(self):
        from core.records.facades import _optional_positive_int

        self.assertIsNone(_optional_positive_int("", "x"))
        self.assertEqual(_optional_positive_int("7", "x"), 7)
        with self.assertRaisesRegex(ValueError, "integer"):
            _optional_positive_int("abc", "x")
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            _optional_positive_int("0", "x")


class FactoryAndPatternRegressionTests(unittest.TestCase):
    def test_factory_singleton_identity(self):
        from core.accounts.factories import AccountFactory

        self.assertIs(AccountFactory(), AccountFactory.get_instance())

    def test_factory_registry_has_all_roles(self):
        from core.accounts.factories import AccountFactory

        self.assertEqual(set(AccountFactory._creators), {"patient", "doctor", "admin"})

    def test_factory_role_dispatch_has_no_if_match_or_try(self):
        import inspect
        from core.accounts.factories import AccountFactory

        import textwrap
        tree = ast.parse(textwrap.dedent(inspect.getsource(AccountFactory.create_account)))
        forbidden = (ast.If, ast.IfExp, ast.Match, ast.Try)
        self.assertEqual([type(n).__name__ for n in ast.walk(tree) if isinstance(n, forbidden)], [])

    def test_account_creator_role_cleanup(self):
        from core.accounts.factories import DoctorAccountCreator, PatientAccountCreator

        client = SimpleNamespace(user_id=1)
        patient = SimpleNamespace(p_id=2)
        doctor = SimpleNamespace(d_id=3)
        with patch("core.accounts.factories.Patient.objects.create", return_value=patient) as create_patient:
            result = PatientAccountCreator().create_role(
                client=client,
                date_of_birth=None,
                blood_group=" A+ ",
                address=" Road ",
            )
        self.assertIs(result, patient)
        create_patient.assert_called_once_with(
            user=client, date_of_birth=None, blood_group="A+", address="Road"
        )

        with patch("core.accounts.factories.Doctor.objects.create", return_value=doctor) as create_doctor:
            result = DoctorAccountCreator().create_role(
                client=client,
                licence_number=" LIC-1 ",
                degree=" MBBS ",
                field_of_expertise=" Cardiology ",
                workplace=" NSU Clinic ",
            )
        self.assertIs(result, doctor)
        self.assertEqual(create_doctor.call_args.kwargs["verification_status"], "Pending")
        self.assertEqual(create_doctor.call_args.kwargs["licence_number"], "LIC-1")


class ProxyRegressionTests(unittest.TestCase):
    def setUp(self):
        from core.chatbot.proxy import ChatbotProxy

        ChatbotProxy._request_times.clear()

    def test_proxy_rejects_inactive_mismatch_empty_and_long_question(self):
        from core.chatbot.proxy import ChatbotProxy

        service = Mock()
        proxy = ChatbotProxy(service, max_requests=10)
        with self.assertRaises(PermissionError):
            proxy.answer(SimpleNamespace(user_id=1, account_status="Suspended"), SimpleNamespace(user_id=1), "hi")
        with self.assertRaises(PermissionError):
            proxy.answer(SimpleNamespace(user_id=1, account_status="Active"), SimpleNamespace(user_id=2), "hi")
        with self.assertRaises(ValueError):
            proxy.answer(SimpleNamespace(user_id=1, account_status="Active"), SimpleNamespace(user_id=1), "   ")
        with self.assertRaises(ValueError):
            proxy.answer(SimpleNamespace(user_id=1, account_status="Active"), SimpleNamespace(user_id=1), "x" * 501)
        service.answer_question.assert_not_called()

    def test_proxy_normalizes_and_forwards_question(self):
        from core.chatbot.proxy import ChatbotProxy

        service = Mock(answer_question=Mock(return_value="answer"))
        proxy = ChatbotProxy(service, max_requests=10)
        client = SimpleNamespace(user_id=1001, account_status="Active")
        patient = SimpleNamespace(user_id=1001)
        self.assertEqual(proxy.answer(client, patient, "  What   happened?  "), "answer")
        service.answer_question.assert_called_once_with(patient, "What happened?")

    def test_proxy_rate_limit(self):
        from core.chatbot.proxy import ChatbotProxy

        service = Mock(answer_question=Mock(return_value="ok"))
        proxy = ChatbotProxy(service, max_requests=2, window_seconds=60)
        client = SimpleNamespace(user_id=1002, account_status="Active")
        patient = SimpleNamespace(user_id=1002)
        proxy.answer(client, patient, "one")
        proxy.answer(client, patient, "two")
        with self.assertRaisesRegex(PermissionError, "Too many"):
            proxy.answer(client, patient, "three")


class StrategyRegressionTests(unittest.TestCase):
    def test_openrouter_requires_key(self):
        from core.chatbot.strategies import OpenRouterStrategy

        with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
            OpenRouterStrategy("", "model").generate_response("q", "c")

    def test_huggingface_requires_key(self):
        from core.chatbot.strategies import HuggingFaceStrategy

        with self.assertRaisesRegex(RuntimeError, "HUGGINGFACE_API_KEY"):
            HuggingFaceStrategy("", "model").generate_response("q", "c")

    def test_openrouter_request_and_response_contract(self):
        from core.chatbot.strategies import OpenRouterStrategy

        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": " answer "}}]}
        with patch("core.chatbot.strategies.requests.post", return_value=response) as post:
            result = OpenRouterStrategy("key", "model-x").generate_response("Question", "Context")
        self.assertEqual(result, "answer")
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(post.call_args.kwargs["json"]["model"], "model-x")
        self.assertIn("Question", post.call_args.kwargs["json"]["messages"][1]["content"])

    def test_huggingface_request_and_response_contract(self):
        from core.chatbot.strategies import HuggingFaceStrategy

        response = Mock()
        response.json.return_value = {"choices": [{"message": {"content": " hf answer "}}]}
        with patch("core.chatbot.strategies.requests.post", return_value=response) as post:
            result = HuggingFaceStrategy("key", "model-y", "https://example.test/chat").generate_response("Q", "C")
        self.assertEqual(result, "hf answer")
        self.assertEqual(post.call_args.args[0], "https://example.test/chat")
        self.assertEqual(post.call_args.kwargs["timeout"], 30)

    def test_build_chatbot_service_selects_configured_provider(self):
        from core.chatbot.service import build_chatbot_service
        from core.chatbot.strategies import HuggingFaceStrategy, OpenRouterStrategy

        with patch("core.chatbot.service.settings.AI_PROVIDER", "huggingface"), \
             patch("core.chatbot.service.settings.HUGGINGFACE_API_KEY", "k"), \
             patch("core.chatbot.service.settings.HUGGINGFACE_MODEL", "m"), \
             patch("core.chatbot.service.settings.HUGGINGFACE_API_URL", "u"):
            self.assertIsInstance(build_chatbot_service().provider, HuggingFaceStrategy)
        with patch("core.chatbot.service.settings.AI_PROVIDER", "openrouter"), \
             patch("core.chatbot.service.settings.OPENROUTER_API_KEY", "k"), \
             patch("core.chatbot.service.settings.OPENROUTER_MODEL", "m"):
            self.assertIsInstance(build_chatbot_service().provider, OpenRouterStrategy)


class ChatbotServiceRegressionTests(unittest.TestCase):
    def test_answer_question_delegates_with_built_context(self):
        from core.chatbot.service import ChatbotService

        provider = Mock(generate_response=Mock(return_value="result"))
        patient = SimpleNamespace()
        service = ChatbotService(provider)
        with patch.object(service, "_build_patient_context", return_value="CTX"):
            self.assertEqual(service.answer_question(patient, "Q"), "result")
        provider.generate_response.assert_called_once_with("Q", "CTX")

    def test_patient_context_contains_disease_prescription_medicine_and_test(self):
        from core.chatbot.service import ChatbotService

        disease = SimpleNamespace(disease_name="Migraine")
        disease_record = SimpleNamespace(
            disease=disease,
            current_status="Active",
            diagnosed_date=date(2026, 7, 15),
            notes="Recurring",
        )
        disease_manager = MagicMock()
        disease_manager.select_related.return_value.all.return_value = [disease_record]
        patient = SimpleNamespace(user=SimpleNamespace(full_name="Test Patient"), disease_records=disease_manager)

        medicine_entry = SimpleNamespace(
            medicine=SimpleNamespace(medicine_name="Med A", main_active_ingredient="Ingredient"),
            dosage="1 tablet",
            times_per_day=2,
            duration_days=5,
            start_date=None,
            end_date=None,
            course_completed=False,
            side_effects=None,
            effectiveness="Unknown",
        )
        test_entry = SimpleNamespace(
            custom_test_name=None,
            test=SimpleNamespace(test_name="CBC"),
            completion_status="Completed",
            test_date=date(2026, 7, 16),
            diagnostic_center_name="Popular",
            result_summary="Normal",
        )
        prescription = SimpleNamespace(
            prescription_id=10,
            prescription_date=date(2026, 7, 15),
            patient_disease=SimpleNamespace(disease=disease),
            doctor_name="Dr Ahmed",
            facility=SimpleNamespace(facility_name="Popular Diagnostic Centre"),
            custom_facility_name=None,
            illness_location="Head",
            advice="Rest",
            additional_notes=None,
            medicine_entries=SimpleNamespace(all=lambda: [medicine_entry]),
            test_entries=SimpleNamespace(all=lambda: [test_entry]),
        )
        qs = MagicMock()
        qs.filter.return_value.select_related.return_value.prefetch_related.return_value.order_by.return_value.__getitem__.return_value = [prescription]
        with patch("core.chatbot.service.Prescription.objects", qs):
            context = ChatbotService(Mock())._build_patient_context(patient)
        for text in ["Test Patient", "Migraine", "Dr Ahmed", "Med A", "CBC", "Popular Diagnostic Centre"]:
            self.assertIn(text, context)


class ObserverRegressionTests(unittest.TestCase):
    def test_notification_round_trip_and_user_filter(self):
        from core.approvals.observer import UserNotificationObserver

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notifications.jsonl"
            observer = UserNotificationObserver(path)
            observer.update("one", SimpleNamespace(user_id=1))
            observer.update("other user", SimpleNamespace(user_id=2))
            observer.update("two", SimpleNamespace(user_id=1))
            events = observer.read_for_user(1)
        self.assertEqual([event["message"] for event in events], ["two", "one"])

    def test_notification_reader_ignores_corrupt_json_lines(self):
        from core.approvals.observer import UserNotificationObserver

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "notifications.jsonl"
            path.write_text('{bad json}\n{"user_id": 3, "message": "ok"}\n', encoding="utf-8")
            events = UserNotificationObserver(path).read_for_user(3)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message"], "ok")


class ApprovalServiceRegressionTests(unittest.TestCase):
    def test_doctor_approval_and_rejection_state_rules(self):
        from core.approvals.services import ApprovalService

        service = ApprovalService()
        service.notify_observers = Mock()
        admin = SimpleNamespace(a_id=1)
        user = SimpleNamespace(user_id=2)
        doctor = SimpleNamespace(verification_status="Pending", user=user, save=Mock())
        approved = ApprovalService.approve_doctor.__wrapped__(service, admin, doctor)
        self.assertIs(approved, doctor)
        self.assertEqual(doctor.verification_status, "Approved")
        self.assertIs(doctor.verified_by_admin, admin)
        service.notify_observers.assert_called_once()

        with self.assertRaisesRegex(ValueError, "Only Pending"):
            ApprovalService.approve_doctor.__wrapped__(service, admin, doctor)

        doctor2 = SimpleNamespace(verification_status="Pending", user=user, save=Mock())
        service.notify_observers.reset_mock()
        ApprovalService.reject_doctor.__wrapped__(service, admin, doctor2, comments="Bad licence")
        self.assertEqual(doctor2.verification_status, "Rejected")
        self.assertIn("Bad licence", service.notify_observers.call_args.args[0])

    def test_medicine_rejection_updates_submission_and_notifies(self):
        from core.approvals.services import ApprovalService

        service = ApprovalService()
        service.notify_observers = Mock()
        admin = SimpleNamespace(a_id=1)
        user = SimpleNamespace(user_id=4)
        submission = SimpleNamespace(
            status="Pending",
            proposed_medicine_name="Med X",
            patient=SimpleNamespace(user=user),
            save=Mock(),
        )
        result = ApprovalService.reject_medicine.__wrapped__(service, admin, submission, comments="Duplicate")
        self.assertIs(result, submission)
        self.assertEqual(submission.status, "Rejected")
        self.assertEqual(submission.review_comments, "Duplicate")
        submission.save.assert_called_once()
        self.assertIn("Duplicate", service.notify_observers.call_args.args[0])


class BuilderRegressionTests(unittest.TestCase):
    def test_builder_requires_core_fields_and_facility(self):
        from core.records.builders import PrescriptionBuilder

        builder = PrescriptionBuilder(SimpleNamespace(patient_disease_id=1))
        with self.assertRaisesRegex(ValueError, "Missing prescription fields"):
            builder._validate()
        builder.set_base(prescription_date="2026-08-27", doctor_name="Dr A")
        with self.assertRaisesRegex(ValueError, "Select a facility"):
            builder._validate()

    def test_builder_builds_base_and_optional_children(self):
        from core.records.builders import PrescriptionBuilder

        patient_disease = SimpleNamespace(patient_disease_id=1)
        facility = SimpleNamespace(facility_id=2)
        medicine = SimpleNamespace(medicine_id=3)
        medical_test = SimpleNamespace(test_id=4)
        prescription = SimpleNamespace(prescription_id=5)
        builder = PrescriptionBuilder(patient_disease)
        builder.set_base(
            facility_id=2,
            prescription_date="2026-08-27",
            doctor_name=" Dr A ",
            illness_location=" Head ",
        ).add_medicine(
            medicine_id=3,
            dosage="1 tablet",
            times_per_day="2",
            duration_days="5",
            course_completed="false",
        ).add_test(test_id=4).add_image(file_path="prescriptions/a.png", file_size_kb=12)

        with patch("core.records.builders.MedicalFacility.objects.get", return_value=facility), \
             patch("core.records.builders.Prescription.objects.create", return_value=prescription) as create_rx, \
             patch("core.records.builders.Medicine.objects.get", return_value=medicine), \
             patch("core.records.builders.PrescriptionMedicine.objects.create") as create_med, \
             patch("core.records.builders.MedicalTest.objects.get", return_value=medical_test), \
             patch("core.records.builders.PrescriptionTest.objects.create") as create_test, \
             patch("core.records.builders.PrescriptionImage.objects.create") as create_img:
            result = PrescriptionBuilder.build.__wrapped__(builder)
        self.assertIs(result, prescription)
        self.assertEqual(create_rx.call_args.kwargs["doctor_name"], "Dr A")
        self.assertFalse(create_med.call_args.kwargs["course_completed"])
        create_test.assert_called_once()
        create_img.assert_called_once()

    def test_builder_rejects_invalid_medicine_values(self):
        from core.records.builders import PrescriptionBuilder

        builder = PrescriptionBuilder(SimpleNamespace())
        builder.set_base(custom_facility_name="Clinic", prescription_date="2026-08-27", doctor_name="Dr")
        builder.add_medicine(medicine_id=1, dosage="x", times_per_day=0, duration_days=5)
        with patch("core.records.builders.Prescription.objects.create", return_value=SimpleNamespace()), \
             patch("core.records.builders.Medicine.objects.get", return_value=SimpleNamespace()):
            with self.assertRaisesRegex(ValueError, "greater than zero"):
                PrescriptionBuilder.build.__wrapped__(builder)


class FacadeRegressionTests(unittest.TestCase):
    def test_png_validation(self):
        from core.records.facades import MedicalRecordFacade

        good = SimpleNamespace(name="scan.PNG", content_type="image/png", size=1024)
        MedicalRecordFacade._validate_png(good)
        with self.assertRaisesRegex(ValueError, "Only PNG"):
            MedicalRecordFacade._validate_png(SimpleNamespace(name="scan.jpg", content_type="image/jpeg", size=10))
        too_large = SimpleNamespace(
            name="scan.png", content_type="image/png", size=(settings.MAX_PNG_MB * 1024 * 1024) + 1
        )
        with self.assertRaisesRegex(ValueError, "at most"):
            MedicalRecordFacade._validate_png(too_large)

    def test_facade_delegates_create_and_children(self):
        from core.records.facades import MedicalRecordFacade

        patient = SimpleNamespace(p_id=1)
        pd = SimpleNamespace(patient_disease_id=2)
        built = SimpleNamespace(prescription_id=3)
        builder = Mock()
        builder.set_base.return_value = builder
        builder.add_medicine.return_value = builder
        builder.add_test.return_value = builder
        builder.build.return_value = built
        with patch("core.records.facades.PatientDisease.objects.get", return_value=pd), \
             patch("core.records.facades.PrescriptionBuilder", return_value=builder):
            result = MedicalRecordFacade.create_prescription(
                patient=patient,
                patient_disease_id=2,
                base_data={"doctor_name": "Dr", "prescription_date": "2026-08-27", "custom_facility_name": "Clinic"},
                medicines=[{"medicine_id": 1}],
                tests=[{"test_id": 2}],
            )
        self.assertIs(result, built)
        builder.add_medicine.assert_called_once_with(medicine_id=1)
        builder.add_test.assert_called_once_with(test_id=2)

    def test_facade_search_applies_requested_filters(self):
        from core.records.facades import MedicalRecordFacade

        patient = SimpleNamespace(p_id=1)
        qs = MagicMock()
        # Make each filter return the same mock so call history remains inspectable.
        qs.filter.return_value = qs
        qs.distinct.return_value = qs
        qs.order_by.return_value = qs
        with patch.object(MedicalRecordFacade, "patient_prescriptions", return_value=qs):
            result = MedicalRecordFacade.search(
                patient=patient, disease_id="1", medicine_id="2", test_id="3", facility_id="4"
            )
        self.assertIs(result, qs)
        expected = [
            {"patient_disease__disease_id": 1},
            {"medicine_entries__medicine_id": 2},
            {"test_entries__test_id": 3},
            {"facility_id": 4},
        ]
        self.assertEqual([c.kwargs for c in qs.filter.call_args_list], expected)


class SerializerRegressionTests(unittest.TestCase):
    def test_client_and_availability_serializers(self):
        from core.serializers import availability_dict, client_dict

        client = SimpleNamespace(
            user_id=1,
            full_name="User",
            email="u@example.com",
            phone=None,
            account_status="Active",
            created_at=datetime(2026, 8, 27, 10, 0),
        )
        self.assertEqual(client_dict(client)["email"], "u@example.com")
        doctor = SimpleNamespace(user=client, field_of_expertise="Cardiology", workplace="Clinic")
        slot = SimpleNamespace(
            availability_id=2,
            doctor_id=3,
            doctor=doctor,
            available_date=date(2026, 8, 28),
            start_time=time(9),
            end_time=time(10),
            visiting_fee=Decimal("500.00"),
            is_active=True,
        )
        data = availability_dict(slot)
        self.assertEqual(data["doctor_name"], "User")
        self.assertEqual(data["visiting_fee"], "500.00")

    def test_patient_disease_serializer(self):
        from core.serializers import patient_disease_dict

        item = SimpleNamespace(
            patient_disease_id=4,
            disease_id=5,
            disease=SimpleNamespace(disease_name="Migraine"),
            diagnosed_date=None,
            current_status="Active",
            custom_disease_name=None,
            notes="n",
        )
        data = patient_disease_dict(item)
        self.assertEqual(data["disease_name"], "Migraine")
        self.assertIsNone(data["diagnosed_date"])


class IdentityAndMiddlewareRegressionTests(unittest.TestCase):
    def test_api_attach_identity_patient(self):
        from core import decorators

        request = SimpleNamespace(session=FakeSession(client_id=10, role="patient", role_id=20))
        client = SimpleNamespace(user_id=10, account_status="Active")
        patient = SimpleNamespace(p_id=20)
        with patch("core.decorators.Client.objects.get", return_value=client), \
             patch("core.decorators.Patient.objects.get", return_value=patient):
            self.assertTrue(decorators._attach_identity(request))
        self.assertIs(request.client, client)
        self.assertIs(request.patient, patient)
        self.assertEqual(request.role, "patient")

    def test_api_attach_identity_rejects_inactive_and_flushes(self):
        from core import decorators

        session = FakeSession(client_id=10, role="patient", role_id=20)
        request = SimpleNamespace(session=session)
        with patch("core.decorators.Client.objects.get", return_value=SimpleNamespace(account_status="Suspended")):
            self.assertFalse(decorators._attach_identity(request))
        self.assertTrue(session.flushed)

    def test_web_navigation_context(self):
        from core.web.helpers import navigation

        request = SimpleNamespace(session=FakeSession(client_id=1, role="doctor", full_name="Dr X"))
        nav = navigation(request)["nav"]
        self.assertTrue(nav["authenticated"])
        self.assertEqual(nav["role_display"], "Doctor")

    def test_request_audit_middleware_logs_response_metadata(self):
        from core.middleware import RequestAuditMiddleware

        request = SimpleNamespace(
            method="GET", path="/health/", session=FakeSession(client_id=1, role="patient")
        )
        middleware = RequestAuditMiddleware(lambda request: HttpResponse("ok", status=200))
        with patch("core.middleware.logger.info") as log:
            response = middleware(request)
        self.assertEqual(response.status_code, 200)
        log.assert_called_once()
        self.assertEqual(log.call_args.args[1:4], ("GET", "/health/", 200))


class FormsRegressionTests(unittest.TestCase):
    def test_registration_password_mismatch(self):
        from core.web.forms import PatientRegistrationForm

        form = PatientRegistrationForm(
            data={
                "full_name": "Test",
                "email": "test@example.com",
                "password": "abcdef",
                "confirm_password": "abcdeg",
                "blood_group": "A+",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("confirm_password", form.errors)

    def test_availability_form_rejects_past_and_bad_time_order(self):
        from core.web.forms import AvailabilityForm

        form = AvailabilityForm(
            data={
                "available_date": (date.today() - timedelta(days=1)).isoformat(),
                "start_time": "10:00",
                "end_time": "09:00",
                "visiting_fee": "500",
                "is_active": "on",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("available_date", form.errors)
        self.assertIn("end_time", form.errors)

    def test_chatbot_form_enforces_500_character_limit(self):
        from core.web.forms import ChatbotForm

        self.assertTrue(ChatbotForm(data={"question": "x" * 500}).is_valid())
        form = ChatbotForm(data={"question": "x" * 501})
        self.assertFalse(form.is_valid())
        self.assertIn("500", form.errors["question"][0])

    def test_disease_form_requires_custom_name_for_other(self):
        from core.web.forms import DiseaseRecordForm

        other = SimpleNamespace(disease_id=99, disease_name="Other")
        manager = MagicMock()
        manager.filter.return_value.order_by.return_value = [other]
        with patch("core.web.forms.Disease.objects", manager):
            form = DiseaseRecordForm(data={"disease_id": "99", "current_status": "Active"})
            self.assertFalse(form.is_valid())
            self.assertIn("custom_disease_name", form.errors)


class RoutingTemplateAndSchemaRegressionTests(unittest.TestCase):
    def test_expected_routes_resolve(self):
        expected = [
            "/", "/login/", "/patient/dashboard/", "/doctor/dashboard/", "/admin-panel/dashboard/",
            "/api/health/", "/api/accounts/login/", "/api/doctors/availability/",
            "/api/master-data/", "/api/records/search/", "/api/approvals/users/", "/api/chatbot/ask/",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertIsNotNone(resolve(path).func)

    def test_all_literal_templates_referenced_by_web_views_exist_and_load(self):
        source = (BACKEND_ROOT / "core" / "web" / "views.py").read_text(encoding="utf-8")
        names = sorted(set(re.findall(r'["\']([^"\']+\.html)["\']', source)))
        self.assertGreaterEqual(len(names), 20)
        for name in names:
            with self.subTest(template=name):
                self.assertTrue((PROJECT_ROOT / "templates" / name).is_file(), name)
                get_template(name)

    def test_static_references_in_templates_exist(self):
        missing = []
        static_re = re.compile(r"\{%\s*static\s+['\"]([^'\"]+)['\"]\s*%\}")
        for template in (PROJECT_ROOT / "templates").rglob("*.html"):
            text = template.read_text(encoding="utf-8")
            for rel in static_re.findall(text):
                if not (PROJECT_ROOT / "static" / rel).is_file():
                    missing.append(f"{template.relative_to(PROJECT_ROOT)} -> {rel}")
        self.assertEqual(missing, [])

    def test_sql_schema_has_19_expected_tables(self):
        sql_path = BACKEND_ROOT / "database" / "medbaksho_corrected.sql"
        sql = sql_path.read_text(encoding="utf-8", errors="replace").lower()
        tables = re.findall(r"create\s+table\s+`?([a-z0-9_]+)`?", sql)
        expected = {
            "client", "admin", "patient", "doctor", "doctoravailability", "disease",
            "patientdisease", "medicalfacilitytype", "medicalfacility", "medicinebrand",
            "medicinetype", "medicine", "testcategory", "medicaltest", "prescription",
            "prescriptionmedicine", "prescriptiontest", "prescriptionimage", "medicinesubmission",
        }
        self.assertEqual(set(tables), expected)
        self.assertEqual(len(tables), 19)

    def test_required_schema_foreign_keys_are_present(self):
        sql = (BACKEND_ROOT / "database" / "medbaksho_corrected.sql").read_text(
            encoding="utf-8", errors="replace"
        ).lower()
        for token in [
            "verified_by_admin_id", "doctor_id", "patient_id", "patient_disease_id",
            "approved_medicine_id", "reviewed_by_admin_id",
        ]:
            with self.subTest(token=token):
                self.assertIn(token, sql)


class HealthAndApiViewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_health_endpoint_contract(self):
        from core.views import health

        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.__exit__.return_value = False
        with patch("core.views.connection.cursor", return_value=cursor):
            response = health(self.rf.get("/api/health/"))
        self.assertEqual(response.status_code, 200)
        payload = json_payload(response)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["database"], "connected")
        cursor.execute.assert_called_once_with("SELECT 1")

    def test_health_endpoint_reports_database_failure(self):
        from core.views import health

        with patch("core.views.connection.cursor", side_effect=RuntimeError("db down")):
            response = health(self.rf.get("/api/health/"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json_payload(response)["error"], "Database connection failed.")

    def test_chatbot_view_success_and_provider_failure_contracts(self):
        from core.chatbot import views

        # Unwrap csrf, require_POST, role_required to test endpoint body without DB identity queries.
        target = views.ask
        while hasattr(target, "__wrapped__"):
            target = target.__wrapped__
        request = self.rf.post(
            "/api/chatbot/ask/", data=json.dumps({"question": "hello"}), content_type="application/json"
        )
        request.client = SimpleNamespace(user_id=1, account_status="Active")
        request.patient = SimpleNamespace(user_id=1)
        proxy = Mock()
        proxy.answer.return_value = "answer"
        with patch("core.chatbot.views.build_chatbot_service", return_value=Mock()), \
             patch("core.chatbot.views.ChatbotProxy", return_value=proxy):
            response = target(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_payload(response)["data"]["answer"], "answer")

        proxy.answer.side_effect = RuntimeError("provider down")
        with patch("core.chatbot.views.build_chatbot_service", return_value=Mock()), \
             patch("core.chatbot.views.ChatbotProxy", return_value=proxy), \
             patch("core.chatbot.views.logger.exception"):
            response = target(request)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(json_payload(response)["ok"])

    def test_account_registration_body_requires_fields(self):
        from core.accounts import views

        target = views.register_patient
        while hasattr(target, "__wrapped__"):
            target = target.__wrapped__
        request = self.rf.post(
            "/api/accounts/register/patient/",
            data=json.dumps({"full_name": "Test"}),
            content_type="application/json",
        )
        response = target(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required fields", json_payload(response)["error"])

    def test_medicine_submission_requires_name(self):
        from core.records import views

        target = views.medicine_submission_create
        while hasattr(target, "__wrapped__"):
            target = target.__wrapped__
        request = self.rf.post(
            "/api/records/medicine-submissions/create/",
            data=json.dumps({}),
            content_type="application/json",
        )
        request.patient = SimpleNamespace(p_id=1)
        response = target(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("proposed_medicine_name", json_payload(response)["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
