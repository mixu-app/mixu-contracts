#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for the shared reading locator schema and examples."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCATOR_SCHEMA_PATH = REPO_ROOT / "schemas" / "common" / "locator.schema.json"
EXAMPLES_DIR = REPO_ROOT / "examples" / "locators"


@pytest.fixture
def locator_schema() -> dict:
    return json.loads(LOCATOR_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def validator(locator_schema: dict) -> Draft202012Validator:
    Draft202012Validator.check_schema(locator_schema)
    return Draft202012Validator(locator_schema)


@pytest.fixture
def base_valid_locator() -> dict:
    return {
        "doc_id": "urn:mixu:doc:study-in-scarlet",
        "edition_fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "spine_index": 0,
        "spine_item_id": "chapter01",
        "spine_href": "text/chapter01.xhtml",
        "char_offset": 0,
        "progression": 0.0,
        "total_progression": 0.0,
        "cfi": "/6/4[chapter01]!/4/2/1:0",
    }


def test_schema_metadata(locator_schema: dict) -> None:
    assert (
        locator_schema["$id"] == "https://schemas.mixu.app/common/locator.schema.json"
    )
    assert locator_schema["title"] == "Locator"
    assert locator_schema["additionalProperties"] is False
    # Ensure normative rule against page numbers is explicitly documented in description
    description = locator_schema["description"].lower()
    assert "page number" in description
    assert "never carries a rendered page number" in description


def test_all_example_files_pass_validation(validator: Draft202012Validator) -> None:
    example_paths = sorted(EXAMPLES_DIR.glob("*.json"))
    assert len(example_paths) >= 3, "Expected at least 3 locator examples"
    expected_stems = {"locator-start", "locator-mid-chapter", "locator-chapter-end"}
    found_stems = {p.stem for p in example_paths}
    assert expected_stems.issubset(found_stems)

    for path in example_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(payload))
        assert not errors, (
            f"{path.name} failed schema validation: {[e.message for e in errors]}"
        )


@pytest.mark.parametrize(
    "field,invalid_value",
    [
        ("char_offset", -1),
        ("char_offset", -100),
        ("spine_index", -1),
        ("progression", -0.001),
        ("progression", 1.001),
        ("progression", 2.0),
        ("total_progression", -0.01),
        ("total_progression", 1.01),
        ("doc_id", ""),
        ("edition_fingerprint", ""),
        ("spine_href", ""),
        ("spine_item_id", ""),
        ("cfi", ""),
    ],
)
def test_invalid_field_values_rejected(
    validator: Draft202012Validator,
    base_valid_locator: dict,
    field: str,
    invalid_value: object,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    payload[field] = invalid_value
    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize(
    "missing_field",
    [
        "doc_id",
        "edition_fingerprint",
        "progression",
    ],
)
def test_missing_required_top_level_fields_rejected(
    validator: Draft202012Validator,
    base_valid_locator: dict,
    missing_field: str,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    del payload[missing_field]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(payload)
    assert missing_field in exc_info.value.message


def test_missing_all_spine_identifiers_rejected(
    validator: Draft202012Validator,
    base_valid_locator: dict,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    del payload["spine_index"]
    del payload["spine_item_id"]
    del payload["spine_href"]
    with pytest.raises(ValidationError):
        validator.validate(payload)


@pytest.mark.parametrize("spine_prop", ["spine_index", "spine_href", "spine_item_id"])
def test_spine_identification_alternatives_accepted(
    validator: Draft202012Validator,
    base_valid_locator: dict,
    spine_prop: str,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    # Remove all spine props, then add back only one
    payload.pop("spine_index", None)
    payload.pop("spine_href", None)
    payload.pop("spine_item_id", None)

    if spine_prop == "spine_index":
        payload["spine_index"] = 2
    elif spine_prop == "spine_href":
        payload["spine_href"] = "text/chapter03.xhtml"
    elif spine_prop == "spine_item_id":
        payload["spine_item_id"] = "chap03"

    validator.validate(payload)


@pytest.mark.parametrize(
    "page_field",
    [
        "page_number",
        "page",
        "page_index",
        "rendered_page",
        "page_count",
    ],
)
def test_page_number_fields_strictly_forbidden(
    validator: Draft202012Validator,
    base_valid_locator: dict,
    page_field: str,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    payload[page_field] = 42
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(payload)
    assert exc_info.value.validator == "additionalProperties"
    assert page_field in exc_info.value.message


def test_arbitrary_extra_properties_rejected(
    validator: Draft202012Validator,
    base_valid_locator: dict,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    payload["viewport_width"] = 1080
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(payload)
    assert exc_info.value.validator == "additionalProperties"
    assert "viewport_width" in exc_info.value.message


def test_char_range_validation(
    validator: Draft202012Validator,
    base_valid_locator: dict,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    payload["char_range"] = {"start": 100, "end": 150}
    validator.validate(payload)

    # Missing end
    payload_bad1 = copy.deepcopy(base_valid_locator)
    payload_bad1["char_range"] = {"start": 100}
    with pytest.raises(ValidationError):
        validator.validate(payload_bad1)

    # Negative offset in range
    payload_bad2 = copy.deepcopy(base_valid_locator)
    payload_bad2["char_range"] = {"start": -1, "end": 10}
    with pytest.raises(ValidationError):
        validator.validate(payload_bad2)

    # Unexpected property in range
    payload_bad3 = copy.deepcopy(base_valid_locator)
    payload_bad3["char_range"] = {"start": 0, "end": 10, "page": 1}
    with pytest.raises(ValidationError):
        validator.validate(payload_bad3)


def test_text_quote_validation(
    validator: Draft202012Validator,
    base_valid_locator: dict,
) -> None:
    payload = copy.deepcopy(base_valid_locator)
    payload["text_quote"] = {
        "exact": "It was the best of times",
        "prefix": "In London, ",
        "suffix": ", it was the worst of times",
    }
    validator.validate(payload)

    # Missing exact
    payload_bad1 = copy.deepcopy(base_valid_locator)
    payload_bad1["text_quote"] = {"prefix": "before "}
    with pytest.raises(ValidationError):
        validator.validate(payload_bad1)

    # Empty exact
    payload_bad2 = copy.deepcopy(base_valid_locator)
    payload_bad2["text_quote"] = {"exact": ""}
    with pytest.raises(ValidationError):
        validator.validate(payload_bad2)

    # Unexpected property in text_quote
    payload_bad3 = copy.deepcopy(base_valid_locator)
    payload_bad3["text_quote"] = {"exact": "Hello", "page_number": 5}
    with pytest.raises(ValidationError):
        validator.validate(payload_bad3)


def test_edition_mismatch_scenario(
    validator: Draft202012Validator,
    base_valid_locator: dict,
) -> None:
    """Verifies that an edition mismatch is detectable between a publication and a locator."""
    book_edition_fingerprint = (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    different_edition_fingerprint = (
        "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"
    )

    def verify_locator_edition(locator: dict, expected_edition: str) -> bool:
        validator.validate(locator)
        return locator["edition_fingerprint"] == expected_edition

    matching_locator = copy.deepcopy(base_valid_locator)
    matching_locator["edition_fingerprint"] = book_edition_fingerprint
    assert verify_locator_edition(matching_locator, book_edition_fingerprint) is True

    mismatched_locator = copy.deepcopy(base_valid_locator)
    mismatched_locator["edition_fingerprint"] = different_edition_fingerprint
    assert verify_locator_edition(mismatched_locator, book_edition_fingerprint) is False
