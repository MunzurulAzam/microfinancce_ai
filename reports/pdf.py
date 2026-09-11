"""Render the saved presentation payload, never query or regenerate narration."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String, Line

BLUE = colors.HexColor('#133e88')
GOLD = colors.HexColor('#ffb43e')
PALETTE = ['#123d88', '#00a953', '#ce281f', '#ffc000']


def chart(countries, key, title):
    drawing = Drawing(350, 180)
    drawing.add(String(175, 162, title, textAnchor='middle', fontName='Helvetica-Bold', fontSize=13, fillColor=BLUE))
    available = [c[key] for c in countries if c.get(key) is not None]
    if not available:
        drawing.add(String(175, 90, 'Unavailable - see source notes', textAnchor='middle', fontSize=10))
        return drawing
    lo, hi = min(0, min(available)), max(0, max(available))
    span = hi - lo or 1
    baseline = 40 + (-lo / span) * 100
    drawing.add(Line(20, baseline, 335, baseline, strokeColor=colors.lightgrey))
    width = 310 / len(countries)
    for i, c in enumerate(countries):
        x = 28 + i * width
        v = c.get(key)
        if v is not None:
            height = abs(v) / span * 100
            drawing.add(Rect(x, baseline if v >= 0 else baseline-height, width-20, height,
                             fillColor=colors.HexColor(PALETTE[i % 4]), strokeColor=None))
        drawing.add(String(x+(width-20)/2, 23, c['name'], textAnchor='middle', fontSize=9))
        drawing.add(String(x+(width-20)/2, 10, 'Unavailable' if v is None else f'{v:.2f}%', textAnchor='middle', fontSize=8))
    return drawing


def render_pdf(report):
    buffer = BytesIO()
    width, height = landscape(A4)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyReport', fontName='Helvetica', fontSize=10, leading=14, spaceAfter=9))
    styles.add(ParagraphStyle(name='CellReport', fontName='Helvetica', fontSize=8, leading=11))
    styles.add(ParagraphStyle(name='WhiteReport', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.white))
    styles.add(ParagraphStyle(name='CoverReport', fontName='Helvetica-Bold', fontSize=27, leading=34, textColor=BLUE, spaceAfter=18))
    styles.add(ParagraphStyle(name='KPIReport', fontName='Helvetica-Bold', fontSize=17, leading=23, alignment=TA_CENTER, textColor=colors.white))
    def para(text, style='BodyReport'):
        return Paragraph(escape(str(text)), styles[style])
    def table(columns, rows):
        data = [[para(c, 'WhiteReport') for c in columns]] + [[para(c, 'CellReport') for c in row] for row in rows]
        proportions = ([.13,.24,.13,.1,.12,.14,.14] if len(columns)==7 else
                       [.14,.38,.18,.13,.17] if len(columns)==5 else [1/len(columns)]*len(columns))
        t = Table(data, colWidths=[(width-80)*p/sum(proportions) for p in proportions], repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#cbd2dc')),
                              ('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f6fb')]),
                              ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
                              ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        return t
    story = [Spacer(1,30), para('UMOJA INTERNATIONAL', 'CoverReport'),
             para('END OF MONTH REPORT', 'CoverReport'),
             para(f"{report['period_label']} | Comparative review against {report['comparison_label']}"), Spacer(1,20)]
    metrics = report['metrics']
    labels = [('Countries', 'countries'), ('Branches with portfolio', 'branches'), ('Reported borrowers','borrowers'),
              ('Group principal portfolio (USD)','principal_usd'), ('Group PAR >30 (%)','par_percent'), ('Portfolio at risk (USD)','par_amount_usd')]
    styles.add(ParagraphStyle(name='GoldKPIReport', parent=styles['KPIReport'], textColor=BLUE))
    styles.add(ParagraphStyle(name='GoldLabelReport', parent=styles['WhiteReport'], textColor=BLUE, alignment=TA_CENTER))
    styles['WhiteReport'].alignment = TA_CENTER
    cells = []
    for label, key in labels:
        value = metrics[key]
        text = 'Unavailable' if value is None else (f'{value:,.2f}' if key in ('principal_usd','par_percent','par_amount_usd') else f'{value:,}')
        gold = len(cells) % 3 == 1
        cells.append([para(text, 'GoldKPIReport' if gold else 'KPIReport'), para(label, 'GoldLabelReport' if gold else 'WhiteReport')])
    kpi = Table([cells[:3], cells[3:]], colWidths=[(width-80)/3]*3)
    kpi.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BLUE),('BACKGROUND',(1,0),(1,-1),GOLD),
                            ('BOX',(0,0),(-1,-1),2,colors.white),('INNERGRID',(0,0),(-1,-1),5,colors.white),
                            ('TOPPADDING',(0,0),(-1,-1),15),('BOTTOMPADDING',(0,0),(-1,-1),15)]))
    story += [kpi, Spacer(1,22), para('Monthly portfolio, country performance and branch risk review.'),
              para('Unavailable values indicate missing or unreconciled source data. See the source and availability notes.'), PageBreak()]
    for section in report['sections']:
        if section['id'] in ('countries','actions'):
            story.append(PageBreak())
        story.append(para(section['title'], 'Heading1'))
        for text in section.get('paragraphs', []):
            story.append(para(text))
        if section['id'] == 'executive':
            story.append(Table([[chart(report['countries'],'growth_percent','Portfolio growth (local currency)'),
                                 chart(report['countries'],'portfolio_share_percent','Portfolio share (USD)')]], colWidths=[(width-80)/2]*2))
            story.append(Spacer(1,12))
        for block in section.get('blocks', []):
            story.append(KeepTogether([para(block['heading'], 'Heading2'), para(block['text'])]))
        if section.get('table'):
            story.append(table(**section['table']))
        story.append(Spacer(1,15))
    story += [PageBreak(), para('Sources and availability', 'Heading1')]
    for source in report['sources']:
        story.append(para(source['table'] + ': ' + source['basis']))
    for note in report['availability']['warnings']:
        story.append(para(note))
    story.append(para(f"Report ID: {report['report_id']} | Generated: {report['generated_at']}"))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLUE)
        canvas.setFont('Helvetica', 9)
        canvas.drawString(40,height-25,f"Umoja International | Group Performance Report - {report['period_label']}")
        canvas.setStrokeColor(GOLD)
        canvas.line(40,height-32,width-40,height-32)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(width-40,20,str(doc.page))
        canvas.restoreState()
    SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=40,rightMargin=40,
                      topMargin=48,bottomMargin=36,title=report['title'],author='Umoja International').build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()
