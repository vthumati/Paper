"""Convert a Markdown doc -> .docx using pandoc (via pypandoc).
Produces a standalone Word doc with a clickable Table of Contents.

Usage:  py build_docx.py [REQUIREMENTS|HLD]   (default: REQUIREMENTS)
"""
import os
import sys
import pypandoc

HERE = os.path.dirname(os.path.abspath(__file__))

DOCS = {
    "REQUIREMENTS": "Paper — Requirements",
    "HLD": "Paper — High-Level Design (HLD)",
}
name = (sys.argv[1] if len(sys.argv) > 1 else "REQUIREMENTS").upper().replace(".MD", "")
title = DOCS.get(name, name)

SRC = os.path.join(HERE, name + ".md")
OUT = os.path.join(HERE, name + ".docx")

extra_args = [
    "--standalone",
    "--toc",
    "--toc-depth=3",
    "--metadata", "title=" + title,
    "--metadata", "subtitle=An operating system for corporate legal — for Indian startups and funds",
]

pypandoc.convert_file(
    SRC,
    "docx",
    format="gfm",          # GitHub-flavored markdown: tables, fenced code, autolinks
    outputfile=OUT,
    extra_args=extra_args,
)
print("Wrote", OUT, "(%d bytes)" % os.path.getsize(OUT))
