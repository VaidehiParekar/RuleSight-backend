from app.db.queries import _change_from_row, _diff_phrases


def test_diff_phrases_are_exact_substrings() -> None:
    old = "Banks may  continue using existing machines."
    new = "Banks shall phase out existing machines by 30 June 2027."

    removed, added = _diff_phrases(old, new)

    assert removed and added
    assert all(phrase in old for phrase in removed)
    assert all(phrase in new for phrase in added)


def test_change_row_maps_to_ui_contract() -> None:
    row = {
        "id": "chg-01",
        "old_document_id": "doc-v1",
        "new_document_id": "doc-v2",
        "clause_ref": "para 8.2",
        "change_type": "consolidated",
        "title": "Carried over",
        "old_text": None,
        "new_text": None,
        "summary": "No text change.",
        "significance": "low",
        "carried_over": '["N-01"]',
        "impact": '{"controls": ["CTL-20"]}',
    }

    change = _change_from_row(row, old_doc=None, new_doc=None).model_dump()

    assert change["code"] == "CHG-01"
    assert change["before"] is None and change["after"] is None
    assert change["removed_phrases"] == [] and change["added_phrases"] == []
    assert change["carried_over"] == ["N-01"]
    assert change["impact"] == {"obligations": [], "controls": ["CTL-20"], "gaps": []}
    assert "clause_ref" not in change
