#!/usr/bin/env python3
"""
Simple PDF creation for SLATE User Manual without external dependencies.
Uses only standard library and matplotlib (which is already available).
"""

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path

# Read the markdown file
md_file = Path('SLATE_User_Manual.md')
with open(md_file, 'r', encoding='utf-8') as f:
    md_content = f.read()

# Create PDF
pdf_file = Path('SLATE_User_Manual.pdf')

with PdfPages(pdf_file) as pdf:
    # Title page
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis('off')

    ax.text(0.5, 0.7, 'SLATE', fontsize=48, fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, color='#2C3E50')
    ax.text(0.5, 0.6, 'User Manual', fontsize=36, fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, color='#34495E')
    ax.text(0.5, 0.5, 'Strategy Learning & Autonomous Trading Engine', fontsize=18,
            ha='center', va='center', transform=ax.transAxes, color='#7F8C8D')
    ax.text(0.5, 0.4, 'Version 1.0.0', fontsize=14,
            ha='center', va='center', transform=ax.transAxes, color='#95A5A6')
    ax.text(0.5, 0.35, 'April 30, 2026', fontsize=14,
            ha='center', va='center', transform=ax.transAxes, color='#95A5A6')
    ax.text(0.5, 0.25, '⚠️ PAPER TRADING ONLY', fontsize=14, fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, color='#E74C3C')

    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

    # Process content
    lines = md_content.split('\n')
    page_num = 1
    y_position = 0.85
    current_page_content = []

    for line in lines:
        # Main chapter titles
        if line.startswith('# ') and not line.startswith('## '):
            # Save current page if we have content
            if current_page_content:
                fig, ax = plt.subplots(figsize=(8.5, 11))
                ax.axis('off')

                y = 0.9
                for content in current_page_content:
                    ax.text(0.1, y, content, fontsize=9,
                           ha='left', va='top', transform=ax.transAxes, color='#2C3E50')
                    y -= 0.02

                ax.text(0.5, 0.02, f'Page {page_num}',
                       ha='center', va='center', transform=ax.transAxes, color='#95A5A6')
                pdf.savefig(fig, bbox_inches='tight')
                plt.close()
                page_num += 1

            # New chapter page
            fig, ax = plt.subplots(figsize=(8.5, 11))
            ax.axis('off')

            chapter_title = line.lstrip('#').strip()
            ax.text(0.5, 0.6, chapter_title, fontsize=20, fontweight='bold',
                   ha='center', va='center', transform=ax.transAxes, color='#2C3E50')
            ax.text(0.5, 0.02, f'Page {page_num}',
                   ha='center', va='center', transform=ax.transAxes, color='#95A5A6')

            pdf.savefig(fig, bbox_inches='tight')
            plt.close()
            page_num += 1
            y_position = 0.85
            current_page_content = []

        # Section headers
        elif line.startswith('## '):
            section_title = line.lstrip('##').strip()
            current_page_content.append(f'\n{section_title}')
            y_position -= 0.03

        # Image references
        elif line.strip().startswith('![') and '](images/' in line:
            img_name = line.split('](images/')[1].rstrip(')')
            img_path = Path('images') / img_name

            if img_path.exists():
                fig, ax = plt.subplots(figsize=(8.5, 11))
                ax.axis('off')

                try:
                    from PIL import Image
                    img = Image.open(img_path)

                    # Calculate size
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height

                    max_width = 7.0
                    max_height = 8.0

                    if aspect_ratio > max_width / max_height:
                        display_width = max_width
                        display_height = max_width / aspect_ratio
                    else:
                        display_height = max_height
                        display_width = max_height * aspect_ratio

                    # Center image
                    x_offset = (8.5 - display_width) / 2
                    y_offset = (11 - display_height) / 2

                    ax.imshow(img, extent=[x_offset, x_offset + display_width,
                                                y_offset, y_offset + display_height])

                    ax.text(0.5, 0.02, f'Page {page_num}',
                           ha='center', va='center', transform=ax.transAxes, color='#95A5A6')

                    pdf.savefig(fig, bbox_inches='tight')
                    plt.close()
                    page_num += 1
                    y_position = 0.85
                    current_page_content = []
                except Exception as e:
                    print(f"Warning: Could not include image {img_name}: {e}")
                    current_page_content.append(f'[Image: {img_name}]')

        # Code blocks
        elif line.strip().startswith('```'):
            continue  # Skip code block markers

        # Regular content
        elif line.strip():
            current_page_content.append(line)

            # Check if we need a new page
            if y_position < 0.1:
                fig, ax = plt.subplots(figsize=(8.5, 11))
                ax.axis('off')

                y = 0.9
                for content in current_page_content:
                    ax.text(0.1, y, content, fontsize=9,
                           ha='left', va='top', transform=ax.transAxes, color='#2C3E50')
                    y -= 0.02

                ax.text(0.5, 0.02, f'Page {page_num}',
                       ha='center', va='center', transform=ax.transAxes, color='#95A5A6')

                pdf.savefig(fig, bbox_inches='tight')
                plt.close()
                page_num += 1
                current_page_content = []
                y_position = 0.85

    # Final page
    if current_page_content:
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis('off')

        y = 0.9
        for content in current_page_content:
            ax.text(0.1, y, content, fontsize=9,
                   ha='left', va='top', transform=ax.transAxes, color='#2C3E50')
            y -= 0.02

        ax.text(0.5, 0.02, f'Page {page_num}',
               ha='center', va='center', transform=ax.transAxes, color='#95A5A6')

        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        page_num += 1

    # Quick reference page
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis('off')

    ax.text(0.5, 0.9, 'Quick Reference', fontsize=18, fontweight='bold',
           ha='center', va='center', transform=ax.transAxes, color='#2C3E50')

    quick_ref = [
        ('📡 Server Port', '8788'),
        ('📊 Main Dashboard', 'http://localhost:8788/dashboard'),
        ('🔬 Discovery Dashboard', 'http://localhost:8788/discovery-dashboard'),
        ('📚 API Documentation', 'http://localhost:8788/docs'),
        ('⚠️  Mode', 'Paper Trading Only'),
        ('💰 Initial Capital', '10,000 USDT'),
        ('📉 Maker Fee', '0.02%'),
        ('📈 Taker Fee', '0.05%'),
        ('💸 Slippage', '5 bps (0.05%)'),
        ('🎯 Max Position', '10% of capital'),
    ]

    y = 0.75
    for label, value in quick_ref:
        ax.text(0.3, y, label, fontsize=11, fontweight='bold',
               ha='left', va='center', transform=ax.transAxes, color='#34495E')
        ax.text(0.7, y, value, fontsize=11,
               ha='left', va='center', transform=ax.transAxes, color='#2C3E50')
        y -= 0.06

    ax.text(0.5, 0.02, f'Page {page_num}',
           ha='center', va='center', transform=ax.transAxes, color='#95A5A6')

    pdf.savefig(fig, bbox_inches='tight')
    plt.close()

print(f"✓ Created PDF: {pdf_file}")
print(f"✓ Total pages: {page_num}")
print(f"\nUser Manual files created:")
print(f"  - {md_file}")
print(f"  - {pdf_file}")
print(f"  - images/ (diagrams)")
