"""Vector PDF charts; prevalence always uses all sheets in the frozen cycle."""
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Flowable, Paragraph, LongTable, Table, TableStyle

INK = colors.HexColor('#162c43')
MUTED = colors.HexColor('#62758a')
TRACK = colors.HexColor('#eaf0f5')
BLUE = '#2563a6'
AMBER = '#ad711a'
CORAL = '#bf5048'


def coverage(count, total):
    """None means no denominator, never an invented zero percent."""
    return 100 * count / total if total else None


def percentage(count, total):
    value = coverage(count, total)
    return f'{value:.1f}%'.replace('.', ',') if value is not None else 'н/д'


def leading_rows(rows, limit=8):
    return sorted(rows, key=lambda r: (-r['sheets'], r['name']))[:limit]


class CoverageBar(Flowable):
    def __init__(self, count, total, color, width=210):
        super().__init__()
        self.width, self.height = width, 22
        self.value = coverage(count, total)
        self.color = colors.HexColor(color)

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(TRACK)
        canvas.roundRect(0, 5, self.width, 12, 3, fill=1, stroke=0)
        if self.value is not None and self.value > 0:
            canvas.setFillColor(self.color)
            canvas.roundRect(0, 5, self.width * min(self.value, 100) / 100, 12, 3, fill=1, stroke=0)


class Scale(Flowable):
    def __init__(self, width=210):
        super().__init__()
        self.width, self.height = width, 17

    def draw(self):
        self.canv.setFont('Losa', 7)
        self.canv.setFillColor(MUTED)
        for value in (0, 25, 50, 75, 100):
            label = f'{value}%'
            x = self.width * value / 100
            if value == 0:
                self.canv.drawString(x, 4, label)
            elif value == 100:
                self.canv.drawRightString(x, 4, label)
            else:
                self.canv.drawCentredString(x, 4, label)


def prevalence_chart(rows, total, color=BLUE):
    """A splittable chart with wrapping labels, a fixed 0-100% scale and exact counts."""
    label_style = ParagraphStyle('chart-label', fontName='Losa', fontSize=8.5, leading=12,
                                 textColor=INK, splitLongWords=True)
    value_style = ParagraphStyle('chart-value', parent=label_style, alignment=2)
    data = [['', Scale(), Paragraph('Доля листов', value_style)]]
    for row in leading_rows(rows):
        value = f"{percentage(row['sheets'], total)}<br/><font size='7' color='#62758a'>{row['sheets']} из {total}</font>"
        data.append([Paragraph(escape(row['name']), label_style),
                     CoverageBar(row['sheets'], total, color), Paragraph(value, value_style)])
    chart = LongTable(data, colWidths=[181, 222, 84], repeatRows=1, hAlign='LEFT')
    chart.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (0, -1), 12),
                              ('RIGHTPADDING', (1, 0), (-1, -1), 0),
                              ('TOPPADDING', (0, 1), (-1, -1), 8),
                              ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                              ('LINEBELOW', (0, 1), (-1, -1), .35, TRACK)]))
    return chart


def metric_cards(payload):
    big = ParagraphStyle('metric-number', fontName='LosaBold', fontSize=23, leading=28, textColor=INK)
    small = ParagraphStyle('metric-caption', fontName='Losa', fontSize=8, leading=12, textColor=MUTED)
    cells = []
    for key, caption in [('sheets', 'наблюдений / листов'), ('texts', 'согласованных текстов'), ('cards', 'текстовых карточек')]:
        cells.append([Paragraph(str(payload[key]), big), Paragraph(caption, small)])
    table = Table([cells], colWidths=[162, 162, 163], hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f5fa')),
                              ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#dce7f1')),
                              ('LINEAFTER', (0, 0), (1, 0), 2, colors.white),
                              ('TOPPADDING', (0, 0), (-1, -1), 12),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                              ('LEFTPADDING', (0, 0), (-1, -1), 12)]))
    return table
