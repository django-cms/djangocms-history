#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

    import django
    from django.test.runner import DiscoverRunner

    django.setup()

    runner = DiscoverRunner(verbosity=1)
    failures = runner.run_tests(sys.argv[1:] or ['tests'])
    sys.exit(bool(failures))


if __name__ == '__main__':
    main()
