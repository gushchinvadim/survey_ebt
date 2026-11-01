from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from openpyxl import load_workbook

from losa.models import ChangingSafetyConditionSheet


class Command(BaseCommand):
    help = "Загрузка кодов изменения состояния безопасности ВС из Excel"

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

        try:
            with transaction.atomic():
                for row_number, data in records:
                    matches = ChangingSafetyConditionSheet.objects.filter(
                        code=data["code"],
                    )

                    if matches.count() > 1:
                        raise CommandError(
                            f"Строка {row_number}: в БД несколько записей "
                            f"с кодом {data['code']}."
                        )

                    obj = matches.first()

                    if obj is None:
                        obj = ChangingSafetyConditionSheet(
                            code=data["code"],
                        )
                        created_count += 1
                    else:
                        updated_count += 1

                    obj.section = data["section"]
                    obj.name = data["name"]

                    try:
                        obj.full_clean()
                        obj.save()
                    except Exception as exc:
                        raise CommandError(
                            f"Строка {row_number}, "
                            f"код {data['code']}: {exc}"
                        ) from exc

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
            f"{action}. Новых: {created_count}; "
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

        required = ("code", "section", "name")
        missing = [name for name in required if name not in columns]

        if missing:
            raise CommandError(
                f"Отсутствуют колонки: {', '.join(missing)}"
            )

        allowed_sections = {
            str(code)
            for code, _ in ChangingSafetyConditionSheet.SECTION_CHOICES
        }

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

            try:
                code = int(data["code"])
            except ValueError as exc:
                raise CommandError(
                    f"Строка {row_number}: код должен быть целым числом."
                ) from exc

            if code < 0:
                raise CommandError(
                    f"Строка {row_number}: код не может быть отрицательным."
                )

            if code in seen_codes:
                raise CommandError(
                    f"Код {code} повторяется в строках "
                    f"{seen_codes[code]} и {row_number}."
                )

            if data["section"] not in allowed_sections:
                raise CommandError(
                    f"Строка {row_number}: неизвестный раздел "
                    f"'{data['section']}'. Допустимы: 1, 2, 3."
                )

            seen_codes[code] = row_number
            data["code"] = code
            records.append((row_number, data))

        return records