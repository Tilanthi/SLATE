#!/usr/bin/env python3
"""
Convert SLATE User Manual from Markdown to PDF
"""

import weasyprint
from pathlib import Path
import markdown
import sys

def convert_markdown_to_pdf(md_file, pdf_file):
    """Convert Markdown file to PDF using WeasyPrint"""

    # Read markdown content
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Convert markdown to HTML
    html_body = markdown.markdown(
        md_content,
        extensions=[
            'tables',
            'fenced_code',
            'codehilite',
            'toc',
            'sane_lists',
            'nl2br',
            'extra'
        ]
    )

    # Create complete HTML document with styling
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>SLATE User Manual</title>
        <style>
            @page {{
                size: A4;
                margin: 2cm;
                @bottom-center {{
                    content: counter(page);
                    font-size: 10pt;
                    color: #666;
                }}
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}

            h1 {{
                color: #0066cc;
                border-bottom: 3px solid #0066cc;
                padding-bottom: 10px;
                page-break-before: always;
                margin-top: 50px;
            }}

            h1:first-of-type {{
                page-break-before: auto;
                margin-top: 0;
            }}

            h2 {{
                color: #0066cc;
                border-bottom: 1px solid #cce5ff;
                padding-bottom: 5px;
                margin-top: 30px;
                page-break-after: avoid;
            }}

            h3 {{
                color: #0066cc;
                margin-top: 20px;
                page-break-after: avoid;
            }}

            h4 {{
                color: #666;
                font-weight: bold;
                margin-top: 15px;
                page-break-after: avoid;
            }}

            p {{
                margin-bottom: 15px;
                text-align: justify;
            }}

            code {{
                background-color: #f5f5f5;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Monaco', 'Courier New', monospace;
                font-size: 0.9em;
            }}

            pre {{
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                overflow-x: auto;
                page-break-inside: avoid;
            }}

            pre code {{
                background-color: transparent;
                padding: 0;
                border: none;
            }}

            blockquote {{
                border-left: 4px solid #0066cc;
                padding-left: 20px;
                margin: 20px 0;
                color: #666;
                font-style: italic;
            }}

            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
                page-break-inside: avoid;
            }}

            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}

            th {{
                background-color: #0066cc;
                color: white;
                font-weight: bold;
            }}

            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}

            ul, ol {{
                margin: 15px 0;
                padding-left: 30px;
            }}

            li {{
                margin: 5px 0;
            }}

            strong {{
                color: #0066cc;
                font-weight: bold;
            }}

            a {{
                color: #0066cc;
                text-decoration: none;
            }}

            a:hover {{
                text-decoration: underline;
            }}

            hr {{
                border: none;
                border-top: 1px solid #ddd;
                margin: 30px 0;
            }}

            .toc {{
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 20px;
                margin: 20px 0;
                page-break-after: always;
            }}

            .toc h2 {{
                margin-top: 0;
                border-bottom: none;
            }}

            .toc ul {{
                list-style-type: none;
                padding-left: 0;
            }}

            .toc a {{
                color: #0066cc;
                display: block;
                padding: 3px 0;
            }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    # Convert HTML to PDF
    try:
        pdf_doc = weasyprint.HTML(string=html_template).render()
        pdf_doc.write_pdf(pdf_file)
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

    print("Converting SLATE User Manual to PDF...")
    if convert_markdown_to_pdf(md_path, pdf_path):
        print(f"\n✓ PDF created successfully: {pdf_path}")
    else:
        print(f"\n✗ Failed to create PDF")
        sys.exit(1)
