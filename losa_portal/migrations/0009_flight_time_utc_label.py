from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("losa_portal", "0008_auditassignment_archive")]
    operations = [migrations.AlterField(model_name="flight", name="time",
        field=models.TimeField(verbose_name="Время вылета (UTC)"))]
