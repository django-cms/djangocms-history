from django.db import migrations


def delete_cms3_history(apps, schema_editor):
    """
    Deletes all recorded operations.

    Operations recorded with django CMS 3.x store treebeard-era plugin
    snapshots (per-parent positions and tree order lists) which cannot
    be replayed against the position-based plugin tree of django CMS 4+.
    History is ephemeral by design (the undo window is 24 hours), so the
    records are dropped on upgrade.
    """
    PlaceholderOperation = apps.get_model('djangocms_history', 'PlaceholderOperation')
    PlaceholderOperation.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('djangocms_history', '0002_auto_20170606_1001'),
    ]

    operations = [
        migrations.RunPython(delete_cms3_history, migrations.RunPython.noop),
    ]
