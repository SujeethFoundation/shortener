import pytest
from link_service import as_bool, public_link, validate_code, validate_url


def test_alias_rules_and_immutability_identity():
    assert validate_code("career-circle_2026") == "career-circle_2026"
    with pytest.raises(ValueError): validate_code("two words")
    entity = {"RowKey": "stay", "DestinationUrl": "https://example.org", "ClickCount": 2, "HistoricalClickCount": 7}
    assert public_link(entity, "https://go.sujeeth.org")["code"] == "stay"


def test_only_http_destinations_are_accepted():
    assert validate_url("https://example.org/path") == "https://example.org/path"
    with pytest.raises(ValueError): validate_url("javascript:alert(1)")


def test_csv_boolean_values_do_not_turn_false_into_true():
    assert as_bool("false") is False
    assert as_bool("true") is True
