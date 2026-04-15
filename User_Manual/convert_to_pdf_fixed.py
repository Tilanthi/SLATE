#!/usr/bin/env python3
"""
Convert SLATE User Manual from Markdown to PDF using ReportLab
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
import re
from pathlib import Path
import sys

def clean_markdown_text(text):
    """Convert markdown formatting to ReportLab-compatible formatting"""
    if not isinstance(text, str):
        text = str(text)

    # Escape HTML special characters first
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # Handle inline code
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" backcolor="#f0f0f0">\1</font>', text)

    # Handle bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)

    # Handle italic
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)

    # Handle links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<link href="\2">\1</link>', text)

    return text

def create_pdf(md_file, pdf_file):
    """Create PDF from markdown file"""

    # Read markdown content
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Create PDF document
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=36
    )

    # Story (content elements)
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=HexColor('#0066cc'),
        spaceAfter=30,
        alignment=1  # Center
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=HexColor('#666666'),
        spaceAfter=36,
        alignment=1
    )

    h1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=HexColor('#0066cc'),
        spaceAfter=12,
        spaceBefore=30
    )

    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=HexColor('#0066cc'),
        spaceAfter=10,
        spaceBefore=20
    )

    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=HexColor('#0066cc'),
        spaceAfter=8,
        spaceBefore=12
    )

    h4_style = ParagraphStyle(
        'CustomH4',
        parent=styles['Heading4'],
        fontSize=12,
        textColor=HexColor('#0066cc'),
        spaceAfter=6,
        spaceBefore=10
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )

    code_style = ParagraphStyle(
        'CustomCode',
        parent=styles['Code'],
        fontSize=9,
        leftIndent=20,
        backColor=colors.lightgrey,
        spaceAfter=10,
        spaceBefore=10,
        fontName='Courier'
    )

    # Add title page
    title = Paragraph("SLATE User Manual", title_style)
    subtitle = Paragraph(
        "Strategy Learning &amp; Autonomous Trading Engine<br/>"
        "Version 2.0<br/>"
        "April 2026",
        subtitle_style
    )
    story.append(title)
    story.append(Spacer(1, 0.75*inch))
    story.append(subtitle)
    story.append(PageBreak())

    # Process markdown line by line
    lines = md_content.split('\n')
    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []
    in_list = False
    list_items = []

    for i, line in enumerate(lines):
        # Handle code blocks
        if line.startswith('```'):
            if in_code_block:
                # End code block - add to story
                code_text = '\n'.join(code_lines)
                # Truncate if too long
                if len(code_text) > 1000:
                    code_text = code_text[:997] + '...'
                code_para = Paragraph(
                    f'<font name="Courier" size="9">{code_text}</font>',
                    ParagraphStyle('CodeBlock', parent=code_style, leftIndent=30)
                )
                story.append(code_para)
                code_lines = []
                in_code_block = False
            else:
                # Start code block
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Handle headers
        if line.startswith('#'):
            # Flush any pending list items
            if in_list:
                for item in list_items:
                    item_text = clean_markdown_text(item.lstrip('- *').lstrip('0123456789.'))
                    story.append(Paragraph(f'• {item_text}', body_style))
                list_items = []
                in_list = False

            level = len(re.match(r'^#+', line).group())
            title = clean_markdown_text(line.lstrip('#').strip())

            if level == 1:
                story.append(Paragraph(title, h1_style))
            elif level == 2:
                story.append(Paragraph(title, h2_style))
            elif level == 3:
                story.append(Paragraph(title, h3_style))
            else:
                story.append(Paragraph(title, h4_style))
            continue

        # Handle horizontal rules
        if line.strip() == '---':
            story.append(Spacer(1, 0.2*inch))
            continue

        # Handle tables
        if line.strip().startswith('|') and '|' in line[1:]:
            if line.strip().startswith('|---'):
                continue  # Skip table separator

            # Parse table row
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            table_lines.append(cells)
            in_table = True
            continue

        # Flush table if we're done with it
        if in_table and not line.strip().startswith('|'):
            # Create table
            if len(table_lines) > 1:
                t = Table(table_lines)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0066cc')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f9f9f9')),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey)
                ]))
                story.append(t)
            table_lines = []
            in_table = False

        # Handle lists
        if line.strip().startswith(('- ', '* ', '•', '+ ')) or \
           re.match(r'^\s*\d+\.\s', line.strip()):
            list_items.append(line.strip())
            in_list = True
            continue

        # Flush list if we're done with it
        if in_list and not line.strip():
            for item in list_items:
                # Remove bullet/number
                item_text = re.sub(r'^[\s\-*+•0-9.]+', '', item)
                item_text = clean_markdown_text(item_text.strip())
                if item_text:
                    story.append(Paragraph(f'• {item_text}', body_style))
            list_items = []
            in_list = False

        # Handle regular paragraphs
        if line.strip() and not in_table and not in_list:
            # Flush any pending list items first
            if in_list:
                for item in list_items:
                    item_text = clean_markdown_text(item.lstrip('- *').lstrip('0123456789.'))
                    story.append(Paragraph(f'• {item_text}', body_style))
                list_items = []
                in_list = False

            para_text = clean_markdown_text(line.strip())
            if para_text:
                story.append(Paragraph(para_text, body_style))

    # Flush any remaining list items
    if in_list:
        for item in list_items:
            item_text = clean_markdown_text(item.lstrip('- *').lstrip('0123456789.'))
            story.append(Paragraph(f'• {item_text}', body_style))

    # Build PDF
    try:
        doc.build(story)
        print(f"✓ Successfully created PDF: {pdf_file}")
        return True
    except Exception as e:
        print(f"✗ Error creating PDF: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    md_path = Path("SLATE_User_Manual.md")
    pdf_path = Path("SLATE_User_Manual.pdf")

    if not md_path.exists():
        print(f"Error: {md_path} not found")
        sys.exit(1)

    print("Creating PDF from Markdown...")
    if create_pdf(md_path, pdf_path):
        print(f"\n✓ PDF created successfully: {pdf_path}")
        print(f"✓ Markdown version: {md_path}")
        print(f"\nFiles are in: {Path.cwd()}")
    else:
        print(f"\n✗ Failed to create PDF")
        sys.exit(1)
