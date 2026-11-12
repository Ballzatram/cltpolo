import pytest

from starter_package import normalize_label


@pytest.mark.parametrize(
    ("value", "expected"),
    [("  hello   world  ", "hello world"), ("hello", "hello"), ("a\nb", "a b")],
)
def test_normalizes_labels(value: str, expected: str) -> None:
    assert normalize_label(value) == expected


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_rejects_empty_labels(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        normalize_label(value)
