#!/usr/bin/env python3
"""Convert a Markdown file to a styled PDF (Playwright on Windows, WeasyPrint elsewhere)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import markdown

CSS = """
@page {
  size: A4;
  margin: 2cm 2.2cm 2.2cm 2.2cm;
  @bottom-center {
    content: counter(page);
    font-family: "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 9pt;
    color: #64748b;
  }
}

html {
  font-size: 10.5pt;
}

body {
  font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
  line-height: 1.55;
  color: #1e293b;
  max-width: 100%;
}

h1 {
  font-size: 1.65rem;
  line-height: 1.25;
  margin: 0 0 0.75rem;
  color: #0f172a;
  page-break-after: avoid;
}

h2 {
  font-size: 1.25rem;
  margin: 1.75rem 0 0.6rem;
  color: #0f172a;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.25rem;
  page-break-after: avoid;
}

h3 {
  font-size: 1.05rem;
  margin: 1.25rem 0 0.45rem;
  color: #334155;
  page-break-after: avoid;
}

p, li {
  margin: 0.45rem 0;
}

strong {
  color: #0f172a;
}

hr {
  border: none;
  border-top: 1px solid #cbd5e1;
  margin: 1.25rem 0;
}

blockquote {
  margin: 1rem 0;
  padding: 0.65rem 1rem;
  border-left: 4px solid #6366f1;
  background: #f8fafc;
  color: #475569;
  font-size: 0.95rem;
}

blockquote p {
  margin: 0.35rem 0;
}

pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 0.75rem 0.9rem;
  border-radius: 6px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 8.25pt;
  line-height: 1.35;
  white-space: pre;
  overflow-x: auto;
  page-break-inside: avoid;
}

code {
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.92em;
}

p code, li code {
  background: #f1f5f9;
  padding: 0.08rem 0.28rem;
  border-radius: 3px;
  color: #334155;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
  font-size: 9.5pt;
  page-break-inside: avoid;
}

th, td {
  border: 1px solid #cbd5e1;
  padding: 0.4rem 0.55rem;
  text-align: left;
  vertical-align: top;
}

th {
  background: #f1f5f9;
  font-weight: 600;
}

ul, ol {
  margin: 0.5rem 0 0.75rem;
  padding-left: 1.35rem;
}

a {
  color: #4f46e5;
  text-decoration: none;
}

.title-meta {
  color: #64748b;
  font-size: 0.95rem;
  margin-bottom: 1.25rem;
}

.title-meta p {
  margin: 0.2rem 0;
}
"""


def _write_pdf_playwright(html_doc: str, output_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>PrismRAG Technical Article</title>
  <style>{CSS}</style>
</head>
<body>
{html_doc}
</body>
</html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(full_html, wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="A4",
            margin={"top": "2cm", "right": "2.2cm", "bottom": "2.2cm", "left": "2.2cm"},
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=(
                '<div style="width:100%;font-size:9px;color:#64748b;text-align:center;">'
                '<span class="pageNumber"></span></div>'
            ),
        )
        browser.close()


def _write_pdf_weasyprint(html_doc: str, output_path: Path, base_url: str) -> None:
    from weasyprint import HTML

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>PrismRAG Technical Article</title>
  <style>{CSS}</style>
</head>
<body>
{html_doc}
</body>
</html>"""
    HTML(string=full_html, base_url=base_url).write_pdf(
        target=str(output_path),
        stylesheets=[],
    )


def convert(input_path: Path, output_path: Path) -> None:
    md_text = input_path.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        md_text,
        extensions=[
            "markdown.extensions.extra",
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.nl2br",
            "markdown.extensions.sane_lists",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _write_pdf_playwright(body_html, output_path)
    except Exception as playwright_err:
        if sys.platform == "win32":
            raise RuntimeError(
                "Playwright PDF export failed. Run: playwright install chromium"
            ) from playwright_err
        _write_pdf_weasyprint(body_html, output_path, str(input_path.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown to PDF")
    parser.add_argument("input", type=Path, help="Input .md file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .pdf file (default: same name as input)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    output = args.output or args.input.with_suffix(".pdf")
    convert(args.input, output)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
