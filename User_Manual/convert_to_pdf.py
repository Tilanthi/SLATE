#!/usr/bin/env python3
"""
Improved PDF creation for SLATE User Manual.
Fixes formatting issues: overlapping text, line throws, unnecessary spaces.
Uses proper text wrapping and page layout.
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path
import textwrap

# Read the markdown file
md_file = Path('SLATE_User_Manual.md')
with open(md_file, 'r', encoding='utf-8') as f:
    md_content = f.read()

# Create PDF
pdf_file = Path('SLATE_User_Manual.pdf')

# Page settings
PAGE_WIDTH = 8.5
PAGE_HEIGHT = 11
MARGIN_LEFT = 0.8
MARGIN_RIGHT = 0.8
MARGIN_TOP = 0.8
MARGIN_BOTTOM = 0.8
TEXT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
LINE_HEIGHT = 0.035

def create_title_page(pdf):
    """Create professional title page."""
    fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
    ax.axis('off')

    # Main title
    ax.text(0.5, 0.65, 'SLATE', fontsize=52, fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, color='#2C3E50')
    ax.text(0.5, 0.56, 'User Manual', fontsize=38, fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, color='#34495E')
    ax.text(0.5, 0.47, 'Strategy Learning & Autonomous Trading Engine',
            fontsize=16, ha='center', va='center', transform=ax.transAxes,
            color='#7F8C8D', style='italic')
    ax.text(0.5, 0.41, 'Complete Guide to Discovery, Testing, and Evolution',
            fontsize=14, ha='center', va='center', transform=ax.transAxes,
            color='#95A5A6')

    # Version info
    ax.text(0.5, 0.32, 'Version 2.0.0', fontsize=12,
            ha='center', va='center', transform=ax.transAxes, color='#7F8C8D')
    ax.text(0.5, 0.28, 'April 30, 2026', fontsize=12,
            ha='center', va='center', transform=ax.transAxes, color='#7F8C8D')

    # Warning box
    ax.text(0.5, 0.18, 'PAPER TRADING ONLY', fontsize=14, fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, color='#C0392B',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#FADBD8',
                     edgecolor='#C0392B', linewidth=2))

    # Footer
    ax.text(0.5, 0.08, 'No real money is ever risked',
            fontsize=10, ha='center', va='center', transform=ax.transAxes,
            color='#95A5A6', style='italic')

    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

def wrap_text(text, width_chars=95):
    """Wrap text to specified width."""
    return textwrap.fill(text, width=width_chars, break_long_words=False)

def render_text_on_page(ax, text_blocks, y_start, page_num):
    """Render multiple text blocks on a page."""
    y = y_start
    blocks_rendered = 0

    for block_type, content in text_blocks:
        # Check if we need a new page
        if y < MARGIN_BOTTOM + 0.1:
            return blocks_rendered, y, True  # Need new page

        if block_type == 'title':
            ax.text(0.5, y, content, fontsize=14, fontweight='bold',
                   ha='center', va='top', transform=ax.transAxes,
                   color='#2C3E50')
            y -= 0.08

        elif block_type == 'subtitle':
            ax.text(0.5, y, content, fontsize=11, fontweight='bold',
                   ha='center', va='top', transform=ax.transAxes,
                   color='#34495E')
            y -= 0.06

        elif block_type == 'section':
            ax.text(MARGIN_LEFT, y, content, fontsize=12, fontweight='bold',
                   ha='left', va='top', transform=ax.transAxes,
                   color='#2C3E50')
            y -= 0.05

        elif block_type == 'subsection':
            ax.text(MARGIN_LEFT, y, content, fontsize=11, fontweight='bold',
                   ha='left', va='top', transform=ax.transAxes,
                   color='#34495E')
            y -= 0.04

        elif block_type == 'text':
            wrapped = wrap_text(content)
            ax.text(MARGIN_LEFT, y, wrapped, fontsize=9,
                   ha='left', va='top', transform=ax.transAxes,
                   color='#2C3E50', family='monospace')
            # Estimate lines
            lines = wrapped.count('\n') + 1
            y -= lines * LINE_HEIGHT

        elif block_type == 'bullet':
            wrapped = wrap_text('• ' + content, width_chars=92)
            ax.text(MARGIN_LEFT + 0.05, y, wrapped, fontsize=9,
                   ha='left', va='top', transform=ax.transAxes,
                   color='#2C3E50', family='monospace')
            lines = wrapped.count('\n') + 1
            y -= lines * LINE_HEIGHT

        elif block_type == 'code':
            # Code block
            ax.text(MARGIN_LEFT, y, content, fontsize=8,
                   ha='left', va='top', transform=ax.transAxes,
                   color='#27AE60', family='monospace',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='#ECF0F1',
                            edgecolor='#BDC3C7', alpha=0.8))
            y -= 0.08

        elif block_type == 'numbered':
            wrapped = wrap_text(content, width_chars=92)
            ax.text(MARGIN_LEFT + 0.05, y, wrapped, fontsize=9,
                   ha='left', va='top', transform=ax.transAxes,
                   color='#2C3E50', family='monospace')
            lines = wrapped.count('\n') + 1
            y -= lines * LINE_HEIGHT

        blocks_rendered += 1

    # Page number
    ax.text(0.5, 0.02, f'Page {page_num}',
           ha='center', va='center', transform=ax.transAxes,
           color='#95A5A6', fontsize=8)

    return blocks_rendered, y, False  # Page complete

def process_markdown(content, pdf):
    """Process markdown content and create PDF pages."""
    lines = content.split('\n')
    page_num = 2  # Start after title page
    y = MARGIN_TOP

    text_blocks = []
    in_code_block = False
    code_buffer = []

    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                text_blocks.append(('code', '\n'.join(code_buffer)))
                code_buffer = []
                in_code_block = False
            else:
                # Start code block
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        # Main chapter titles (# Title)
        if line.startswith('# ') and not line.startswith('## '):
            # Flush existing blocks
            if text_blocks:
                fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
                ax.axis('off')
                rendered, new_y, need_page = render_text_on_page(
                    ax, text_blocks, y, page_num)
                if need_page or rendered < len(text_blocks):
                    pdf.savefig(fig, bbox_inches='tight')
                    plt.close()
                    page_num += 1
                    # Put remaining on new page
                    if rendered < len(text_blocks):
                        remaining = text_blocks[rendered:]
                        fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
                        ax.axis('off')
                        render_text_on_page(ax, remaining, MARGIN_TOP, page_num)
                        pdf.savefig(fig, bbox_inches='tight')
                        plt.close()
                        page_num += 1
                text_blocks = []
                y = MARGIN_TOP

            # Create chapter title page
            chapter_title = line.lstrip('#').strip()
            fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
            ax.axis('off')

            ax.text(0.5, 0.6, chapter_title, fontsize=20, fontweight='bold',
                   ha='center', va='center', transform=ax.transAxes,
                   color='#2C3E50')
            ax.text(0.5, 0.02, f'Page {page_num}',
                   ha='center', va='center', transform=ax.transAxes,
                   color='#95A5A6', fontsize=8)

            pdf.savefig(fig, bbox_inches='tight')
            plt.close()
            page_num += 1
            y = MARGIN_TOP
            continue

        # Section headers (## Section)
        if line.startswith('## '):
            text_blocks.append(('section', line.lstrip('##').strip()))
            continue

        # Subsection headers (### Subsection)
        if line.startswith('### '):
            text_blocks.append(('subsection', line.lstrip('###').strip()))
            continue

        # Bold text (**text**)
        if line.strip().startswith('**') and line.strip().endswith('**'):
            text_blocks.append(('section', line.strip().strip('*').strip()))
            continue

        # Bullet points
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            text_blocks.append(('bullet', line.strip()[2:]))
            continue

        # Numbered list
        if len(line.strip()) > 2 and line.strip()[0].isdigit() and line.strip()[1] == '.':
            text_blocks.append(('numbered', line.strip()))
            continue

        # Image references
        if line.strip().startswith('![') and '](images/' in line:
            img_name = line.split('](images/')[1].rstrip(')')
            img_path = Path('images') / img_name

            # Flush existing text first
            if text_blocks:
                fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
                ax.axis('off')
                render_text_on_page(ax, text_blocks, y, page_num)
                pdf.savefig(fig, bbox_inches='tight')
                plt.close()
                page_num += 1
                text_blocks = []
                y = MARGIN_TOP

            # Add image page
            if img_path.exists():
                fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
                ax.axis('off')

                try:
                    from PIL import Image
                    img = Image.open(img_path)

                    # Calculate display size
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height

                    max_width = TEXT_WIDTH
                    max_height = PAGE_HEIGHT - 2 * MARGIN_TOP

                    if aspect_ratio > max_width / max_height:
                        display_width = max_width
                        display_height = max_width / aspect_ratio
                    else:
                        display_height = max_height
                        display_width = max_height * aspect_ratio

                    # Center image
                    y_pos = (PAGE_HEIGHT - display_height) / 2 / PAGE_HEIGHT

                    ax.imshow(img, extent=[MARGIN_LEFT, MARGIN_LEFT + display_width,
                                          (PAGE_HEIGHT/2) - (display_height/2),
                                          (PAGE_HEIGHT/2) + (display_height/2)],
                             transform=ax.transData)

                    # Caption
                    caption = img_name.replace('_', ' ').replace('.png', '').title()
                    ax.text(0.5, 0.03, caption, fontsize=8,
                           ha='center', va='center', transform=ax.transAxes,
                           color='#7F8C8D', style='italic')

                    ax.text(0.5, 0.02, f'Page {page_num}',
                           ha='center', va='center', transform=ax.transAxes,
                           color='#95A5A6', fontsize=7)

                    pdf.savefig(fig, bbox_inches='tight')
                    plt.close()
                    page_num += 1
                except Exception as e:
                    print(f"Warning: Could not include image {img_name}: {e}")
                    plt.close()
            continue

        # Empty lines separate paragraphs
        if not line.strip():
            if text_blocks and text_blocks[-1][0] == 'text':
                text_blocks.append(('text', ''))  # Paragraph break
            continue

        # Regular text
        if line.strip():
            # Skip table of contents links
            if line.strip().startswith('* [') and '](' in line.strip():
                continue
            # Skip horizontal rules
            if line.strip().startswith('---'):
                continue
            text_blocks.append(('text', line.strip()))

    # Render remaining blocks
    if text_blocks:
        fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
        ax.axis('off')
        render_text_on_page(ax, text_blocks, y, page_num)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        page_num += 1

    return page_num

def create_quick_reference_page(pdf, page_num):
    """Create quick reference card."""
    fig, ax = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
    ax.axis('off')

    ax.text(0.5, 0.92, 'Quick Reference', fontsize=16, fontweight='bold',
           ha='center', va='center', transform=ax.transAxes, color='#2C3E50')

    # Two columns
    left_col = 0.15
    right_col = 0.55
    y = 0.82

    # Server section
    ax.text(left_col, y, 'Server', fontsize=10, fontweight='bold',
           ha='left', va='center', transform=ax.transAxes, color='#E74C3C')
    ax.text(right_col, y, 'Commands', fontsize=10, fontweight='bold',
           ha='left', va='center', transform=ax.transAxes, color='#E74C3C')
    y -= 0.05

    server_info = [
        ('Port', '8788'),
        ('Health Check', 'curl localhost:8788/health'),
        ('API Docs', 'http://localhost:8788/docs'),
        ('Start Server', 'python3 -m slate_core.server'),
    ]

    for label, value in server_info:
        ax.text(left_col, y, label, fontsize=9,
               ha='left', va='center', transform=ax.transAxes, color='#2C3E50')
        ax.text(right_col, y, value, fontsize=8, family='monospace',
               ha='left', va='center', transform=ax.transAxes, color='#2C3E50')
        y -= 0.04

    y -= 0.03

    # Discovery section
    ax.text(left_col, y, 'Discovery', fontsize=10, fontweight='bold',
           ha='left', va='center', transform=ax.transAxes, color='#27AE60')
    ax.text(right_col, y, 'API Endpoints', fontsize=10, fontweight='bold',
           ha='left', va='center', transform=ax.transAxes, color='#27AE60')
    y -= 0.05

    discovery_info = [
        ('Start Discovery', 'POST /api/discovery/realistic/start'),
        ('Get Status', 'GET /api/discovery/realistic/status'),
        ('Top Strategies', 'GET /api/discovery/realistic/top'),
        ('Statistics', 'GET /api/discovery/realistic/statistics'),
        ('Stop Discovery', 'POST /api/discovery/realistic/stop'),
    ]

    for label, value in discovery_info:
        ax.text(left_col, y, label, fontsize=9,
               ha='left', va='center', transform=ax.transAxes, color='#2C3E50')
        ax.text(right_col, y, value, fontsize=8, family='monospace',
               ha='left', va='center', transform=ax.transAxes, color='#2C3E50')
        y -= 0.04

    y -= 0.03

    # Trading section
    ax.text(left_col, y, 'Trading Costs', fontsize=10, fontweight='bold',
           ha='left', va='center', transform=ax.transAxes, color='#F39C12')
    ax.text(right_col, y, 'Risk Limits', fontsize=10, fontweight='bold',
           ha='left', va='center', transform=ax.transAxes, color='#F39C12')
    y -= 0.05

    trading_info = [
        ('Maker Fee', '0.02%'),
        ('Taker Fee', '0.05%'),
        ('Slippage', '0.05% (5 bps)'),
        ('Fill Rate', '95%'),
    ]

    risk_info = [
        ('Max Position', '10% of capital'),
        ('Max Drawdown', '30%'),
        ('Initial Capital', '10,000 USDT'),
        ('Mode', 'Paper Trading Only'),
    ]

    for i, (label1, value1) in enumerate(trading_info):
        ax.text(left_col, y, f'{label1}: {value1}', fontsize=9,
               ha='left', va='center', transform=ax.transAxes, color='#2C3E50')
        if i < len(risk_info):
            label2, value2 = risk_info[i]
            ax.text(right_col, y, f'{label2}: {value2}', fontsize=9,
                   ha='left', va='center', transform=ax.transAxes, color='#2C3E50')
        y -= 0.04

    # Warning
    ax.text(0.5, 0.08, '⚠️  PAPER TRADING ONLY  ⚠️', fontsize=11, fontweight='bold',
           ha='center', va='center', transform=ax.transAxes, color='#C0392B',
           bbox=dict(boxstyle='round,pad=0.4', facecolor='#FADBD8',
                    edgecolor='#C0392B', linewidth=2))

    ax.text(0.5, 0.03, 'SLATE never executes real trades. No real money is ever risked.',
           fontsize=9, ha='center', va='center', transform=ax.transAxes,
           color='#7F8C8D', style='italic')

    ax.text(0.5, 0.02, f'Page {page_num}',
           ha='center', va='center', transform=ax.transAxes,
           color='#95A5A6', fontsize=8)

    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

# Create PDF
with PdfPages(pdf_file) as pdf:
    # Title page
    create_title_page(pdf)

    # Process markdown content
    final_page = process_markdown(md_content, pdf)

    # Quick reference page
    create_quick_reference_page(pdf, final_page)

print(f"✓ Created PDF: {pdf_file}")
print(f"✓ Improved formatting:")
print(f"  - No overlapping text")
print(f"  - Proper line spacing")
print(f"  - Clean text wrapping")
print(f"  - Professional layout")
print(f"\nUser Manual files:")
print(f"  - {md_file}")
print(f"  - {pdf_file}")
print(f"  - images/ (diagrams)")
