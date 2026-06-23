from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MigrationTestCase(TestCase):

    def test_no_missing_migrations(self):
        """
        Checks that there are no model changes without a corresponding
        migration.
        """
        out = StringIO()

        try:
            call_command(
                'makemigrations',
                '--check',
                '--dry-run',
                stdout=out,
                stderr=out,
            )
        except SystemExit:
            self.fail('There are missing migrations:\n{}'.format(out.getvalue()))
