from pathlib import Path
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import QuerySet

from core.models import Patient, PatientDisease, Prescription
from core.records.builders import PrescriptionBuilder


class MedicalRecordFacade:
    """Facade Pattern: one simple API for medical-record workflows."""

    @staticmethod
    def create_prescription(
        *,
        patient: Patient,
        patient_disease_id: int,
        base_data: dict[str, Any],
        medicines: list[dict[str, Any]],
        tests: list[dict[str, Any]],
        uploaded_file=None,
    ) -> Prescription:
        patient_disease = PatientDisease.objects.get(
            patient_disease_id=patient_disease_id,
            patient=patient,
        )
        builder = PrescriptionBuilder(patient_disease).set_base(**base_data)

        for medicine in medicines:
            builder.add_medicine(**medicine)
        for test in tests:
            builder.add_test(**test)

        saved_path = None
        if uploaded_file is not None:
            MedicalRecordFacade._validate_png(uploaded_file)
            saved_path = default_storage.save(
                f"prescriptions/{uuid4().hex}.png",
                uploaded_file,
            )
            builder.add_image(
                file_path=saved_path,
                file_size_kb=max(1, uploaded_file.size // 1024),
            )

        try:
            return builder.build()
        except Exception:
            if saved_path and default_storage.exists(saved_path):
                default_storage.delete(saved_path)
            raise

    @staticmethod
    def _validate_png(uploaded_file) -> None:
        extension = Path(uploaded_file.name).suffix.lower()
        content_type = getattr(uploaded_file, "content_type", "")
        max_size = settings.MAX_PNG_MB * 1024 * 1024
        if extension != ".png" or content_type not in {"image/png", "application/octet-stream"}:
            raise ValueError("Only PNG prescription images are accepted.")
        if uploaded_file.size > max_size:
            raise ValueError(f"PNG file must be at most {settings.MAX_PNG_MB} MB.")

    @staticmethod
    def patient_prescriptions(patient: Patient) -> QuerySet:
        return Prescription.objects.select_related(
            "patient_disease__disease", "facility"
        ).filter(patient_disease__patient=patient)

    @staticmethod
    def search(
        *,
        patient: Patient,
        disease_id: str | None = None,
        medicine_id: str | None = None,
        test_id: str | None = None,
        facility_id: str | None = None,
    ) -> QuerySet:
        queryset = MedicalRecordFacade.patient_prescriptions(patient)
        if disease_id:
            queryset = queryset.filter(patient_disease__disease_id=disease_id)
        if medicine_id:
            queryset = queryset.filter(medicine_entries__medicine_id=medicine_id)
        if test_id:
            queryset = queryset.filter(test_entries__test_id=test_id)
        if facility_id:
            queryset = queryset.filter(facility_id=facility_id)
        return queryset.distinct().order_by("-prescription_date", "-prescription_id")
