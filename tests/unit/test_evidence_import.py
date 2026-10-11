import pytest

from app.services.evidence_import import EvidenceFormatError, evidence_code, parse_table


def test_code_comes_from_file_name_or_fallback() -> None:
    assert evidence_code("EVD-07_NSM_Test_Certificates_Log.csv", "doc-1") == "EVD-07"
    assert evidence_code("inventory.csv", "doc-1a2b") == "DOC-1A2B"


def test_table_keeps_header_and_rows_as_text() -> None:
    columns, rows = parse_table(b"cycle,machines\nOct 2025,42\n\nApr 2026,42\n")

    assert columns == ["cycle", "machines"]
    assert rows == [["Oct 2025", "42"], ["Apr 2026", "42"]]


def test_header_only_table_is_rejected() -> None:
    with pytest.raises(EvidenceFormatError):
        parse_table(b"cycle,machines\n")
