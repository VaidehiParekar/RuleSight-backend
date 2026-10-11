"""Stores an uploaded evidence table (CSV) so gaps can cite it.

The code comes from the file name when it carries one (e.g. "EVD-07_..." -> EVD-07), otherwise
from the document id. Rows are stored as text exactly as uploaded; nothing is interpreted here.
"""

from __future__ import annotations

import csv
import io
import json
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

_CODE = re.compile(r"\b(EVD-\d+)", re.IGNORECASE)


class EvidenceFormatError(ValueError):
    """The file is not a readable evidence table."""


def evidence_code(file_name: str, fallback: str) -> str:
    match = _CODE.search(file_name)
    return (match.group(1) if match else fallback).upper()[:32]


def parse_table(content: bytes) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
    table = [row for row in reader if any(cell.strip() for cell in row)]
    if len(table) < 2:
        raise EvidenceFormatError("Evidence table needs a header row and at least one data row.")
    header, *rows = table
    return [h.strip() for h in header], [[cell.strip() for cell in row] for row in rows]


def import_evidence(
    session: Session, *, content: bytes, file_name: str, title: str, fallback_code: str
) -> str:
    """Upserts one evidence row inside the caller's transaction. Returns its code."""
    columns, rows = parse_table(content)
    code = evidence_code(file_name, fallback_code)
    session.execute(
        text("""
            INSERT INTO evidence (
                id, code, title, file_name, control_codes, columns, rows, flagged_cells, summary
            ) VALUES (
                :id, :code, :title, :file_name, '[]'::jsonb, CAST(:columns AS jsonb),
                CAST(:rows AS jsonb), '[]'::jsonb, :summary
            )
            ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title,
                file_name = EXCLUDED.file_name,
                columns = EXCLUDED.columns,
                rows = EXCLUDED.rows,
                summary = EXCLUDED.summary
        """),
        {
            "id": code.lower(),
            "code": code,
            "title": title[:255],
            "file_name": file_name[:255],
            "columns": json.dumps(columns),
            "rows": json.dumps(rows),
            "summary": f"{len(rows)} rows, {len(columns)} columns, uploaded as {file_name}.",
        },
    )
    return code
