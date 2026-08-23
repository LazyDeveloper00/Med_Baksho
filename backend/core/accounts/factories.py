from abc import ABC, abstractmethod
from typing import Any, ClassVar, Optional

from django.contrib.auth.hashers import make_password
from django.db import transaction

from core.models import Admin, Client, Doctor, Patient


class AccountRole(ABC):
    """Abstract Product interface matching Step 1 of the Factory pattern."""
    pass


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
    def create_role(self, *, client: Client, **data: Any) -> AccountRole:
        raise NotImplementedError


class PatientAccountCreator(AccountCreator):
    def create_role(self, *, client: Client, **data: Any) -> AccountRole:
        return Patient.objects.create(
            user=client,
            date_of_birth=data.get("date_of_birth") or None,
            blood_group=(data.get("blood_group") or "").strip() or None,
            address=(data.get("address") or "").strip() or None,
        )


class DoctorAccountCreator(AccountCreator):
    def create_role(self, *, client: Client, **data: Any) -> AccountRole:
        return Doctor.objects.create(
            user=client,
            licence_number=data["licence_number"].strip(),
            degree=(data.get("degree") or "").strip() or None,
            field_of_expertise=(data.get("field_of_expertise") or "").strip() or None,
            workplace=(data.get("workplace") or "").strip() or None,
            verification_status="Pending",
        )


class AdminAccountCreator(AccountCreator):
    def create_role(self, *, client: Client, **data: Any) -> AccountRole:
        return Admin.objects.create(user=client)


class AccountFactory:
    """Singleton factory supporting direct class invocation and static instance getters."""

    _instance: ClassVar[Optional["AccountFactory"]] = None
    _creators: ClassVar[dict[str, type[AccountCreator]]] = {
        "patient": PatientAccountCreator,
        "doctor": DoctorAccountCreator,
        "admin": AdminAccountCreator,
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "AccountFactory":
        """Matches Logger::getLogger() access pattern."""
        return cls()

    @classmethod
    def create_account(cls, role: str, *, password: str, **data: Any):
        """Class method wrapper resolving the Singleton instance automatically."""
        instance = cls.get_instance()
        creator_class = instance._creators[role.strip().lower()]
        return creator_class().create(password=password, **data)