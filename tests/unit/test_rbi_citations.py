"""Checks that quotes used in the demo answer key are real RBI text.

The critic is only useful if real regulation text passes it. These tests read the RBI KYC Master
Direction saved in demo_data and confirm the quotes the team relies on are exact copies of it.
"""

from pathlib import Path

import pytest

from app.workflows.critic import quote_in

RBI_TEXT_PATH = (
    Path(__file__).resolve().parents[2]
    / "demo_data"
    / "1_regulations_rbi"
    / "RBI_KYC_MD_2016_updated_2025-08-14.txt"
)


@pytest.fixture(scope="module")
def rbi_text() -> str:
    if not RBI_TEXT_PATH.is_file():
        pytest.skip("RBI KYC text is not present in demo_data")
    return RBI_TEXT_PATH.read_text(encoding="utf-8")


REAL_QUOTES = [
    "In no case, the Principal Officer shall be nominated as the "
    "'Designated Director'.",  # para 6(d)
    "at least once in six months",  # para 37(a)
    "more than 10 percent of the shares or capital or profits of the company",  # para 3 definition
    "stored in a system / systems located in India",  # para 18(c)(i)
    "The video recordings should contain the live GPS co-ordinates "
    "(geo-tagging) of the customer",  # 18(a)(iv)
    "face liveness / spoof detection as well as face matching technology",  # para 18(a)(v)
    "On-going employee training programme shall be put in place",  # para 70
    "at least once in every two years for high-risk customers",  # para 38
    "for at least five years from the date of transaction",  # para 46(a)
]


@pytest.mark.parametrize("quote", REAL_QUOTES)
def test_answer_key_quotes_are_exact_rbi_text(rbi_text: str, quote: str) -> None:
    assert quote_in(quote, rbi_text), quote


def test_paraphrased_rbi_quote_is_rejected(rbi_text: str) -> None:
    assert not quote_in("banks must review the risk category every six months", rbi_text)
