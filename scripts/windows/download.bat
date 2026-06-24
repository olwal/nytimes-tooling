@echo off
REM Download NYT front page PDF(s).
REM Usage: download.bat [START_DATE] [END_DATE]   (dates as YYYY-MM-DD)
REM   no args        -> today only
REM   one date       -> that date only
REM   two dates      -> the inclusive range
uv run download-frontpages %*
