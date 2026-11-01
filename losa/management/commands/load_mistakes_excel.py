from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from losa.models import Mistake, MistakeSection, MistakeType


class Command(BaseCommand):
    help = "Загрузка ошибок и разделов из Excel"

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--sheet", help="Название листа")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Проверить без сохранения",
        )

    @staticmethod
    def as_text(value):
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    def handle(self, *args, **options):
        file_path = options["file"].expanduser()

        if not file_path.is_file():
            raise CommandError(f"Файл не найден: {file_path}")

        try:
            workbook = load_workbook(
                file_path,
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
            raise CommandError("Нет записей для загрузки.")

        created_count = 0
        updated_count = 0
        section_count = 0

        try:
            with transaction.atomic():
                types = {
                    obj.code: obj
                    for obj in MistakeType.objects.all()
                }

                for row_number, data in records:
                    mistake_type = types.get(data["type_code"])

                    if mistake_type is None:
                        raise CommandError(
                            f"Строка {row_number}: тип "
                            f"{data['type_code']} отсутствует в БД."
                        )

                    section, section_created = (
                        MistakeSection.objects.get_or_create(
                            type=mistake_type,
                            name=data["section"],
                        )
                    )

                    if section_created:
                        section_count += 1

                    section.full_clean()

                    obj = Mistake.objects.filter(
                        code=data["code"],
                    ).first()

                    if obj is None:
                        obj = Mistake(code=data["code"])
                        created_count += 1
                    else:
                        updated_count += 1

                    obj.name = data["name"]
                    obj.type = mistake_type
                    obj.section = section

                    obj.full_clean()
                    obj.save()

                if options["dry_run"]:
                    transaction.set_rollback(True)

        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(
                f"Импорт отменён, изменения не сохранены: {exc}"
            ) from exc

        action = (
            "Проверка завершена, данные не сохранены"
            if options["dry_run"]
            else "Загрузка завершена"
        )
        self.stdout.write(self.style.SUCCESS(
            f"{action}. Новых ошибок: {created_count}; "
            f"существующих: {updated_count}; "
            f"новых разделов: {section_count}."
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

        required = ("code", "name", "type_code", "section")
        missing = [name for name in required if name not in columns]

        if missing:
            raise CommandError(
                f"Отсутствуют колонки: {', '.join(missing)}"
            )

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
                        f"Строка {row_number}: поле {name} не заполнено."
                    )

            code = data["code"]

            if code in seen_codes:
                raise CommandError(
                    f"Код {code} повторяется в строках "
                    f"{seen_codes[code]} и {row_number}."
                )

            seen_codes[code] = row_number
            records.append((row_number, data))

        return records