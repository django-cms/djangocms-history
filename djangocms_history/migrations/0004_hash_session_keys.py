import hashlib

from django.db import migrations, models


HASH_PREFIX = "sha256$"


def hash_session_keys(apps, schema_editor):
    PlaceholderOperation = apps.get_model("djangocms_history", "PlaceholderOperation")
    for operation in PlaceholderOperation.objects.only("pk", "user_session_key").iterator():
        if operation.user_session_key.startswith(HASH_PREFIX):
            continue
        digest = hashlib.sha256(operation.user_session_key.encode()).hexdigest()
        operation.user_session_key = HASH_PREFIX + digest
        operation.save(update_fields=["user_session_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("djangocms_history", "0003_delete_cms3_history"),
    ]

    operations = [
        migrations.RunPython(hash_session_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="placeholderoperation",
            name="user_session_key",
            field=models.CharField(db_index=True, max_length=72),
        ),
    ]
