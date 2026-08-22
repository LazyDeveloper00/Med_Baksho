from abc import ABC, abstractmethod
from typing import Any, ClassVar

from django.contrib.auth.hashers import make_password
from django.db import transaction

from core.models import Admin, Client, Doctor, Patient


class AccountCreator(ABC):
    """Creator base class used by the Factory Method implementation."""

    @transaction.atomic
    def create(self, *, password: str, **data: Any):
        client = Client.objects.create(
            full_name=data["full_name"].strip(),
            email=data["email"].strip().lower(),
            phone=(data.get("phone") or "").strip() or None,
            password_hash=make_password(password),
            account_status="Active",
        )
        return client, self.create_role(client=client, **data)

    @abstractmethod
    def create_role(self, *, client: Client, **data: Any):
        raise NotImplementedError


class PatientAccountCreator(AccountCreator):
    def create_role(self, *, client: Client, **data: Any) -> Patient:
        return Patient.objects.create(
            user=client,
            date_of_birth=data.get("date_of_birth") or None,
            blood_group=(data.get("blood_group") or "").strip() or None,
            address=(data.get("address") or "").strip() or None,
        )


class DoctorAccountCreator(AccountCreator):
    def create_role(self, *, client: Client, **data: Any) -> Doctor:
        return Doctor.objects.create(
            user=client,
            licence_number=data["licence_number"].strip(),
            degree=(data.get("degree") or "").strip() or None,
            field_of_expertise=(data.get("field_of_expertise") or "").strip() or None,
            workplace=(data.get("workplace") or "").strip() or None,
            verification_status="Pending",
        )


class AdminAccountCreator(AccountCreator):
    def create_role(self, *, client: Client, **data: Any) -> Admin:
        return Admin.objects.create(user=client)


class AccountFactory:
    """Branch-free factory: role names resolve directly through a creator registry."""

    _creators: ClassVar[dict[str, type[AccountCreator]]] = {
        "patient": PatientAccountCreator,
        "doctor": DoctorAccountCreator,
        "admin": AdminAccountCreator,
    }

    @classmethod
    def create_account(cls, role: str, *, password: str, **data: Any):
        creator_class = cls._creators[role.strip().lower()]
        return creator_class().create(password=password, **data)
