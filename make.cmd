@echo off
rem Windows target launcher. GNU Make can use the accompanying Makefile.
python "%~dp0run.py" %*
exit /b %errorlevel%
