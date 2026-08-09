from datetime import date, datetime

from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.decorators import role_required
from core.http import fail, ok, parse_json_list, read_payload
from core.models import (
    Disease,
    MedicalFacility,
    MedicalTest,
    Medicine,
    MedicineSubmission,
    PatientDisease,
    Prescription,
)
from core.records.facades import MedicalRecordFacade
from core.serializers import patient_disease_dict, prescription_dict, submission_dict


def _optional_date(value, field_name: str):
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.") from exc


@require_GET
@role_required("patient")
def disease_records(request):
    items = PatientDisease.objects.select_related("disease").filter(patient=request.patient)
    return ok([patient_disease_dict(item) for item in items.order_by("-patient_disease_id")])


@csrf_exempt
@require_POST
@role_required("patient")
def disease_create(request):
    try:
        data = read_payload(request)
        try:
            disease_id = int(data["disease_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("disease_id must be an integer.") from exc
        diagnosed_date = _optional_date(data.get("diagnosed_date"), "diagnosed_date")
        if diagnosed_date and diagnosed_date > date.today():
            raise ValueError("diagnosed_date cannot be in the future.")
        disease = Disease.objects.get(disease_id=disease_id, is_active=True)
        item = PatientDisease.objects.create(
            patient=request.patient,
            disease=disease,
            diagnosed_date=diagnosed_date,
            current_status=(data.get("current_status") or "Active").strip(),
            custom_disease_name=(data.get("custom_disease_name") or "").strip() or None,
            notes=(data.get("notes") or "").strip() or None,
        )
        return ok(patient_disease_dict(item), 201)
    except KeyError as exc:
        return fail(f"Missing required field: {exc.args[0]}", 400)
    except ValueError as exc:
        return fail(str(exc), 400)
    except Disease.DoesNotExist:
        return fail("Disease not found or inactive.", 404)


@require_GET
@role_required("patient")
def prescription_list(request):
    queryset = MedicalRecordFacade.patient_prescriptions(request.patient).order_by(
        "-prescription_date", "-prescription_id"
    )
    return ok([prescription_dict(item) for item in queryset])


@csrf_exempt
@require_POST
@role_required("patient")
def prescription_create(request):
    try:
        data = read_payload(request)
        medicines = parse_json_list(data.get("medicines"), "medicines")
        tests = parse_json_list(data.get("tests"), "tests")
        patient_disease_id = int(data["patient_disease_id"])
        base_data = {
            key: data.get(key)
            for key in (
                "facility_id",
                "prescription_date",
                "doctor_name",
                "custom_facility_name",
                "illness_location",
                "advice",
                "additional_notes",
            )
        }
        prescription = MedicalRecordFacade.create_prescription(
            patient=request.patient,
            patient_disease_id=patient_disease_id,
            base_data=base_data,
            medicines=medicines,
            tests=tests,
            uploaded_file=request.FILES.get("image"),
        )
        prescription = Prescription.objects.select_related(
            "patient_disease__disease", "facility"
        ).get(prescription_id=prescription.prescription_id)
        return ok(prescription_dict(prescription, include_children=True), 201)
    except KeyError as exc:
        return fail(f"Missing required field: {exc.args[0]}", 400)
    except (ValueError, IntegrityError) as exc:
        return fail(str(exc), 400)
    except PatientDisease.DoesNotExist:
        return fail("Patient-disease record not found.", 404)
    except MedicalFacility.DoesNotExist:
        return fail("Selected medical facility was not found or is inactive.", 404)
    except Medicine.DoesNotExist:
        return fail("Selected medicine was not found or is inactive.", 404)
    except MedicalTest.DoesNotExist:
        return fail("Selected medical test was not found or is inactive.", 404)


@require_GET
@role_required("patient")
def prescription_detail(request, prescription_id: int):
    try:
        item = MedicalRecordFacade.patient_prescriptions(request.patient).get(
            prescription_id=prescription_id
        )
        return ok(prescription_dict(item, include_children=True))
    except Prescription.DoesNotExist:
        return fail("Prescription not found.", 404)


@require_GET
@role_required("patient")
def prescription_search(request):
    try:
        queryset = MedicalRecordFacade.search(
            patient=request.patient,
            disease_id=request.GET.get("disease_id"),
            medicine_id=request.GET.get("medicine_id"),
            test_id=request.GET.get("test_id"),
            facility_id=request.GET.get("facility_id"),
        )
        return ok([prescription_dict(item) for item in queryset])
    except ValueError as exc:
        return fail(str(exc), 400)


@csrf_exempt
@require_POST
@role_required("patient")
def medicine_submission_create(request):
    try:
        data = read_payload(request)
        name = (data.get("proposed_medicine_name") or "").strip()
        if not name:
            return fail("proposed_medicine_name is required.", 400)
        item = MedicineSubmission.objects.create(
            patient=request.patient,
            proposed_medicine_name=name,
            med_brand_name=(data.get("med_brand_name") or "").strip() or None,
            proposed_active_ingredient=(data.get("proposed_active_ingredient") or "").strip()
            or None,
            status="Pending",
        )
        return ok(submission_dict(item), 201)
    except ValueError as exc:
        return fail(str(exc), 400)


@require_GET
@role_required("patient")
def medicine_submission_list(request):
    queryset = MedicineSubmission.objects.select_related("patient__user").filter(
        patient=request.patient
    )
    return ok([submission_dict(item) for item in queryset.order_by("-submitted_at")])
