"""Loads a bank's risk control matrix (CSV) into the controls table.

Expected header (extra columns are ignored, missing optional ones are left empty):
control_id, control_name, description, source_document, source_section, owner, frequency,
control_type, automation, evidence_expected, rbi_reference

Rows are upserted by control code, so uploading a revised matrix updates the controls in place.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

REQUIRED = ("control_id", "control_name", "description")
_TEXT_DEFAULT = "Not specified"


class RcmFormatError(ValueError):
    """The file is not a control matrix this importer understands."""


@dataclass(frozen=True)
class ControlRow:
    code: str
    name: str
    description: str
    owner: str
    frequency: str
    control_type: str
    automation: str
    source_document: str | None
    source_section: str | None
    evidence_expected: str | None
    rbi_reference: str | None
    topic: str


def _topic(rbi_reference: str | None, name: str) -> str:
    """Short topic from the regulation reference, e.g. "RBI KYC para 37(a)" -> "KYC"."""
    if rbi_reference:
        match = re.match(
            r"\s*(?:RBI\s+)?(.+?)\s+(?:paras?|paragraphs?|sections?|§)\b", rbi_reference, re.I
        )
        if match:
            return match.group(1).strip()[:128]
    return name[:128]


def parse_rcm(content: bytes) -> list[ControlRow]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
    header = {h.strip().lower() for h in reader.fieldnames or []}
    missing = [column for column in REQUIRED if column not in header]
    if missing:
        raise RcmFormatError(f"Control matrix is missing columns: {', '.join(missing)}")

    rows: list[ControlRow] = []
    for raw in reader:
        row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        if not row.get("control_id"):
            continue
        rbi_reference = row.get("rbi_reference") or None
        rows.append(
            ControlRow(
                code=row["control_id"].upper()[:32],
                name=row["control_name"][:255],
                description=row["description"],
                owner=(row.get("owner") or _TEXT_DEFAULT)[:128],
                frequency=(row.get("frequency") or _TEXT_DEFAULT)[:64],
                control_type=(row.get("control_type") or _TEXT_DEFAULT)[:64],
                automation=(row.get("automation") or _TEXT_DEFAULT)[:64],
                source_document=(row.get("source_document") or None),
                source_section=(row.get("source_section") or None),
                evidence_expected=row.get("evidence_expected") or None,
                rbi_reference=rbi_reference[:64] if rbi_reference else None,
                topic=_topic(rbi_reference, row["control_name"]),
            )
        )
    if not rows:
        raise RcmFormatError("Control matrix has no control rows.")
    return rows


def import_controls(session: Session, rows: list[ControlRow]) -> int:
    """Upserts controls by code inside the caller's transaction. Returns the number written."""
    for row in rows:
        session.execute(
            text("""
                INSERT INTO controls (
                    id, code, name, description, owner, frequency, control_type, automation,
                    source_document, source_section, evidence_expected, rbi_reference, topic
                ) VALUES (
                    :id, :code, :name, :description, :owner, :frequency, :control_type,
                    :automation, :source_document, :source_section, :evidence_expected,
                    :rbi_reference, :topic
                )
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    owner = EXCLUDED.owner,
                    frequency = EXCLUDED.frequency,
                    control_type = EXCLUDED.control_type,
                    automation = EXCLUDED.automation,
                    source_document = EXCLUDED.source_document,
                    source_section = EXCLUDED.source_section,
                    evidence_expected = EXCLUDED.evidence_expected,
                    rbi_reference = EXCLUDED.rbi_reference,
                    topic = EXCLUDED.topic
            """),
            {
                "id": row.code.lower(),
                "code": row.code,
                "name": row.name,
                "description": row.description,
                "owner": row.owner,
                "frequency": row.frequency,
                "control_type": row.control_type,
                "automation": row.automation,
                "source_document": row.source_document,
                "source_section": row.source_section,
                "evidence_expected": row.evidence_expected,
                "rbi_reference": row.rbi_reference,
                "topic": row.topic,
            },
        )
    return len(rows)
