from __future__ import annotations

from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from djangocms_history.models import PlaceholderOperation


class Command(BaseCommand):
    help = (
        'Delete archived placeholder operations (and their actions). '
        'Archived operations are never reused by undo/redo, so removing '
        'them is safe and only reclaims database space.'
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            metavar='N',
            help='Only purge archived operations older than N days.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be deleted without deleting anything.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        queryset = PlaceholderOperation.objects.filter(is_archived=True)

        days = options['days']
        if days is not None:
            cutoff = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(date_created__lt=cutoff)

        count = queryset.count()

        if options['dry_run']:
            self.stdout.write(
                '{} archived operation(s) would be deleted.'.format(count)
            )
            return

        queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                'Deleted {} archived operation(s).'.format(count)
            )
        )
