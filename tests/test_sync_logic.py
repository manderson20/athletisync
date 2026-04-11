from app.schemas import MappingFormData


def test_mapping_form_defaults() -> None:
    payload = MappingFormData(school_year_id=1, school_id=2)
    assert payload.enabled is True
    assert payload.sync_behavior == "standard"
