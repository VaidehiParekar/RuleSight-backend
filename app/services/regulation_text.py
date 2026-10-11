"""Turns an uploaded regulation file into numbered paragraphs the pipeline can read.

RBI documents number their operative paragraphs "1.", "2.", ... A table of contents and the
preamble use the same numbers, so the body is taken as the longest run of increasing numbers
that starts at 1, preferring the later run (the body follows the contents page).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# "38. Updation" or "54A. ..." at the start of a line.
_PARAGRAPH = re.compile(r"(?m)^[ \t]*(\d{1,3})([A-Z]?)\.\s")
# Contents-page lines end in dot leaders and a page number.
_DOT_LEADER = re.compile(r"\.{5,}")
# A paragraph may skip a few numbers (deleted paragraphs), never many.
_MAX_STEP = 6
# Words that make a sentence an obligation rather than a definition or history.
_DUTY_WORDS = re.compile(r"\b(shall|must|required|ensure|should|mandatory|not be)\b", re.I)


@dataclass(frozen=True)
class Paragraph:
    ref: str
    text: str

    @property
    def number(self) -> str:
        """Top-level number without a letter suffix, e.g. "54" for "54A"."""
        return re.sub(r"[A-Z]$", "", self.ref)

    @property
    def states_a_duty(self) -> bool:
        return bool(_DUTY_WORDS.search(self.text))


def extract_text(content: bytes, file_name: str) -> str:
    """Plain text of a PDF or text file. Unknown binary formats give an empty string."""
    if Path(file_name).suffix.lower() == ".pdf" or content[:5] == b"%PDF-":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if b"\x00" in content[:4096]:
        return ""
    return content.decode("utf-8", errors="replace")


def split_paragraphs(text: str) -> list[Paragraph]:
    """Numbered body paragraphs of an RBI direction, in document order."""
    lines = [line for line in text.splitlines() if not _DOT_LEADER.search(line)]
    clean = "\n".join(lines)
    marks = [
        (m.start(), int(m.group(1)), m.group(1) + m.group(2)) for m in _PARAGRAPH.finditer(clean)
    ]

    def longest_chain(first: int) -> list[int]:
        best: list[int] = []
        for start, (_, number, _) in enumerate(marks):
            if number != first:
                continue
            chain = [start]
            last = first
            for index in range(start + 1, len(marks)):
                candidate = marks[index][1]
                if last <= candidate <= last + _MAX_STEP:
                    chain.append(index)
                    last = candidate
            if len(chain) >= len(best):
                best = chain
        return best

    paragraphs: list[Paragraph] = []
    best = longest_chain(1)
    if len(best) < 2:
        # Circulars leave the opening paragraph unnumbered and start counting at 2.
        from_two = longest_chain(2)
        if len(from_two) > len(best):
            best = from_two
            opening = clean[: marks[best[0]][0]].strip()
            if opening:
                paragraphs.append(Paragraph(ref="1", text=opening))

    for position, index in enumerate(best):
        begin = marks[index][0]
        end = marks[best[position + 1]][0] if position + 1 < len(best) else len(clean)
        body = clean[begin:end].strip()
        if body:
            paragraphs.append(Paragraph(ref=marks[index][2], text=body))
    return paragraphs


def select_paragraphs(
    paragraphs: list[Paragraph],
    *,
    only: set[str] | None,
    limit: int,
) -> list[Paragraph]:
    """Paragraphs to send to the model: the requested numbers if given, otherwise those that
    state a duty, capped at ``limit`` so one run stays within the model quota."""
    if only:
        chosen = [p for p in paragraphs if p.ref in only or p.number in only]
    else:
        chosen = [p for p in paragraphs if p.states_a_duty]
    return chosen[:limit]
