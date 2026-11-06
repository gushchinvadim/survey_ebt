"""Minimal LOSA reports: coordinator-only publication and frozen download data."""
from collections import Counter
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from rest_framework import serializers

from losa.models import AuditThreat, AuditMistake
from .analytics import coordinator_required
from .models import RoundTableCycle, CycleReport
from .round_table import cycle_view
from .views import read_json
from .pdf_charts import metric_cards, prevalence_chart, percentage, BLUE, AMBER, CORAL


class PublicationInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    summary = serializers.CharField(max_length=6000)
    conclusions = serializers.CharField(max_length=20000)
    limitations = serializers.CharField(max_length=6000)
    decisions = serializers.CharField(max_length=20000)
    anonymized = serializers.BooleanField()


def report_row(report):
    return {'id': report.pk, 'version': report.version, 'created_at': report.created_at.isoformat()}


def event_summary(query, field):
    counts = Counter()
    sheets = {}
    for item in query.select_related(field):
        label = str(getattr(item, field))
        counts[label] += 1
        sheets.setdefault(label, set()).add(item.audit_sheet_id)
    return [{'name': label, 'events': count, 'sheets': len(sheets[label])}
            for label, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]


@never_cache
@require_http_methods(['GET', 'POST'])
@csrf_protect
@coordinator_required
def reports_view(request, pk):
    with transaction.atomic():
        cycle = get_object_or_404(RoundTableCycle.objects.select_for_update(), pk=pk)
        if request.method == 'GET':
            return JsonResponse({'reports': [report_row(r) for r in cycle.reports.all()],
                                 'latest': cycle.reports.first().payload if cycle.reports.exists() else None})
        form = PublicationInput(data=read_json(request))
        if not form.is_valid():
            return JsonResponse({'detail': 'Заполните резюме, выводы, ограничения и решения.', 'errors': form.errors}, status=400)
        values = form.validated_data
        if not cycle.closed or values['revision'] != cycle.revision:
            return JsonResponse({'detail': 'Завершите обсуждение и обновите страницу перед выпуском.'}, status=409)
        if not values['anonymized']:
            return JsonResponse({'detail': 'Проверьте обезличивание введённых текстов.'}, status=400)
        # Reuse the same eligibility rules and denominators as the coordinator screen.
        import json
        state = json.loads(cycle_view(request_for_get(request), pk).content)
        if not state['ready'] or state['stale_count']:
            return JsonResponse({'detail': 'Состав цикла или карточки изменились. Проверьте цикл.'}, status=409)
        sheet_ids = list(cycle.assignments.values_list('audit_sheet_id', flat=True))
        dates = sorted(str(d) for d in cycle.assignments.values_list('audit_sheet__date', flat=True) if d)
        latest = cycle.reports.first()
        version = latest.version + 1 if latest else 1
        payload = {k: values[k] for k in ('summary', 'conclusions', 'limitations', 'decisions')}
        payload.update(name=cycle.name, version=version, generated=timezone.localtime().isoformat(),
                       period=[dates[0], dates[-1]] if dates else [], sheets=state['sheets'],
                       texts=state['total'], cards=len(state['cases']), topics=state['summary'],
                       threats=event_summary(AuditThreat.objects.filter(audit_sheet_id__in=sheet_ids), 'threat'),
                       errors=event_summary(AuditMistake.objects.filter(audit_sheet_id__in=sheet_ids), 'mistake'))
        report = CycleReport.objects.create(cycle=cycle, version=version, payload=payload, created_by=request.user)
        return JsonResponse(report_row(report), status=201)


def request_for_get(request):
    """A shallow request copy keeps publication POST body and CSRF checks untouched."""
    from copy import copy
    cloned = copy(request)
    cloned.method = 'GET'
    return cloned


