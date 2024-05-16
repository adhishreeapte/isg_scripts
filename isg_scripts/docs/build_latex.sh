#!/usr/bin/bash
set -e

sphinx-build -b latex ./source ./build/latex

cd build/latex

pdflatex isgscripts.tex

mv isgscripts.pdf ../../isgscripts.pdf
