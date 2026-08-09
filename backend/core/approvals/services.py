from typing import Iterable

from django.db import transaction
from django.utils import timezone

from core.approvals.observer import Observer
from core.models import (
    Admin,
    Doctor,
    Medicine,
    MedicineBrand,
    MedicineSubmission,
    MedicineType,
)


class ApprovalService:
    """Observer subject and approval workflow service."""

    def __init__(self, observers: Iterable[Observer] | None = None):
        self._observers = list(observers or [])

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, message: str, user) -> None:
        for observer in tuple(self._observers):
            observer.update(message, user)

    @transaction.atomic
    def approve_doctor(self, admin: Admin, doctor: Doctor, comments: str = "") -> Doctor:
        if doctor.verification_status != "Pending":
            raise ValueError("Only Pending doctor registrations can be approved.")
        doctor.verification_status = "Approved"
        doctor.verified_by_admin = admin
        doctor.verified_at = timezone.now()
        doctor.save(update_fields=["verification_status", "verified_by_admin", "verified_at"])
        self.notify_observers("Your doctor registration was approved.", doctor.user)
        return doctor

    @transaction.atomic
    def reject_doctor(self, admin: Admin, doctor: Doctor, comments: str = "") -> Doctor:
        if doctor.verification_status != "Pending":
            raise ValueError("Only Pending doctor registrations can be rejected.")
        doctor.verification_status = "Rejected"
        doctor.verified_by_admin = admin
        doctor.verified_at = timezone.now()
        doctor.save(update_fields=["verification_status", "verified_by_admin", "verified_at"])
        message = "Your doctor registration was rejected."
        if comments:
            message += f" Reason: {comments}"
        self.notify_observers(message, doctor.user)
        return doctor

    @transaction.atomic
    def approve_medicine(
        self,
        admin: Admin,
        submission: MedicineSubmission,
        *,
        med_type_id: int,
        brand_id: int | None = None,
        brand_name: str | None = None,
        comments: str = "",
    ) -> Medicine:
        if submission.status != "Pending":
            raise ValueError("Only Pending submissions can be approved.")
        med_type = MedicineType.objects.get(med_type_id=med_type_id)
        if brand_id:
            brand = MedicineBrand.objects.get(brand_id=brand_id)
        else:
            resolved_name = (brand_name or submission.med_brand_name or "Unknown").strip()
            brand, _ = MedicineBrand.objects.get_or_create(brand_name=resolved_name)

        medicine, _ = Medicine.objects.get_or_create(
            medicine_name=submission.proposed_medicine_name.strip(),
            med_brand=brand,
            med_type=med_type,
            defaults={
                "main_active_ingredient": submission.proposed_active_ingredient,
                "is_active": True,
            },
        )
        submission.status = "Approved"
        submission.reviewed_by_admin = admin
        submission.approved_medicine = medicine
        submission.reviewed_at = timezone.now()
        submission.review_comments = comments or None
        submission.save(
            update_fields=[
                "status",
                "reviewed_by_admin",
                "approved_medicine",
                "reviewed_at",
                "review_comments",
            ]
        )
        self.notify_observers(
            f"Your medicine submission '{submission.proposed_medicine_name}' was approved.",
            submission.patient.user,
        )
        return medicine

    @transaction.atomic
    def reject_medicine(
        self,
        admin: Admin,
        submission: MedicineSubmission,
        comments: str = "",
    ) -> MedicineSubmission:
        if submission.status != "Pending":
            raise ValueError("Only Pending submissions can be rejected.")
        submission.status = "Rejected"
        submission.reviewed_by_admin = admin
        submission.reviewed_at = timezone.now()
        submission.review_comments = comments or None
        submission.save(
            update_fields=["status", "reviewed_by_admin", "reviewed_at", "review_comments"]
        )
        message = f"Your medicine submission '{submission.proposed_medicine_name}' was rejected."
        if comments:
            message += f" Reason: {comments}"
        self.notify_observers(message, submission.patient.user)
        return submission
