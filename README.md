# NYT Front Page Tooling

Download, parse, and query New York Times front page PDFs using a local [Ollama](https://ollama.com) model.

NYT publishes a public PDF of each day's front page at a fixed URL pattern (no subscription required):

```
https://static01.nyt.com/images/YYYY/MM/DD/nytfrontpage/scan.pdf
```

The pipeline has three steps:

```
download-frontpages  →  pdf-to-markdown  →  ask-frontpage
   (PDF files)            (markdown files)      (Q&A via Ollama)
```

## Setup

This project is managed with [uv](https://docs.astral.sh/uv/). Install uv, then:

```bash
uv sync
```

That creates a `.venv/` and installs all dependencies from the lockfile. To run a command:

```bash
uv run download-frontpages
```

(Or activate the venv and call the commands directly.)

For the Q&A step, Ollama must be running locally with at least one model pulled:

```bash
ollama pull llama3
```

## Commands

### `download-frontpages`

Downloads front page PDFs into `frontpages/YYYY-MM-DD.pdf`.

- With **no date**, downloads **today** only
- With **one date**, downloads **that date** only
- With **two dates**, downloads the **inclusive range**
- Skips files already downloaded — safe to resume if interrupted
- Randomized 2–4s delay between requests; handles 404s gracefully

```bash
uv run download-frontpages                          # today only
uv run download-frontpages 2025-01-01               # one date only
uv run download-frontpages 2025-01-01 2025-03-06    # a date range
```

### `pdf-to-markdown`

Converts front page PDFs to structured markdown using the PDF's embedded text (not OCR). Detects the 6-column layout and sorts text blocks by column so articles from different columns don't get interleaved. Each article becomes a section with headline, subheadline, byline, and body, separated by `---`.

The `--filter` flag strips known layout noise (continuation lines, section index refs, weather text, volume/price lines).

```bash
uv run pdf-to-markdown                       # today
uv run pdf-to-markdown 2025-01-01 --filter   # one date, strip noise
uv run pdf-to-markdown --all --filter        # convert all
uv run pdf-to-markdown --all --filter --force  # force reconvert
```

Output is saved to `markdown/YYYY-MM-DD.md`. Converting a single date that hasn't
been downloaded exits with an error telling you to download it first.

### `ask-frontpage`

Interactive Q&A about a front page using a local Ollama model. Reads the pre-converted markdown (avoiding OCR hallucinations). The full page is sent on the first question; later questions send only the conversation history to keep context efficient.

```bash
uv run ask-frontpage                         # today
uv run ask-frontpage 2025-06-15
uv run ask-frontpage 2025-06-15 --model deepseek-coder-v2:16b
```

Type `quit` or press `Ctrl+C` to exit.

## Layout

```
nytimes-tooling/
├── pyproject.toml              # project metadata + dependencies (uv)
├── uv.lock                     # pinned, reproducible dependency versions
├── src/nytimes_tooling/
│   ├── download.py             # Step 1: download PDFs
│   ├── convert.py              # Step 2: PDF → markdown
│   ├── ask.py                  # Step 3: Q&A via Ollama
│   └── _cli.py                 # shared CLI helpers (today default, syntax)
├── scripts/windows/            # .bat wrappers that forward args to the commands
├── frontpages/                 # downloaded PDFs (git-ignored)
└── markdown/                   # converted markdown (git-ignored)
```

## Known limitations

- Articles continuing across columns may have body text split across sections
- Captions/teasers near column boundaries sometimes land under the wrong article
- `--filter` removes the most common noise; some layout artifacts may remain
