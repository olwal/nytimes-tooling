"""
Ask questions about an NYT front page using a local Ollama model.
Reads from pre-converted markdown files (run pdf-to-markdown first).

Usage:
    ask-frontpage 2025-01-01
    ask-frontpage 2025-01-01 --model llama3:latest
"""

import argparse
import sys

import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3:latest"
MARKDOWN_DIR = "markdown"

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
    parser = argparse.ArgumentParser(description="Ask questions about an NYT front page.")
    parser.add_argument("date", help="Date in YYYY-MM-DD format (e.g. 2025-01-01)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    md_path = f"{MARKDOWN_DIR}/{args.date}.md"

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            context = f.read()
    except FileNotFoundError:
        print(f"Error: {md_path} not found. Run pdf-to-markdown {args.date} first.")
        sys.exit(1)

    print(f"Model  : {args.model}")
    print(f"Date   : {args.date}")
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
