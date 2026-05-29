import pytest
from app.core.json_utils import extract_json


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_markdown_fenced_json():
    raw = '```json\n{\n  "tags": ["rust"],\n  "detailed_description": "rusty roof"\n}\n```'
    out = extract_json(raw)
    assert out["tags"] == ["rust"]


def test_json_with_surrounding_prose():
    raw = 'Here is the result:\n{"x": 2}\nHope that helps!'
    assert extract_json(raw) == {"x": 2}


def test_empty_raises():
    with pytest.raises(ValueError):
        extract_json("")
    with pytest.raises(ValueError):
        extract_json(None)
