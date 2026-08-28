from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from django.db import transaction

from core.models import (
    MedicalFacility,
    MedicalTest,
    Medicine,
    PatientDisease,
    Prescription,
    PrescriptionImage,
    PrescriptionMedicine,
    PrescriptionTest,
)

def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _as_optional_date(value: Any, field_name: str):
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.") from exc


def _as_required_date(value: Any, field_name: str):
    result = _as_optional_date(value, field_name)
    if result is None:
        raise ValueError(f"{field_name} is required.")
    return result


@dataclass
class PrescriptionBuilder:
    """Builder Pattern: creates a prescription and its optional child records."""

    patient_disease: PatientDisease
    base_data: dict[str, Any] = field(default_factory=dict)
    medicines: list[dict[str, Any]] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)

    def set_base(self, **data: Any) -> "PrescriptionBuilder":
        self.base_data.update(data)
        return self

    def add_medicine(self, **data: Any) -> "PrescriptionBuilder":
        self.medicines.append(data)
        return self

    def add_test(self, **data: Any) -> "PrescriptionBuilder":
        self.tests.append(data)
        return self

    def add_image(self, **data: Any) -> "PrescriptionBuilder":
        self.images.append(data)
        return self

    def _validate(self) -> None:
        required = ("prescription_date", "doctor_name")
        missing = [field for field in required if not self.base_data.get(field)]
        if missing:
            raise ValueError("Missing prescription fields: " + ", ".join(missing))
        if not self.base_data.get("facility_id") and not self.base_data.get("custom_facility_name"):
            raise ValueError("Select a facility or provide custom_facility_name.")

    @transaction.atomic
    def build(self) -> Prescription:
        self._validate()
        facility = None
        if self.base_data.get("facility_id"):
            facility = MedicalFacility.objects.get(
                facility_id=self.base_data["facility_id"], is_active=True
            )

        prescription = Prescription.objects.create(
            patient_disease=self.patient_disease,
            facility=facility,
            prescription_date=_as_required_date(self.base_data["prescription_date"], "prescription_date"),
            doctor_name=str(self.base_data["doctor_name"]).strip(),
            custom_facility_name=(self.base_data.get("custom_facility_name") or "").strip()
            or None,
            illness_location=(self.base_data.get("illness_location") or "").strip() or None,
            advice=(self.base_data.get("advice") or "").strip() or None,
            additional_notes=(self.base_data.get("additional_notes") or "").strip() or None,
        )

        for data in self.medicines:
            medicine = Medicine.objects.get(medicine_id=data["medicine_id"], is_active=True)
            times_per_day = int(data["times_per_day"])
            duration_days = int(data["duration_days"])
            if times_per_day <= 0 or duration_days <= 0:
                raise ValueError("times_per_day and duration_days must be greater than zero.")
            start_date = _as_optional_date(data.get("start_date"), "start_date")
            end_date = _as_optional_date(data.get("end_date"), "end_date")
            if start_date and end_date and end_date < start_date:
                raise ValueError("Medicine end_date cannot be earlier than start_date.")
            PrescriptionMedicine.objects.create(
                prescription=prescription,
                medicine=medicine,
                dosage=str(data["dosage"]).strip(),
                times_per_day=times_per_day,
                duration_days=duration_days,
                start_date=start_date,
                end_date=end_date,
                course_completed=_as_bool(data.get("course_completed", False)),
                side_effects=(data.get("side_effects") or "").strip() or None,
                effectiveness=(data.get("effectiveness") or "Unknown").strip(),
            )

        for data in self.tests:
            test = MedicalTest.objects.get(test_id=data["test_id"], is_active=True)
            PrescriptionTest.objects.create(
                prescription=prescription,
                test=test,
                completion_status=(data.get("completion_status") or "Recommended").strip(),
                test_date=_as_optional_date(data.get("test_date"), "test_date"),
                diagnostic_center_name=(data.get("diagnostic_center_name") or "").strip()
                or None,
                result_summary=(data.get("result_summary") or "").strip() or None,
                custom_test_name=(data.get("custom_test_name") or "").strip() or None,
            )

        for data in self.images:
            PrescriptionImage.objects.create(
                prescription=prescription,
                file_path=data["file_path"],
                file_size_kb=data.get("file_size_kb"),
            )

        return prescription
