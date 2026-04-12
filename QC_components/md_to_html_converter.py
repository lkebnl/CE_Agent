#!/usr/bin/env python3
# Author      : Lingyun Ke
# Email       : lingyun.lke@gmail.com
# Created     : 2026-04-05
# Project     : DUNE CE WIB FEMB QC — NLP-Driven Test System
# Institution : BNL (Brookhaven National Laboratory)
# Version     : 1.0.0
# Description : Markdown-to-HTML report converter
"""
Markdown to HTML Converter for FEMB QC Reports
Converts Markdown-format test reports to professional scientific-style HTML reports
"""

import os
import sys
import glob
import re


def get_html_template(title, content):
    """Generate a complete HTML document with professional scientific-style CSS"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        /* Professional scientific-style CSS */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}

        .container {{
            background-color: white;
            padding: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 4px;
        }}

        h1 {{
            color: #1a1a1a;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 15px;
            margin-bottom: 30px;
            font-size: 2.2em;
            font-weight: 600;
        }}

        h2 {{
            color: #2c3e50;
            margin-top: 40px;
            margin-bottom: 20px;
            font-size: 1.8em;
            font-weight: 600;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
        }}

        h3 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 1.4em;
            font-weight: 600;
        }}

        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 30px 0;
        }}

        /* Table styles */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            font-size: 0.95em;
        }}

        table thead {{
            background-color: #34495e;
            color: white;
        }}

        table th {{
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            border: 1px solid #2c3e50;
        }}

        table td {{
            padding: 10px 15px;
            border: 1px solid #ddd;
        }}

        table tbody tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}

        table tbody tr:hover {{
            background-color: #e8f4f8;
        }}

        /* Status labels */
        .status-pass {{
            color: #27ae60;
            font-weight: bold;
        }}

        .status-fail {{
            color: #e74c3c;
            font-weight: bold;
        }}

        .status-warning {{
            color: #f39c12;
            font-weight: bold;
        }}

        /* Image styles */
        img {{
            max-width: 100%;
            height: auto;
            margin: 15px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 5px;
            background-color: white;
        }}

        /* Link styles */
        a {{
            color: #3498db;
            text-decoration: none;
            transition: color 0.2s;
        }}

        a:hover {{
            color: #2980b9;
            text-decoration: underline;
        }}

        /* Paragraphs */
        p {{
            margin: 10px 0;
        }}

        /* Lists */
        ul, ol {{
            margin: 10px 0 10px 30px;
        }}

        li {{
            margin: 5px 0;
        }}

        /* Code blocks */
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}

        pre {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 15px 0;
        }}

        pre code {{
            padding: 0;
        }}

        /* Print styles */
        @media print {{
            body {{
                background-color: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
                padding: 20px;
            }}

            @page {{
                margin: 2cm;
            }}
        }}

        /* Colored text */
        span[style*="color: green"] {{
            color: #27ae60 !important;
            font-weight: bold;
        }}

        span[style*="color: red"] {{
            color: #e74c3c !important;
            font-weight: bold;
        }}
    </style>
</head>
<body>
<div class="container">
{content}
</div>
</body>
</html>
'''


def markdown_to_html(md_content):
    """
    Simple Markdown to HTML converter.
    Handles common Markdown syntax.
    """
    html = md_content

    # Convert headings (process longer patterns first)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Convert horizontal rules
    html = re.sub(r'^---+$', r'<hr>', html, flags=re.MULTILINE)
    html = re.sub(r'^___ +$', r'<hr>', html, flags=re.MULTILINE)

    # Convert images ![alt](src)
    html = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'<img src="\2" alt="\1">', html)

    # Convert links [text](url)
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

    # Convert bold **text** or __text__
    html = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', html)

    # Convert italic *text* or _text_
    html = re.sub(r'\*([^\*]+)\*', r'<em>\1</em>', html)
    html = re.sub(r'_([^_]+)_', r'<em>\1</em>', html)

    # Convert inline code `code`
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Convert paragraphs (consecutive non-empty lines)
    lines = html.split('\n')
    in_paragraph = False
    result_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip lines that are already HTML tags
        if stripped.startswith('<h') or stripped.startswith('<hr') or \
           stripped.startswith('<img') or stripped.startswith('<table') or \
           stripped.startswith('</table') or stripped.startswith('<div'):
            if in_paragraph:
                result_lines.append('</p>')
                in_paragraph = False
            result_lines.append(line)
        elif stripped == '':
            if in_paragraph:
                result_lines.append('</p>')
                in_paragraph = False
            result_lines.append(line)
        else:
            if not in_paragraph and not stripped.startswith('|'):  # Do not wrap table rows
                result_lines.append('<p>')
                in_paragraph = True
            result_lines.append(line)

    if in_paragraph:
        result_lines.append('</p>')

    html = '\n'.join(result_lines)

    return html


def convert_md_to_html(md_file, output_file=None):
    """
    Convert a single Markdown file to HTML.

    Args:
        md_file: Path to the Markdown file
        output_file: Output HTML file path (auto-generated if None)

    Returns:
        Output file path
    """
    # Read Markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Extract title (first # heading)
    title_match = re.search(r'^#\s+(.+)$', md_content, re.MULTILINE)
    title = title_match.group(1) if title_match else "FEMB QC Test Report"

    # Convert Markdown to HTML
    html_content = markdown_to_html(md_content)

    # Generate complete HTML document
    full_html = get_html_template(title, html_content)

    # Determine output filename
    if output_file is None:
        output_file = os.path.splitext(md_file)[0] + '.html'

    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"Converted: {md_file} -> {output_file}")
    return output_file


def batch_convert(directory='.', pattern='report_FEMB_*.md'):
    """
    Batch convert Markdown files in a directory.

    Args:
        directory: Directory to search
        pattern: File match pattern

    Returns:
        Number of files converted
    """
    search_pattern = os.path.join(directory, pattern)
    md_files = glob.glob(search_pattern)

    if not md_files:
        print(f"No matching files found: {search_pattern}")
        return 0

    print(f"Found {len(md_files)} Markdown file(s)")
    print("=" * 60)

    converted_count = 0
    for md_file in md_files:
        try:
            convert_md_to_html(md_file)
            converted_count += 1
        except Exception as e:
            print(f"Conversion failed: {md_file}")
            print(f"  Error: {e}")

    print("=" * 60)
    print(f"Conversion complete: {converted_count}/{len(md_files)} file(s)")

    return converted_count


def main():
    """Main function"""
    if len(sys.argv) > 1:
        # If arguments provided, convert the specified file or directory
        arg = sys.argv[1]
        if os.path.isfile(arg):
            convert_md_to_html(arg)
        elif os.path.isdir(arg):
            batch_convert(arg)
        else:
            print(f"Error: File or directory does not exist: {arg}")
            sys.exit(1)
    else:
        # Otherwise convert all report files in the current directory
        batch_convert('.')


if __name__ == '__main__':
    main()
