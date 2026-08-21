#!/usr/bin/env python3
"""Parses and indexes the SNANA manual LaTeX source (Phase 1.6).

Splits the manual into logical chunks by sections and subsections, cleans the LaTeX syntax,
and outputs a JSON file that can be shipped as package data.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

# Maintainer-only script (never run by end users — see Phase 1.8: the built
# manual_chunks.json ships as package data). Not hardcoded to one person's path:
# override with SNANA_MANUAL_TEX_PATH, or pass a path as argv[1].
MANUAL_PATH = Path(
    (len(__import__("sys").argv) > 1 and __import__("sys").argv[1])
    or os.environ.get("SNANA_MANUAL_TEX_PATH")
    or "/global/homes/a/ayanmitr/SNANA/doc/snana_manual.tex"
)
OUTPUT_PATH = Path(__file__).resolve().parent / "manual_chunks.json"

def clean_latex(text: str) -> str:
    # Remove comment lines starting with % (but keep \%)
    cleaned_lines = []
    for line in text.splitlines():
        if line.strip().startswith("%"):
            continue
        # Split on unescaped %
        parts = re.split(r'(?<!\\)%', line)
        line = parts[0]
        cleaned_lines.append(line)
    
    text = "\n".join(cleaned_lines)
    
    # Remove LaTeX structural elements
    text = re.sub(r'\\label\{.*?\}', '', text)
    text = re.sub(r'\\ref\{.*?\}', '', text)
    text = re.sub(r'\\cite\{.*?\}', '', text)
    text = re.sub(r'\\begin\{.*?\}', '', text)
    text = re.sub(r'\\end\{.*?\}', '', text)
    text = re.sub(r'\\clearpage', '', text)
    text = re.sub(r'\\noindent', '', text)
    text = re.sub(r'\\item', '', text)
    
    # Remove formatting styles/families
    text = re.sub(r'\\(tt|bf|em|it|sf|rm|sc|Huge|huge|LARGE|Large|large|normalsize|small|footnotesize|scriptsize|tiny)\b', '', text)
    
    # Remove braces
    text = text.replace('{', '').replace('}', '').replace('\\\\', '\n')
    
    # Standardize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def main() -> None:
    if not MANUAL_PATH.exists():
        print(f"Error: Manual not found at {MANUAL_PATH}")
        return

    print(f"Reading manual from {MANUAL_PATH}...")
    with open(MANUAL_PATH, errors="replace") as f:
        lines = f.readlines()

    chunks = []
    current_chunk_lines = []
    current_section = "Header"
    current_subsection = ""
    current_subsubsection = ""
    start_line = 1

    heading_regex = re.compile(r'\\(section|subsection|subsubsection)\*?\{(.*?)\}')

    for idx, line in enumerate(lines, 1):
        match = heading_regex.search(line)
        if match:
            # Save previous chunk
            if current_chunk_lines:
                raw_text = "".join(current_chunk_lines)
                cleaned_text = clean_latex(raw_text)
                if cleaned_text:
                    chunks.append({
                        "section": current_section,
                        "subsection": current_subsection,
                        "subsubsection": current_subsubsection,
                        "start_line": start_line,
                        "end_line": idx - 1,
                        "text": cleaned_text
                    })
            
            # Extract heading information
            h_type = match.group(1)
            h_title = match.group(2).strip()
            # Clean heading title
            h_title = re.sub(r'\\[a-zA-Z]+', '', h_title).replace('{', '').replace('}', '').replace('\\', '').strip()
            
            if h_type == "section":
                current_section = h_title
                current_subsection = ""
                current_subsubsection = ""
            elif h_type == "subsection":
                current_subsection = h_title
                current_subsubsection = ""
            elif h_type == "subsubsection":
                current_subsubsection = h_title
                
            current_chunk_lines = []
            start_line = idx

        current_chunk_lines.append(line)

    # Save final chunk
    if current_chunk_lines:
        raw_text = "".join(current_chunk_lines)
        cleaned_text = clean_latex(raw_text)
        if cleaned_text:
            chunks.append({
                "section": current_section,
                "subsection": current_subsection,
                "subsubsection": current_subsubsection,
                "start_line": start_line,
                "end_line": len(lines),
                "text": cleaned_text
            })

    print(f"Generated {len(chunks)} chunks.")
    
    with open(OUTPUT_PATH, "w") as f_out:
        json.dump(chunks, f_out, indent=2)
        
    print(f"Saved manual index to {OUTPUT_PATH.name}")

if __name__ == "__main__":
    main()
