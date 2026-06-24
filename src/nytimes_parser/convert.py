"""
Convert NYT front page PDFs to markdown using embedded text.
Detects column layout so articles from different columns don't get mixed.

Usage:
    pdf-to-markdown 2025-01-01                 # single date
    pdf-to-markdown 2025-01-01 --filter        # strip noise lines
    pdf-to-markdown --all --filter             # convert all, filtered
    pdf-to-markdown --all --force              # reconvert even existing ones
"""

import argparse
import os
import re
import sys
from collections import Counter

import fitz  # PyMuPDF

FRONTPAGES_DIR = "frontpages"
MARKDOWN_DIR = "markdown"

# Noise blocks to skip (print metadata, barcodes, etc.)
SKIP_PATTERNS = ["C M Y K", "Nxxx,", "U(D54G1D)"]


def extract_blocks(page):
    """Extract text blocks with bounding box and dominant font size."""
    raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    blocks = []
    for b in raw:
        if b.get("type") != 0:
            continue
        spans = [s for line in b["lines"] for s in line["spans"]]
        if not spans:
            continue
        text = " ".join(s["text"] for s in spans).strip()
        text = " ".join(text.split())  # normalize whitespace
        if not text or len(text) < 3:
            continue
        if any(p in text for p in SKIP_PATTERNS):
            continue
        max_size = max(s["size"] for s in spans)
        is_bold = any("Bold" in s.get("font", "") or "Black" in s.get("font", "") for s in spans)
        blocks.append({
            "text": text,
            "size": round(max_size, 1),
            "bold": is_bold,
            "x0": b["bbox"][0],
            "y0": b["bbox"][1],
            "x1": b["bbox"][2],
            "y1": b["bbox"][3],
            "width": b["bbox"][2] - b["bbox"][0],
        })
    return blocks


def find_column_starts(blocks, cluster_threshold=30):
    """
    Cluster block left-edges (x0) to find column start positions.
    Values within cluster_threshold px of each other form one column.
    """
    x0s = sorted(b["x0"] for b in blocks)
    if not x0s:
        return [0]

    clusters = []
    current = [x0s[0]]
    for x in x0s[1:]:
        if x - current[-1] <= cluster_threshold:
            current.append(x)
        else:
            clusters.append(min(current))
            current = [x]
    clusters.append(min(current))
    return clusters


def assign_column(x0, col_starts):
    """Return the index of the nearest column start."""
    return min(range(len(col_starts)), key=lambda i: abs(col_starts[i] - x0))


def body_size(blocks):
    """Estimate the body text font size as the most common size among small text."""
    sizes = [round(b["size"]) for b in blocks if b["size"] < 15]
    if not sizes:
        return 9.0
    return Counter(sizes).most_common(1)[0][0]


def classify_block(block, body_sz):
    """Classify a block as headline, subheadline, byline, caption, or body."""
    size = block["size"]
    text = block["text"]
    if size >= body_sz * 2.2:
        return "h1"
    if size >= body_sz * 1.5:
        return "h2"
    if size >= body_sz * 1.3:
        return "h3"
    if text.startswith("By ") or text.startswith("This article is by"):
        return "byline"
    if size < body_sz * 0.85:
        return "caption"
    return "body"


# Lines matching any of these patterns are noise and can be stripped.
# Patterns are matched against the raw text content (markdown formatting stripped).
NOISE_PATTERNS = [
    (re.compile(r"^Continued on Page [A-Z]\d+"), "continuation line"),
    (re.compile(r"\bPAGE [A-Z]\d+"), "section index page ref"),
    (re.compile(r"^(NATIONAL|INTERNATIONAL|BUSINESS|SPORTS|ARTS|OPINION|OBITUARIES|THURSDAY STYLES?)\b"), "section header"),
    (re.compile(r"^Prices in Canada"), "cover price line"),
    (re.compile(r"^VOL\.\s+[CLXVI]+"), "volume/issue line"),
    (re.compile(r"^THE WEATHER$"), "weather label"),
    (re.compile(r"^Weather map is on Page"), "weather map ref"),
    (re.compile(r"^Today,.*high \d+\."), "weather forecast"),
    (re.compile(r"^Tonight,|^Tomorrow,"), "weather forecast continuation"),
]


def _raw_content(line: str) -> str:
    """Strip markdown formatting to get the plain text for noise matching."""
    s = line.strip()
    s = re.sub(r"^#+\s*", "", s)   # headings
    s = re.sub(r"^>\s*", "", s)    # blockquotes
    s = s.strip("*_")              # bold/italic wrappers
    return s.strip()


