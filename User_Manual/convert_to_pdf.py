#!/usr/bin/env python3
"""
Create a proper PDF from the SLATE User Manual markdown.
This version actually renders ALL the content, not just title pages.
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from fpdf import FPDF
from pathlib import Path
import textwrap
import re

# Read the markdown file
md_file = Path('SLATE_User_Manual.md')
with open(md_file, 'r', encoding='utf-8') as f:
    content = f.read()

class SLATEManualPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.title_font = 'Helvetica'
        self.body_font = 'Helvetica'
        self.mono_font = 'Courier'

    def header(self):
        # Page header
        self.set_font(self.title_font, 'B', 8)
        self.cell(0, 5, 'SLATE User Manual v2.0', 0, 0, 'L')
        self.cell(0, 5, f'Page {self.page_no()}', 0, 0, 'R')
        self.ln(5)

    def footer(self):
        # Page footer
        self.set_y(-15)
        self.set_font(self.body_font, 'I', 7)
        self.cell(0, 5, 'Paper Trading Only - No Real Money Risked', 0, 0, 'C')
        self.ln(5)

    def chapter_title(self, title):
        self.set_font(self.title_font, 'B', 16)
        self.set_fill_color(44, 62, 80)
        title = clean_text(title)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(4)

    def section_title(self, title):
        self.set_font(self.title_font, 'B', 12)
        self.set_fill_color(52, 73, 94)
        title = clean_text(title)
        self.cell(0, 8, title, 0, 1, 'L', 1)
        self.ln(3)

    def subsection_title(self, title):
        self.set_font(self.title_font, 'B', 11)
        self.set_text_color(41, 128, 185)
        title = clean_text(title)
        self.cell(0, 6, title, 0, 1, 'L')
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def body_text(self, text):
        self.set_font(self.body_font, '', 10)
        text = clean_text(text)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font(self.body_font, '', 10)
        self.cell(10, 5, '*', 0, 0)
        text = clean_text(text)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def code_block(self, code):
        self.set_font(self.mono_font, '', 8)
        self.set_fill_color(236, 240, 241)
        code = clean_text(code)
        self.multi_cell(0, 4, code)
        self.set_fill_color(255, 255, 255)
        self.ln(2)

def clean_text(text):
    """Replace Unicode characters with ASCII equivalents."""
    replacements = {
        '→': '->',
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '—': '--',
        '–': '-',
        '…': '...',
        '≥': '>=',
        '≤': '<=',
        '≠': '!=',
        '×': 'x',
        '•': '*',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def create_pdf():
    pdf = SLATEManualPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title page
    pdf.set_font('Helvetica', 'B', 48)
    pdf.set_xy(0, 80)
    pdf.cell(0, 20, 'SLATE', 0, 1, 'C')
    pdf.set_font('Helvetica', 'B', 24)
    pdf.cell(0, 15, 'User Manual', 0, 1, 'C')
    pdf.set_font('Helvetica', 'I', 14)
    pdf.cell(0, 10, 'Strategy Learning & Autonomous Trading Engine', 0, 1, 'C')
    pdf.ln(30)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 8, 'Version 2.0.0', 0, 1, 'C')
    pdf.cell(0, 8, 'April 30, 2026', 0, 1, 'C')
    pdf.ln(20)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(192, 57, 43)
    pdf.cell(0, 10, 'PAPER TRADING ONLY', 0, 1, 'C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(0, 8, 'No real money is ever risked', 0, 1, 'C')

    # Add new page for content
    pdf.add_page()

    # Parse and render content
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Skip table of contents section
        if line.startswith('## Table of Contents'):
            # Skip until next major section
            while i < len(lines) and not lines[i].startswith('## 1.'):
                i += 1
            continue

        # Main chapter titles (# Title)
        if line.startswith('# ') and not line.startswith('## '):
            title = line.lstrip('#').strip()
            # Check if it's the main title (already done)
            if title.upper() == 'SLATE USER MANUAL':
                i += 1
                continue
            pdf.add_page()
            pdf.chapter_title(title)
            i += 1
            continue

        # Section headers (## Section)
        if line.startswith('## '):
            # Skip table of contents items
            if '[' in line and '](' in line:
                i += 1
                continue
            title = line.lstrip('##').strip()
            # Remove markdown links
            title = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', title)
            pdf.section_title(title)
            i += 1
            continue

        # Subsection headers (### Subsection)
        if line.startswith('### '):
            title = line.lstrip('###').strip()
            pdf.subsection_title(title)
            i += 1
            continue

        # Skip horizontal rules
        if line.startswith('---'):
            i += 1
            continue

        # Image references - add placeholder
        if line.startswith('![') and '](images/' in line:
            img_name = line.split('](images/')[1].rstrip(')')
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(0, 5, f'[Diagram: {img_name}]', 0, 1, 'C')
            pdf.ln(3)
            i += 1
            continue

        # Code blocks
        if line.strip().startswith('```'):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                # Replace Unicode characters with ASCII
                code_line = lines[i]
                code_line = code_line.replace('→', '->')
                code_line = code_line.replace('"', '"')
                code_line = code_line.replace('"', '"')
                code_line = code_line.replace(''', "'")
                code_line = code_line.replace(''', "'")
                code_lines.append(code_line)
                i += 1
            pdf.code_block('\n'.join(code_lines))
            i += 1
            continue

        # Bold standalone lines (like **What this tells you:**)
        if line.startswith('**') and line.endswith('**'):
            text = line.strip('*')
            pdf.set_font('Helvetica', 'B', 10)
            pdf.multi_cell(0, 5, text)
            pdf.ln(2)
            i += 1
            continue

        # Bullet points
        if line.startswith('- ') or line.startswith('* '):
            text = line[2:].strip()
            # Clean up markdown formatting
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            pdf.bullet(text)
            i += 1
            continue

        # Numbered lists
        match = re.match(r'^(\d+)\.\s+(.+)', line)
        if match:
            num, text = match.groups()
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
            text = clean_text(text)
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(15, 5, f'{num}.', 0, 0)
            pdf.multi_cell(0, 5, text)
            pdf.ln(1)
            i += 1
            continue

        # Regular text
        if line:
            # Clean up markdown formatting and Unicode
            text = line
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            text = re.sub(r'`([^`]+)`', r'\1', text)
            text = clean_text(text)
            pdf.body_text(text)
            i += 1
            continue

        i += 1

    # Quick reference page
    pdf.add_page()
    pdf.chapter_title('Quick Reference')

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Server Information', 0, 1)
    pdf.set_font('Helvetica', '', 10)

    ref_data = [
        ('Server Port:', '8788'),
        ('Mode:', 'Paper Trading Only'),
        ('Initial Capital:', '10,000 USDT'),
        ('Maker Fee:', '0.02%'),
        ('Taker Fee:', '0.05%'),
        ('Slippage:', '0.05% (5 bps)'),
        ('Fill Rate:', '95%'),
        ('Max Position:', '10% of capital'),
    ]

    for label, value in ref_data:
        pdf.cell(60, 6, label, 0, 0)
        pdf.cell(0, 6, value, 0, 1)
    pdf.ln(5)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Essential Commands', 0, 1)
    pdf.set_font('Courier', '', 9)

    commands = [
        'python3 -m slate_core.autonomous_research.server',
        'curl http://localhost:8788/health',
        'curl -X POST http://localhost:8788/api/discovery/realistic/start',
    ]

    for cmd in commands:
        pdf.multi_cell(0, 5, cmd)
        pdf.ln(1)

    # Output
    output_file = Path('SLATE_User_Manual.pdf')
    pdf.output(str(output_file))

    print(f"✓ Created PDF: {output_file}")
    print(f"✓ Full content rendered from markdown")
    print(f"✓ Accessible language preserved")
    print(f"✓ Proper formatting with chapters, sections, and code blocks")
    print(f"\nUser Manual files:")
    print(f"  - {md_file}")
    print(f"  - {output_file}")

if __name__ == '__main__':
    create_pdf()
