@echo off
echo ========================================
echo STEP 1: Replacing Section 5 File
echo ========================================

cd /d d:\HCMUT\252\thesis\MP-AI-252\docs\content

echo Backing up old file...
copy /Y sec5_tinyML.tex sec5_tinyML_OLD_backup.tex

echo Replacing with new version...
copy /Y sec5_personalization_v2.tex sec5_tinyML.tex

echo File replaced successfully!
echo.

echo ========================================
echo STEP 2: Compiling LaTeX - Full Cycle
echo ========================================

cd /d d:\HCMUT\252\thesis\MP-AI-252\docs

echo Cleaning old files...
del main.pdf 2>nul
del main.aux 2>nul
del main.bbl 2>nul
del main.blg 2>nul

echo.
echo [1/4] First LaTeX pass...
pdflatex -interaction=nonstopmode main.tex
if errorlevel 1 (
    echo ERROR in first pass!
    pause
    exit /b 1
)

echo.
echo [2/4] Running BibTeX...
bibtex main
if errorlevel 1 (
    echo WARNING in bibtex - may be OK if no new citations
)

echo.
echo [3/4] Second LaTeX pass...
pdflatex -interaction=nonstopmode main.tex
if errorlevel 1 (
    echo ERROR in second pass!
    pause
    exit /b 1
)

echo.
echo [4/4] Third LaTeX pass...
pdflatex -interaction=nonstopmode main.tex
if errorlevel 1 (
    echo ERROR in third pass!
    pause
    exit /b 1
)

echo.
echo ========================================
echo BUILD SUCCESSFUL!
echo ========================================
echo Output: d:\HCMUT\252\thesis\MP-AI-252\docs\main.pdf
echo Backup: d:\HCMUT\252\thesis\MP-AI-252\docs\content\sec5_tinyML_OLD_backup.tex
echo ========================================
echo.
echo Opening PDF...
start main.pdf

pause
