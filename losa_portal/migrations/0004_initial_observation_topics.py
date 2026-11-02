from django.db import migrations


def seed(apps, schema_editor):
    Topic = apps.get_model('losa_portal', 'ObservationTopic')
    for name in ['Подготовка и планирование', 'Взаимодействие экипажа', 'Управление нагрузкой',
                 'Перекрёстный контроль', 'Управление автоматикой', 'Выполнение процедур SOP',
                 'Принятие решений', 'Взаимодействие с ОрВД', 'Взаимодействие с кабинным экипажем',
                 'Погода и внешние условия']:
        Topic.objects.using(schema_editor.connection.alias).get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [('losa_portal', '0003_observationtopic_textobservation')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
