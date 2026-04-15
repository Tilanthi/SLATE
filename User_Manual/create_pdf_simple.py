#!/usr/bin/env python3
"""
Simple PDF converter for SLATE User Manual
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.colors import HexColor
from pathlib import Path
import sys

def simple_escape(text):
    """Simple text escaping that avoids HTML parsing issues"""
    if not isinstance(text, str):
        text = str(text)
    # Just escape the basics, avoid complex HTML
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def create_pdf(md_file, pdf_file):
    """Create PDF from markdown file"""

    # Read markdown content
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Create PDF document
    doc = SimpleDocTemplate(
        str(pdf_file),  # Convert Path to string
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
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=HexColor('#666666'),
        spaceAfter=36,
        alignment=TA_CENTER
    )

    h1_style = ParagraphStyle(
        'CustomH1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#0066cc'),
        spaceAfter=12,
        spaceBefore=25
    )

    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=15,
        textColor=HexColor('#0066cc'),
        spaceAfter=10,
        spaceBefore=18
    )

    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=HexColor('#0066cc'),
        spaceAfter=8,
        spaceBefore=12
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
        leftIndent=30,
        rightIndent=30,
        spaceAfter=10,
        spaceBefore=10,
        fontName='Courier',
        textColor=HexColor('#333333')
    )

    # Add title page
    story.append(Paragraph("SLATE User Manual", title_style))
    story.append(Spacer(1, 0.75*inch))
    story.append(Paragraph(
        "Strategy Learning &amp; Autonomous Trading Engine<br/>"
        "Version 2.0<br/>"
        "April 2026",
        subtitle_style
    ))
    story.append(PageBreak())

    # Process markdown line by line
    lines = md_content.split('\n')
    in_code_block = False
    code_lines = []

    for line in lines:
        # Handle code blocks
        if line.startswith('```'):
            if in_code_block:
                # End code block
                if code_lines:
                    code_text = '\n'.join(code_lines)
                    # Escape HTML chars
                    code_text = simple_escape(code_text)
                    # Truncate if too long
                    if len(code_text) > 800:
                        code_text = code_text[:797] + '...'
                    story.append(Paragraph(code_text, code_style))
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
            level = len(line) - len(line.lstrip('#'))
            title = simple_escape(line.lstrip('#').strip())

            if level == 1:
                story.append(Paragraph(title, h1_style))
            elif level == 2:
                story.append(Paragraph(title, h2_style))
            elif level == 3:
                story.append(Paragraph(title, h3_style))
            else:
                story.append(Paragraph(title, h3_style))
            continue

        # Skip empty lines and horizontal rules
        if not line.strip() or line.strip() == '---':
            continue

        # Handle lists and bullet points
        if line.strip().startswith(('- ', '* ', '•', '+ ')) or \
           any(line.strip().startswith(f'{i}. ') for i in range(1, 10)):
            item_text = simple_escape(line.strip())
            # Remove bullet/number prefix
            for prefix in ['- ', '* ', '• ', '+ ']:
                if item_text.startswith(prefix):
                    item_text = item_text[len(prefix):]
                    break
            # Remove numbered prefix
            for i in range(1, 10):
                if item_text.startswith(f'{i}. '):
                    item_text = item_text[3:]
                    break
            story.append(Paragraph(f'• {item_text}', body_style))
            continue

        # Handle tables (simple - just show as text)
        if line.strip().startswith('|') and '|' in line[1:]:
            # Just skip tables for now, they're complex
            continue

        # Regular paragraphs
        para_text = simple_escape(line.strip())
        if para_text:
            story.append(Paragraph(para_text, body_style))

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
    print("Note: Tables and complex formatting may be simplified in PDF version")
    print("For full formatting, see the Markdown version\n")

    if create_pdf(md_path, pdf_path):
        print(f"\n✓ PDF created successfully: {pdf_path}")
        print(f"✓ Markdown version: {md_path}")
        print(f"\nFiles are in: {Path.cwd()}")
        print(f"\nTo view the PDF:")
        print(f"  - Mac: open {pdf_path}")
        print(f"  - Linux: xdg-open {pdf_path}")
        print(f"  - Windows: start {pdf_path}")
    else:
        print(f"\n✗ Failed to create PDF")
        print(f"  The Markdown version is still available at: {md_path}")
        sys.exit(1)
