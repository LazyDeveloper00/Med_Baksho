from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from core.accounts.factories import AccountFactory


class Command(BaseCommand):
    help = "Create a Mediবাক্স admin account in the existing client/admin tables."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--phone", default="")

    def handle(self, *args, **options):
        try:
            client, admin = AccountFactory.create_account(
                "admin",
                full_name=options["name"],
                email=options["email"],
                password=options["password"],
                phone=options["phone"],
            )
        except (ValueError, IntegrityError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Created admin {client.email} with a_id={admin.a_id} and user_id={client.user_id}."
            )
        )
