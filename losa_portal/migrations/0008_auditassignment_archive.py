import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('losa_portal', '0007_cyclereport'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='auditassignment', name='archived_at', field=models.DateTimeField('Отправлено в архив', null=True, blank=True, db_index=True, editable=False)),
        migrations.AddField(model_name='auditassignment', name='archived_by', field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name='archived_losa_assignments', verbose_name='Кто архивировал', editable=False)),
        migrations.AddField(model_name='auditassignment', name='archived_cycle', field=models.ForeignKey(to='losa_portal.roundtablecycle', on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name='archived_assignments', verbose_name='Цикл архивирования', editable=False)),
        migrations.AddField(model_name='auditassignment', name='archived_report', field=models.ForeignKey(to='losa_portal.cyclereport', on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name='archived_assignments', verbose_name='Отчет при архивировании', editable=False)),
        migrations.AddConstraint(model_name='auditassignment', constraint=models.CheckConstraint(
            condition=(models.Q(archived_at__isnull=True, archived_by__isnull=True, archived_cycle__isnull=True, archived_report__isnull=True)
                | models.Q(archived_at__isnull=False, archived_by__isnull=False, archived_cycle__isnull=False, archived_report__isnull=False, status='completed')),
            name='portal_archive_consistent')),
    ]
