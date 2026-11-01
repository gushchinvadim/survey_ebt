# losa/management/commands/load_exel.py

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from losa.models import Threat


class Command(BaseCommand):
    help = "Загрузка справочника угроз из Excel (.xlsx)"

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path, help="Путь к Excel-файлу")
        parser.add_argument("--sheet", help="Название листа Excel")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Проверить файл без сохранения в БД",
        )

    def handle(self, *args, **options):
        path = options["file"].expanduser()

        if not path.is_file():
            raise CommandError(f"Файл не найден: {path}")

        try:
            workbook = load_workbook(
                path,
                read_only=True,
                data_only=True,
            )
        except Exception as exc:
            raise CommandError(f"Не удалось открыть Excel: {exc}") from exc

        try:
            sheet_name = options["sheet"]

            if sheet_name:
                if sheet_name not in workbook.sheetnames:
                    raise CommandError(f"Лист не найден: {sheet_name}")
                sheet = workbook[sheet_name]
            else:
                sheet = workbook.active

            records = self.read_records(sheet)
        finally:
            workbook.close()

        if not records:
            raise CommandError("В файле нет записей для загрузки.")

        created_count = 0
        updated_count = 0

        # Любая ошибка отменяет сохранение всего файла.
        try:
            with transaction.atomic():
                for row_number, data in records:
                    matches = Threat.objects.filter(code=data["code"])

                    if matches.count() > 1:
                        raise CommandError(
                            f"Строка {row_number}: в БД несколько угроз "
                            f"с кодом {data['code']}."
                        )

                    obj = matches.first()

                    if obj is None:
                        obj = Threat(code=data["code"])
                        created_count += 1
                    else:
                        updated_count += 1

                    obj.type = data["type"]
                    obj.describe = data["describe"]

                    # Проверка choices, длины полей и ограничений модели.
                    obj.full_clean()
                    obj.save()

                if options["dry_run"]:
                    transaction.set_rollback(True)

        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f"Загрузка отменена, изменения не сохранены: {exc}"
            ) from exc

        prefix = "Проверка завершена" if options["dry_run"] else "Загрузка завершена"
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}. Новых: {created_count}; "
            f"существующих: {updated_count}."
        ))

    def read_records(self, sheet):
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)

        if header is None:
            raise CommandError("Лист пустой.")

        columns = {}
        for index, value in enumerate(header):
            name = self.as_text(value).lower()
            if not name:
                continue
            if name in columns:
                raise CommandError(f"Повторяющийся заголовок: {name}")
            columns[name] = index

        required = ("code", "type", "describe")
        missing = [name for name in required if name not in columns]

        if missing:
            raise CommandError(
                f"Не найдены колонки: {', '.join(missing)}"
            )

        # Принимаем коды или русские подписи из текущей модели.
        category_map = {}
        for code, label in Threat.THREAT_TYPE_CHOICES:
            category_map[str(code).strip().casefold()] = str(code)
            category_map[str(label).strip().casefold()] = str(code)

        records = []
        seen_codes = {}

        for row_number, row in enumerate(rows, start=2):
            if all(self.as_text(value) == "" for value in row):
                continue

            data = {
                name: self.as_text(row[columns[name]])
                for name in required
            }

            for name, value in data.items():
                if not value:
                    raise CommandError(
                        f"Строка {row_number}: пустое поле {name}."
                    )

            code = data["code"]
            if code in seen_codes:
                raise CommandError(
                    f"Код {code} повторяется в строках "
                    f"{seen_codes[code]} и {row_number}."
                )
            seen_codes[code] = row_number

            category = category_map.get(data["type"].casefold())
            if category is None:
                raise CommandError(
                    f"Строка {row_number}: неизвестная категория "
                    f"'{data['type']}'."
                )

            data["type"] = category
            records.append((row_number, data))

        return records

    @staticmethod
    def as_text(value):
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()