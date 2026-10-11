from app.services.pipeline_runner import _rename


def test_model_codes_become_app_codes() -> None:
    renames = {"OB-007": "OB-15", "GAP-001": "G-12"}

    renamed = _rename("Close GAP-001 for OB-007; leave OB-0071 alone.", renames)

    assert renamed == "Close G-12 for OB-15; leave OB-0071 alone."
