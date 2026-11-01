import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Count


TYPE_CHOICES = [
    ("1", "Преднамеренное нарушение"),
    ("2", "Процедурная ошибка"),
    ("3", "Коммуникационная ошибка"),
    ("4", "Профессиональная ошибка"),
    ("5", "Ошибка в принятии решения"),
]


def transfer_mistakes(apps, schema_editor):
    Mistake = apps.get_model("losa", "Mistake")
    MistakeType = apps.get_model("losa", "MistakeType")
    database = schema_editor.connection.alias

    mistakes = Mistake.objects.using(database)
    types = MistakeType.objects.using(database)

    # Проверяем данные до изменения существующих записей.
    duplicates = list(
        mistakes.values("code")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
        .values_list("code", flat=True)
    )
    if duplicates:
        raise RuntimeError(
            f"Повторяющиеся коды ошибок: {duplicates}. "
            "Устраните дубли перед повторным запуском миграции."
        )

    valid_codes = {code for code, _ in TYPE_CHOICES}

    for mistake in mistakes.all().iterator():
        old_code = str(mistake.type or "").strip()
        if old_code not in valid_codes:
            raise RuntimeError(
                f"Ошибка id={mistake.pk}: неизвестная категория "
                f"{mistake.type!r}. Укажите категорию 1–5."
            )

    type_by_code = {}
    descriptions = {code: [] for code in valid_codes}

    for code, _ in TYPE_CHOICES:
        type_obj, _ = types.get_or_create(
            code=code,
            defaults={"describe": ""},
        )
        type_by_code[code] = type_obj

    for mistake in mistakes.all().iterator():
        old_code = str(mistake.type).strip()
        description = mistake.describe or ""

        # Сохраняем все различные старые пояснения категории.
        if description and description not in descriptions[old_code]:
            descriptions[old_code].append(description)

        mistake.new_type_id = type_by_code[old_code].pk

        # Названия конкретных ошибок из старой структуры неизвестны.
        # Временно обозначаем их кодом; Excel затем заполнит названия.
        mistake.name = f"Ошибка {mistake.code}"

        mistake.save(
            using=database,
            update_fields=["new_type", "name"],
        )

    for code, type_obj in type_by_code.items():
        type_obj.describe = "\n\n".join(descriptions[code])
        type_obj.save(
            using=database,
            update_fields=["describe"],
        )


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("losa", "0012_auditthreat_correct_actions_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MistakeType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        "Тип ошибки",
                        max_length=1,
                        choices=TYPE_CHOICES,
                        unique=True,
                    ),
                ),
                (
                    "describe",
                    models.TextField(
                        "Пояснение к типу",
                        blank=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Тип ошибки",
                "verbose_name_plural": "Типы ошибок",
                "ordering": ["code"],
            },
        ),

        # Добавляем новые поля, сохраняя старые до переноса.
        migrations.AddField(
            model_name="mistake",
            name="name",
            field=models.CharField(
                "Название ошибки",
                max_length=300,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="mistake",
            name="new_type",
            field=models.ForeignKey(
                to="losa.mistaketype",
                verbose_name="Тип ошибки",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mistakes",
                null=True,
            ),
        ),

        migrations.RunPython(transfer_mistakes),

        # Теперь старые данные перенесены.
        migrations.RemoveField(
            model_name="mistake",
            name="type",
        ),
        migrations.RenameField(
            model_name="mistake",
            old_name="new_type",
            new_name="type",
        ),
        migrations.RemoveField(
            model_name="mistake",
            name="describe",
        ),

        migrations.AlterField(
            model_name="mistake",
            name="name",
            field=models.CharField(
                "Название ошибки",
                max_length=300,
            ),
        ),
        migrations.AlterField(
            model_name="mistake",
            name="type",
            field=models.ForeignKey(
                to="losa.mistaketype",
                verbose_name="Тип ошибки",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mistakes",
            ),
        ),
        migrations.AlterField(
            model_name="mistake",
            name="code",
            field=models.CharField(
                "Код ошибки",
                max_length=100,
                unique=True,
            ),
        ),
        migrations.AlterModelOptions(
            name="mistake",
            options={
                "ordering": ["type__code", "code"],
                "verbose_name": "Ошибка",
                "verbose_name_plural": "Ошибки",
            },
        ),
    ]