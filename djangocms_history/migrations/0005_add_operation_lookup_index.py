from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djangocms_history', '0004_hash_session_keys'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='placeholderoperation',
            index=models.Index(
                fields=['user_session_key', 'origin', 'date_created'],
                name='history_op_lookup_idx',
            ),
        ),
    ]
