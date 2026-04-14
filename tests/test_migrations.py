from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_missing_migrations():
    """
    Checks if there are any changes in models that aren't reflected in migrations.
    """
    out = StringIO()

    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
    except SystemExit as e:
        pytest.fail(f"There are missing migrations:\n{out.getvalue()}")
    except Exception as e:
        pytest.fail(f"Migration check failed with unexpected error: {e}")
