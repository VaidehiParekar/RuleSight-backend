from app.services.regulation_text import (
    Paragraph,
    extract_text,
    select_paragraphs,
    split_paragraphs,
)

DIRECTION = """Master Direction

Contents
1. Short Title ........................................ 3
2. Applicability ...................................... 4

2. Accordingly, in exercise of the powers conferred, the Reserve Bank issues these directions.

1. Short Title and Commencement.
These Directions shall be called the Know Your Customer Directions.
2. Applicability
The provisions of these Directions shall apply to every entity regulated by the Reserve Bank.
3. Definitions
In these Directions the terms have the meaning given here.
4. 112Updation
Periodic updation shall be carried out at least once in every two years for high-risk customers.
"""

CIRCULAR = """RBI/2024-2025/86
Madam / Dear Sir,
Reference is invited to our circular on note sorting machines.
2. The standards are published in the Gazette.
3. Effective May 01, 2025, banks should deploy only certified machines.
Yours faithfully
"""


def test_body_paragraphs_skip_contents_and_preamble() -> None:
    paragraphs = split_paragraphs(DIRECTION)

    assert [p.ref for p in paragraphs] == ["1", "2", "3", "4"]
    assert paragraphs[1].text.startswith("2. Applicability")
    assert "Accordingly" not in paragraphs[1].text


def test_circular_with_unnumbered_opening_starts_at_one() -> None:
    paragraphs = split_paragraphs(CIRCULAR)

    assert [p.ref for p in paragraphs] == ["1", "2", "3"]
    assert "Reference is invited" in paragraphs[0].text


def test_selection_by_number_includes_lettered_paragraphs() -> None:
    paragraphs = [Paragraph("46", "a"), Paragraph("46A", "b"), Paragraph("47", "c")]

    chosen = select_paragraphs(paragraphs, only={"46"}, limit=10)

    assert [p.ref for p in chosen] == ["46", "46A"]


def test_default_selection_keeps_duties_and_respects_limit() -> None:
    paragraphs = split_paragraphs(DIRECTION)

    assert [p.ref for p in select_paragraphs(paragraphs, only=None, limit=10)] == ["1", "2", "4"]
    assert len(select_paragraphs(paragraphs, only=None, limit=1)) == 1


def test_text_files_decode_and_binary_files_are_empty() -> None:
    assert extract_text(b"Banks shall comply.", "rule.txt") == "Banks shall comply."
    assert extract_text(b"\x00\x01\x02binary", "image.bin") == ""
