@echo off
REM Convert a downloaded front page PDF to markdown.
REM Usage: pdf_to_markdown.bat [DATE] [--filter] [--force]   (date as YYYY-MM-DD)
REM   no date -> today
uv run pdf-to-markdown %*
