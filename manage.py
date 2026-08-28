#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medibaksho_backend.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django is not installed. Activate the virtual environment and run "
            "'py -m pip install -r requirements.txt'."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
