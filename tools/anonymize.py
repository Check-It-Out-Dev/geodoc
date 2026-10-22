# geodoc — client-intake anonymizer. TRUE redaction via PyMuPDF redact
# annotations (text is REMOVED from the PDF, not covered). Masks personal data
# while preserving everything the pipeline needs: coordinates, parcel numbers,
# TERYT, dates, ZRD/BPP/STB/RZG attributes are untouched.
#
# What gets redacted:
#   - PESEL-shaped numbers (11 digits, with the registry-number guard: we skip
#     matches embedded in longer digit runs or decimal contexts)
#   - phone numbers (+48 / 9-digit groups), e-mail addresses
#   - every name given in --names (one per line; case-insensitive, whole words)
#     — the operator lists the owners/parties per job; wykonawca names may stay
#       (public professional register) unless listed too.
#
# Usage: python tools/anonymize.py input.pdf output.pdf [--names names.txt]

import argparse
import re
import sys

import fitz

PATTERNS = [
    re.compile(r"(?<![\d.])\d{11}(?!\d)"),                     # PESEL-shaped
    re.compile(r"(?<!\d)(?:\+48[ -]?)?\d{3}[ -]\d{3}[ -]\d{3}(?!\d)"),  # phone
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),                    # e-mail
]


def redact(inp, outp, names=None):
    doc = fitz.open(inp)
    hits = 0
    name_res = [re.compile(rf"(?i)(?<!\w){re.escape(n.strip())}(?!\w)")
                for n in (names or []) if n.strip()]
    for page in doc:
        text = page.get_text("text")
        targets = set()
        for rx in PATTERNS + name_res:
            for m in rx.finditer(text):
                targets.add(m.group(0))
        for t in targets:
            for rect in page.search_for(t):
                page.add_redact_annot(rect, fill=(0, 0, 0))
                hits += 1
        if targets:
            page.apply_redactions()
    doc.save(outp, garbage=3, deflate=True)
    doc.close()
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--names", help="file with one name per line to redact")
    a = ap.parse_args()
    names = open(a.names, encoding="utf-8").read().splitlines() if a.names else []
    n = redact(a.input, a.output, names)
    print(f"redactions applied: {n} -> {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
