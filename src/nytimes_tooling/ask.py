"""
Ask questions about an NYT front page using a local Ollama model.
Reads from pre-converted markdown files (run pdf-to-markdown first).

Usage:
    ask-frontpage                              # today
    ask-frontpage 2025-01-01
    ask-frontpage 2025-01-01 --model llama3:latest
"""

import argparse
import sys

import requests

from ._cli import default_to_today

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3:latest"
MARKDOWN_DIR = "markdown"
SYNTAX = "ask-frontpage [DATE] [--model MODEL]   (date as YYYY-MM-DD)"

SYSTEM_PROMPT = (
    "You are a research assistant helping analyze New York Times front pages. "
    "Answer questions based only on the provided front page content. "
    "Be concise and factual. If something isn't mentioned in the content, say so."
)


def ask_ollama(model, context, question, history):
    if not history:
        # First message — include the full front page as context
        first_message = f"Here is the NYT front page content:\n\n{context}\n\n---\n\n{question}"
        messages = [{"role": "user", "content": first_message}]
    else:
        messages = history + [{"role": "user", "content": question}]

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": messages,
            "system": SYSTEM_PROMPT,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    answer = response.json()["message"]["content"]

    # Store history without re-sending the full context each time
    if not history:
        new_history = [
            {"role": "user", "content": first_message},
            {"role": "assistant", "content": answer},
        ]
    else:
        new_history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]

    return answer, new_history


def main():
    parser = argparse.ArgumentParser(description="Ask questions about an NYT front page (today if no date given).")
    parser.add_argument("date", nargs="?", help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    date_str = args.date if args.date else default_to_today(SYNTAX)
    md_path = f"{MARKDOWN_DIR}/{date_str}.md"

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            context = f.read()
    except FileNotFoundError:
        print(f"Error: {md_path} not found. Run pdf-to-markdown {date_str} first.")
        sys.exit(1)

    print(f"Model  : {args.model}")
    print(f"Date   : {date_str}")
    print(f"Context: {len(context)} chars")
    print("Type your question, or 'quit' to exit.\n")

    history = []
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            break

        try:
            answer, history = ask_ollama(args.model, context, question, history)
            print(f"\nAssistant: {answer}\n")
        except requests.RequestException as e:
            print(f"Error calling Ollama: {e}")


if __name__ == "__main__":
    main()