def render_pdf(payload, kind):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, PageBreak

    fonts = Path(__file__).parent / 'fonts'
    if 'Losa' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Losa', str(fonts / 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('LosaBold', str(fonts / 'DejaVuSans-Bold.ttf')))
    body = ParagraphStyle('body', fontName='Losa', fontSize=9, leading=14, spaceAfter=7, alignment=TA_LEFT,
                          splitLongWords=True, textColor=colors.HexColor('#263b50'))
    heading = ParagraphStyle('heading', parent=body, fontName='LosaBold', fontSize=12, leading=17,
                             spaceBefore=14, spaceAfter=8, keepWithNext=True, textColor=colors.HexColor('#162c43'))
    title_style = ParagraphStyle('title', parent=heading, fontSize=21, leading=28)
    story = []
    def para(text, style=body):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)
    def section(title, text):
        story.extend([para(title, heading), para(text)])
    def table(headers, rows, widths):
        if not rows:
            story.append(para('Записи отсутствуют. Это не подтверждает отсутствие соответствующих ситуаций.'))
            return
        t = LongTable([[para(x) for x in row] for row in [headers, *rows]], colWidths=widths, repeatRows=1,
                      hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef5')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#d5dce5')),
                               ('LEFTPADDING', (0, 0), (-1, -1), 7),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 7)]))
        story.append(t)
    title = 'Итоговый отчет LOSA' if kind == 'results' else 'Решения круглого стола'
    story.extend([para('LOSA / РЕЗУЛЬТАТЫ ЦИКЛА', body), para(title, title_style), para(payload['name'], heading)])
    period = ' - '.join(payload['period']) or 'Не указан'
    story.append(para(f"Версия {payload['version']} · Выпуск {payload['generated'][:10]}\nПериод наблюдений: {period}"))
    if kind == 'results':
        story.extend([Spacer(1, 14), metric_cards(payload), Spacer(1, 8)])
        section('1. Краткие итоги', payload['summary'])
        section('2. Выборка и ограничения', f"Наблюдений (листов): {payload['sheets']}. Согласованных текстов: {payload['texts']}. "
                f"Включенных текстовых карточек: {payload['cards']}.\n" + payload['limitations'])
        story.append(PageBreak())
        story.append(para('3. Темы согласованных наблюдений', heading))
        story.append(para('Доля рассчитана от всех листов цикла. Лист учитывается один раз в каждой теме; темы могут пересекаться. '
                          'Затруднения и удачные практики - число листов с соответствующими карточками. Частота не является оценкой риска.'))
        if payload['topics']:
            story.append(prevalence_chart(payload['topics'], payload['sheets'], BLUE))
            story.append(Spacer(1, 10))
            story.append(para('Показаны до 8 тем с наибольшей долей листов. Полные данные приведены ниже.'))
        table(['Тема', 'Листы / доля', 'Затруднения', 'Удачные практики'],
              [[t['name'], f"{t['sheets']} / {percentage(t['sheets'], payload['sheets'])}",
                f"{t['difficulty']} / {percentage(t['difficulty'], payload['sheets'])}",
                f"{t['practice']} / {percentage(t['practice'], payload['sheets'])}"]
               for t in payload['topics']], [181, 102, 102, 102])
        for number, key, label, color in [(4, 'threats', 'Зарегистрированные угрозы', AMBER),
                                           (5, 'errors', 'Зарегистрированные ошибки', CORAL)]:
            story.append(PageBreak())
            story.append(para(f'{number}. {label}', heading))
            story.append(para(f"Записей в журнале: {sum(r['events'] for r in payload[key])}. "
                              f"Основание процентов: все {payload['sheets']} листов цикла."))
            story.append(para('Диаграмма показывает долю листов, где зарегистрирован каждый тип. '
                              'Повторные записи одного типа в одном листе не увеличивают эту долю. '
                              'Типы могут встречаться совместно, поэтому проценты не суммируются до 100%.'))
            if payload[key]:
                story.append(prevalence_chart(payload[key], payload['sheets'], color))
                story.append(Spacer(1, 10))
                story.append(para('На диаграмме до 8 наиболее распространенных типов. Полные данные - в таблице.'))
            table(['Тип', 'Записи', 'Листы / доля'],
                  [[r['name'], r['events'], f"{r['sheets']} / {percentage(r['sheets'], payload['sheets'])}"]
                   for r in payload[key]], [285, 72, 130])
        section('6. Согласованные выводы и успешные практики', payload['conclusions'])
        story.append(para('Мероприятия и ответственные оформляются отдельно в документе «Решения круглого стола» той же версии.'))
    else:
        section('Основание', f"Итоговый отчет LOSA «{payload['name']}», версия {payload['version']}. Обсуждение цикла завершено.")
        section('Согласованные решения', payload['decisions'])
        story.append(para('Этот документ фиксирует решения на дату выпуска. Статус выполнения мероприятий в этой версии не отслеживается.'))
    output = BytesIO()
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Losa', 8)
        canvas.setFillColor(colors.HexColor('#586575'))
        canvas.drawString(48, 28, f"LOSA · Версия {payload['version']} · Для внутреннего использования")
        canvas.drawRightString(A4[0]-48, 28, str(doc.page))
        canvas.restoreState()
    SimpleDocTemplate(output, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=40,
                      bottomMargin=48, title=title, author='LOSA').build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


@never_cache
@require_http_methods(['GET'])
@coordinator_required
def download_view(request, pk, report_pk, kind):
    if kind not in {'results', 'decisions'}:
        from django.http import Http404
        raise Http404
    report = get_object_or_404(CycleReport, pk=report_pk, cycle_id=pk)
    response = HttpResponse(render_pdf(report.payload, kind), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="losa-{pk}-v{report.version}-{kind}.pdf"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
