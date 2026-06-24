@echo off
REM Ask questions about a front page via a local Ollama model.
REM Usage: ask_frontpage.bat [DATE] [--model MODEL]   (date as YYYY-MM-DD)
REM   no date -> today
uv run ask-frontpage %*
