#!/usr/bin/env python3
"""
Convert SLATE User Manual from Markdown to PDF using ReportLab
"""

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import re
from pathlib import Path
import sys

def parse_markdown(md_content):
    """Parse markdown content into structured format"""
    lines = md_content.split('\n')
    sections = []
    current_section = None
    current_list = None
    code_block = False
    code_content = []

    for line in lines:
        # Code blocks
        if line.startswith('```'):
            if code_block:
                # End code block
                if current_section is not None:
                    current_section.append(('code', '\n'.join(code_content)))
                code_content = []
                code_block = False
            else:
                # Start code block
                code_block = True
            continue

        if code_block:
            code_content.append(line)
            continue

        # Headers
        if line.startswith('#'):
            if current_list:
                sections.append(('list', current_list))
                current_list = None
            level = len(re.match(r'^#+', line).group())
            title = line.lstrip('#').strip()
            sections.append(('header', (level, title)))
            continue

        # Lists
        if line.strip().startswith(('- ', '* ', '1. ', '2. ')):
            if current_list is None:
                current_list = []
            current_list.append(line.strip())
            continue

        if current_list and not line.strip():
            sections.append(('list', current_list))
            current_list = None
            continue

        # Tables
        if line.strip().startswith('|') and '|' in line[1:]:
            if current_list:
                sections.append(('list', current_list))
                current_list = None

            # Simple table detection (could be improved)
            if line.strip().startswith('|---'):
                continue  # Skip table separator

            if current_section and current_section[-1][0] == 'table':
                # Add to existing table
                current_section[-1][1].append([cell.strip() for cell in line.split('|')[1:-1]])
            else:
                # Start new table
                if current_section is None:
                    current_section = []
                current_section.append(('table', [[cell.strip() for cell in line.split('|')[1:-1]]]))
            continue

        # Regular paragraphs
        if line.strip():
            if current_list:
                sections.append(('list', current_list))
                current_list = None
            if current_section is None:
                current_section = []
            current_section.append(('text', line.strip()))
        elif current_section:
            sections.append(('paragraph', current_section))
            current_section = None

    if current_list:
        sections.append(('list', current_list))
    if current_section:
        sections.append(('paragraph', current_section))

    return sections

def create_pdf(md_file, pdf_file):
    """Create PDF from markdown file"""

    # Read markdown content
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Parse markdown
    sections = parse_markdown(md_content)

    # Create PDF document
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )

    # Story (content elements)
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#0066cc'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    h1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#0066cc'),
        spaceAfter=12,
        spaceBefore=20
    )

    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#0066cc'),
        spaceAfter=10,
        spaceBefore=15
    )

    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=HexColor('#0066cc'),
        spaceAfter=8,
        spaceBefore=10
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY
    )

    code_style = ParagraphStyle(
        'CustomCode',
        parent=styles['Code'],
        fontSize=9,
        leftIndent=20,
        backColor=colors.lightgrey,
        spaceAfter=10,
        spaceBefore=10
    )

    # Add title page
    title = Paragraph("SLATE User Manual", title_style)
    subtitle = Paragraph("Strategy Learning & Autonomous Trading Engine<br/>Version 2.0<br/>April 2026", body_style)
    story.append(title)
    story.append(Spacer(1, 0.5*inch))
    story.append(subtitle)
    story.append(PageBreak())

    # Process sections
    for section in sections:
        if section[0] == 'header':
            level, title = section[1]
            if level == 1:
                story.append(Paragraph(title, h1_style))
            elif level == 2:
                story.append(Paragraph(title, h2_style))
            else:
                story.append(Paragraph(title, h3_style))

        elif section[0] == 'text':
            text = section[1]
            # Handle inline code
            text = re.sub(r'`([^`]+)`', r'<font name="Courier" backcolor="#f0f0f0">\1</font>', text)
            # Handle bold
            text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
            # Handle italic
            text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
            story.append(Paragraph(text, body_style))

        elif section[0] == 'code':
            code_text = section[1]
            # Escape HTML special characters
            code_text = code_text.replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f'<font name="Courier">{code_text}</font>', code_style))

        elif section[0] == 'list':
            items = section[1]
            for item in items:
                item = item.lstrip('- *').lstrip('0123456789.')
                item = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', item)
                item = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', item)
                story.append(Paragraph(f'• {item}', body_style))

        elif section[0] == 'table':
            table_data = section[1]
            # Create table
            t = Table(table_data)
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

        elif section[0] == 'paragraph':
            # Join text elements
            for text in section[1]:
                text = re.sub(r'`([^`]+)`', r'<font name="Courier" backcolor="#f0f0f0">\1</font>', text)
                text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
                text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
                story.append(Paragraph(text, body_style))

    # Build PDF
    try:
        doc.build(story)
        print(f"✓ Successfully created PDF: {pdf_file}")
        return True
    except Exception as e:
        print(f"✗ Error creating PDF: {e}")
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
    else:
        print(f"\n✗ Failed to create PDF")
        sys.exit(1)
