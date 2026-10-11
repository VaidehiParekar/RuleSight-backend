from pathlib import Path

import pytest

from app.services.rcm_import import RcmFormatError, parse_rcm

RCM = Path("demo_data/2_bank_nova_trust/rcm/RCM_Nova_Trust_Risk_Control_Matrix.csv")


def test_demo_matrix_parses_every_control() -> None:
    rows = parse_rcm(RCM.read_bytes())

    codes = [r.code for r in rows]
    assert len(rows) == 11
    assert "CTL-19" in codes
    ctl_02 = next(r for r in rows if r.code == "CTL-02")
    assert ctl_02.frequency == "Annual"
    assert ctl_02.topic == "KYC"


def test_missing_required_columns_are_rejected() -> None:
    with pytest.raises(RcmFormatError, match="control_name"):
        parse_rcm(b"control_id,description\nCTL-01,Something\n")


def test_topic_falls_back_to_name_without_reference() -> None:
    rows = parse_rcm(b"control_id,control_name,description\nctl-9,Cash count,Daily count\n")

    assert rows[0].code == "CTL-9"
    assert rows[0].topic == "Cash count"
    assert rows[0].owner == "Not specified"