def filter_noise(md: str) -> str:
    """Remove known noise lines from rendered markdown, preserving structure."""
    out = []
    for line in md.splitlines():
        stripped = line.strip()
        # Always keep blank lines and dividers
        if not stripped or stripped == "---":
            out.append(line)
            continue
        content = _raw_content(line)
        if any(pat.search(content) for pat, _ in NOISE_PATTERNS):
            continue
        out.append(line)

    # Collapse runs of 3+ blank lines down to 2
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return result


def blocks_to_markdown(page):
    blocks = extract_blocks(page)
    if not blocks:
        return ""

    col_starts = find_column_starts(blocks)
    bsz = body_size(blocks)

    # Sort: by column first, then by y within the column
    blocks.sort(key=lambda b: (assign_column(b["x0"], col_starts), b["y0"]))

    # Walk blocks and build article-level sections
    articles = []   # list of dicts: {headline, subheadline, byline, body}
    current = None

    def new_article(headline):
        return {"headline": headline, "subheadline": "", "byline": "", "body": []}

    for b in blocks:
        kind = classify_block(b, bsz)
        text = b["text"]

        if kind == "h1":
            current = new_article(f"# {text}")
            articles.append(current)
        elif kind == "h2":
            if current is None:
                current = new_article(f"## {text}")
                articles.append(current)
            else:
                # Could be a new article headline or a subheadline.
                # Treat as new article if there's already body content.
                if current["body"]:
                    current = new_article(f"## {text}")
                    articles.append(current)
                else:
                    current["subheadline"] = text
        elif kind == "h3":
            if current is None:
                current = new_article(f"### {text}")
                articles.append(current)
            else:
                if current["subheadline"]:
                    current["body"].append(f"*{text}*")
                else:
                    current["subheadline"] = text
        elif kind == "byline":
            if current is not None and not current["byline"]:
                current["byline"] = text
            elif current is not None:
                current["body"].append(f"*{text}*")
        elif kind == "caption":
            if current is not None:
                current["body"].append(f"> {text}")
        else:  # body
            if current is None:
                current = new_article("")
                articles.append(current)
            current["body"].append(text)

    # Render to markdown
    lines = []
    for art in articles:
        if not art["headline"] and not art["body"]:
            continue
        lines.append("---")
        if art["headline"]:
            lines.append(art["headline"])
        if art["subheadline"]:
            lines.append(f"### {art['subheadline']}")
        if art["byline"]:
            lines.append(f"*{art['byline']}*")
        if art["body"]:
            lines.append("")
            lines.extend(art["body"])
        lines.append("")

    return "\n".join(lines).strip()


def pdf_to_markdown(pdf_path, filtered=False):
    doc = fitz.open(pdf_path)
    md = blocks_to_markdown(doc[0])
    if filtered:
        md = filter_noise(md)
    return md


def convert_date(date_str, force=False, filtered=False):
    pdf_path = os.path.join(FRONTPAGES_DIR, f"{date_str}.pdf")
    md_path = os.path.join(MARKDOWN_DIR, f"{date_str}.md")

    if not os.path.exists(pdf_path):
        print(f"  {date_str} - PDF not found, skipping")
        return False
    if os.path.exists(md_path) and not force:
        print(f"  {date_str} - already converted, skipping")
        return True

    try:
        md = pdf_to_markdown(pdf_path, filtered=filtered)
        if md:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# NYT Front Page — {date_str}\n\n")
                f.write(md)
            print(f"  {date_str} - converted ({len(md)} chars)")
        else:
            print(f"  {date_str} - no text extracted")
        return True
    except Exception as e:
        print(f"  {date_str} - error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert NYT front page PDFs to markdown.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("date", nargs="?", help="Single date in YYYY-MM-DD format")
    group.add_argument("--all", action="store_true", help="Convert all PDFs in frontpages/")
    parser.add_argument("--force", action="store_true", help="Reconvert even if markdown already exists")
    parser.add_argument("--filter", action="store_true", dest="filtered",
                        help="Strip noise lines (page refs, section headers, continuation lines, etc.)")
    args = parser.parse_args()

    os.makedirs(MARKDOWN_DIR, exist_ok=True)

    if args.all:
        pdfs = sorted(f for f in os.listdir(FRONTPAGES_DIR) if f.endswith(".pdf"))
        if not pdfs:
            print("No PDFs found in frontpages/")
            sys.exit(1)
        print(f"Converting {len(pdfs)} PDFs{' (filtered)' if args.filtered else ''}...")
        for pdf_file in pdfs:
            convert_date(pdf_file.replace(".pdf", ""), force=args.force, filtered=args.filtered)
    else:
        if not args.date:
            parser.error("Provide a date or use --all")
        convert_date(args.date, force=args.force, filtered=args.filtered)

    print("Done.")


if __name__ == "__main__":
    main()
