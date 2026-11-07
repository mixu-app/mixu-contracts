#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for language profile and edition fingerprint schemas and examples."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent
LANGUAGE_PROFILE_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "common" / "language-profile.schema.json"
)
EDITION_FINGERPRINT_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "common" / "edition-fingerprint.schema.json"
)
LANGUAGE_PROFILES_DIR = REPO_ROOT / "examples" / "language-profiles"
EDITION_FINGERPRINTS_DIR = REPO_ROOT / "examples" / "edition-fingerprints"


@pytest.fixture
def language_profile_schema() -> dict:
    return json.loads(LANGUAGE_PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def edition_fingerprint_schema() -> dict:
    return json.loads(EDITION_FINGERPRINT_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def profile_validator(language_profile_schema: dict) -> Draft202012Validator:
    Draft202012Validator.check_schema(language_profile_schema)
    return Draft202012Validator(language_profile_schema)


@pytest.fixture
def fingerprint_validator(
    edition_fingerprint_schema: dict,
) -> Draft202012Validator:
    Draft202012Validator.check_schema(edition_fingerprint_schema)
    return Draft202012Validator(edition_fingerprint_schema)


@pytest.fixture
def base_valid_profile() -> dict:
    return {
        "id": "zh-Hans",
        "name": "Simplified Chinese Profile",
        "version": "1.0.0",
        "script_family": "han",
        "chapter_rules": [
            {
                "id": "zh-standard-chapter",
                "pattern": r"^\s*第[0-9一二三四五六七八九十百千万]+[章回节卷部集篇]\s*.*$",
                "capture_group": 0,
            }
        ],
        "quote_pairs": [["“", "”"], ["「", "」"]],
        "honorifics": ["先生", "女士"],
        "alias_markers": ["又名", "原名"],
        "ruby_policy": "strip",
    }


@pytest.fixture
def base_valid_fingerprint() -> dict:
    return {
        "doc_id": "urn:mixu:doc:study-in-scarlet",
        "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "language": "zh-Hans",
        "profile_version": "1.0.0",
        "normalization_version": "1.0.0",
        "format": "epub",
        "spine_order": [
            "text/chapter01.xhtml",
            "text/chapter02.xhtml",
        ],
    }


def test_language_profile_schema_metadata(
    language_profile_schema: dict,
) -> None:
    assert (
        language_profile_schema["$id"]
        == "https://schemas.mixu.app/common/language-profile.schema.json"
    )
    assert language_profile_schema["title"] == "LanguageProfile"
    assert language_profile_schema["additionalProperties"] is False
    required = set(language_profile_schema["required"])
    expected_required = {
        "id",
        "version",
        "script_family",
        "chapter_rules",
        "quote_pairs",
        "honorifics",
        "alias_markers",
        "ruby_policy",
    }
    assert expected_required.issubset(required)


def test_edition_fingerprint_schema_metadata(
    edition_fingerprint_schema: dict,
) -> None:
    assert (
        edition_fingerprint_schema["$id"]
        == "https://schemas.mixu.app/common/edition-fingerprint.schema.json"
    )
    assert edition_fingerprint_schema["title"] == "EditionFingerprint"
    assert edition_fingerprint_schema["additionalProperties"] is False
    required = set(edition_fingerprint_schema["required"])
    expected_required = {
        "content_hash",
        "language",
        "profile_version",
        "normalization_version",
        "spine_order",
    }
    assert expected_required == required
    description = edition_fingerprint_schema["description"].lower()
    assert "normative rule" in description
    assert "missing any version field" in description


def test_all_language_profile_examples_pass_validation(
    profile_validator: Draft202012Validator,
) -> None:
    example_files = sorted(LANGUAGE_PROFILES_DIR.glob("*.json"))
    assert len(example_files) >= 4, (
        "Expected at least 4 language profile examples"
    )
    expected_stems = {"zh-Hans", "en", "ja", "generic"}
    found_stems = {p.stem for p in example_files}
    assert expected_stems.issubset(found_stems)

    for path in example_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = list(profile_validator.iter_errors(payload))
        assert not errors, (
            f"{path.name} failed schema validation: {[e.message for e in errors]}"
        )


def test_all_edition_fingerprint_examples_pass_validation(
    fingerprint_validator: Draft202012Validator,
) -> None:
    example_files = sorted(EDITION_FINGERPRINTS_DIR.glob("*.json"))
    assert len(example_files) >= 4, (
        "Expected at least 4 edition fingerprint examples"
    )
    for path in example_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = list(fingerprint_validator.iter_errors(payload))
        assert not errors, (
            f"{path.name} failed schema validation: {[e.message for e in errors]}"
        )


@pytest.mark.parametrize(
    "missing_field",
    [
        "profile_version",
        "normalization_version",
        "content_hash",
        "language",
        "spine_order",
    ],
)
def test_fingerprint_missing_required_fields_rejected(
    fingerprint_validator: Draft202012Validator,
    base_valid_fingerprint: dict,
    missing_field: str,
) -> None:
    payload = copy.deepcopy(base_valid_fingerprint)
    del payload[missing_field]
    with pytest.raises(ValidationError) as excinfo:
        fingerprint_validator.validate(payload)
    assert missing_field in excinfo.value.message


@pytest.mark.parametrize(
    "field,invalid_val",
    [
        ("content_hash", ""),
        ("content_hash", "12345"),
        ("content_hash", "not-a-hex-string-of-64-characters-length-at-all!!"),
        (
            "content_hash",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85",
        ),  # 63 chars
        (
            "content_hash",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8555",
        ),  # 65 chars
        ("language", ""),
        ("profile_version", ""),
        ("profile_version", "v1.0.0"),
        ("profile_version", "1.0"),
        ("profile_version", "invalid-semver"),
        ("normalization_version", ""),
        ("normalization_version", "1"),
        ("normalization_version", "beta-1"),
        ("spine_order", [""]),
        ("spine_order", "not-a-list"),
    ],
)
def test_fingerprint_invalid_values_rejected(
    fingerprint_validator: Draft202012Validator,
    base_valid_fingerprint: dict,
    field: str,
    invalid_val: object,
) -> None:
    payload = copy.deepcopy(base_valid_fingerprint)
    payload[field] = invalid_val
    with pytest.raises(ValidationError):
        fingerprint_validator.validate(payload)


def test_fingerprint_additional_properties_rejected(
    fingerprint_validator: Draft202012Validator,
    base_valid_fingerprint: dict,
) -> None:
    payload = copy.deepcopy(base_valid_fingerprint)
    payload["unknown_extraneous_property"] = True
    with pytest.raises(ValidationError):
        fingerprint_validator.validate(payload)


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "version",
        "script_family",
        "chapter_rules",
        "quote_pairs",
        "honorifics",
        "alias_markers",
        "ruby_policy",
    ],
)
def test_language_profile_missing_required_fields_rejected(
    profile_validator: Draft202012Validator,
    base_valid_profile: dict,
    missing_field: str,
) -> None:
    payload = copy.deepcopy(base_valid_profile)
    del payload[missing_field]
    with pytest.raises(ValidationError) as excinfo:
        profile_validator.validate(payload)
    assert missing_field in excinfo.value.message


@pytest.mark.parametrize(
    "invalid_quote_pair",
    [
        ["“"],  # 1 element
        ["“", "”", "„"],  # 3 elements
        [],  # 0 elements
        ["", "”"],  # empty string
        [123, 456],  # non-string
        "not-a-pair",  # string instead of array
    ],
)
def test_language_profile_invalid_quote_pairs_rejected(
    profile_validator: Draft202012Validator,
    base_valid_profile: dict,
    invalid_quote_pair: object,
) -> None:
    payload = copy.deepcopy(base_valid_profile)
    payload["quote_pairs"] = [invalid_quote_pair]
    with pytest.raises(ValidationError):
        profile_validator.validate(payload)


@pytest.mark.parametrize(
    "invalid_chapter_rule,expected_err",
    [
        (
            {"pattern": r"^Chapter \d+$", "capture_group": 0},
            "'id' is a required property",
        ),
        ({"id": "rule-1", "capture_group": 0}, "'pattern' is a required property"),
        (
            {"id": "rule-1", "pattern": r"^Chapter \d+$"},
            "'capture_group' is a required property",
        ),
        (
            {
                "id": "rule-1",
                "pattern": r"^Chapter \d+$",
                "capture_group": -1,
            },
            "is less than the minimum",
        ),
        (
            {
                "id": "",
                "pattern": r"^Chapter \d+$",
                "capture_group": 0,
            },
            "should be non-empty",
        ),
    ],
)
def test_language_profile_invalid_chapter_rules_rejected(
    profile_validator: Draft202012Validator,
    base_valid_profile: dict,
    invalid_chapter_rule: dict,
    expected_err: str,
) -> None:
    payload = copy.deepcopy(base_valid_profile)
    payload["chapter_rules"] = [invalid_chapter_rule]
    with pytest.raises(ValidationError) as excinfo:
        profile_validator.validate(payload)
    assert (
        expected_err in excinfo.value.message
        or "is not valid" in excinfo.value.message
        or "does not match" in excinfo.value.message
    )


def test_language_profile_ruby_policy_variants(
    profile_validator: Draft202012Validator,
    base_valid_profile: dict,
) -> None:
    # Valid string policies
    for strategy in ("strip", "parenthesize", "keep_base"):
        payload = copy.deepcopy(base_valid_profile)
        payload["ruby_policy"] = strategy
        profile_validator.validate(payload)

    # Valid object policy
    payload = copy.deepcopy(base_valid_profile)
    payload["ruby_policy"] = {
        "strategy": "parenthesize",
        "parentheses": ["(", ")"],
    }
    profile_validator.validate(payload)

    # Invalid string policy
    payload = copy.deepcopy(base_valid_profile)
    payload["ruby_policy"] = "unsupported_strategy"
    with pytest.raises(ValidationError):
        profile_validator.validate(payload)

    # Invalid object policy (missing strategy)
    payload = copy.deepcopy(base_valid_profile)
    payload["ruby_policy"] = {"parentheses": ["(", ")"]}
    with pytest.raises(ValidationError):
        profile_validator.validate(payload)


def test_language_profile_additional_properties_rejected(
    profile_validator: Draft202012Validator,
    base_valid_profile: dict,
) -> None:
    payload = copy.deepcopy(base_valid_profile)
    payload["custom_unsupported_key"] = "forbidden"
    with pytest.raises(ValidationError):
        profile_validator.validate(payload)


def test_validate_contracts_tool_exit_success() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "validate_contracts.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"validate_contracts.py failed: {result.stdout}\n{result.stderr}"
    )
    assert "contracts ok" in result.stdout


@pytest.mark.parametrize(
    "missing_field", ["normalization_version", "profile_version"]
)
def test_validate_contracts_tool_rejects_fingerprint_missing_version(
    tmp_path: Path, missing_field: str
) -> None:
    test_tree = tmp_path / "contracts"
    shutil.copytree(REPO_ROOT / "schemas", test_tree / "schemas")
    shutil.copytree(REPO_ROOT / "api", test_tree / "api")
    shutil.copytree(REPO_ROOT / "config", test_tree / "config")
    shutil.copytree(REPO_ROOT / "examples", test_tree / "examples")
    shutil.copytree(REPO_ROOT / "tools", test_tree / "tools")

    fp_path = (
        test_tree
        / "examples"
        / "edition-fingerprints"
        / "study-in-scarlet-zh-hans.json"
    )
    data = json.loads(fp_path.read_text(encoding="utf-8"))
    del data[missing_field]
    fp_path.write_text(json.dumps(data), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(test_tree / "tools" / "validate_contracts.py")],
        capture_output=True,
        text=True,
        cwd=str(test_tree),
    )
    assert result.returncode != 0
    assert (
        missing_field in result.stdout
        or missing_field in result.stderr
        or "required property" in result.stdout
    )


def test_validate_contracts_tool_rejects_invalid_quote_pairs(
    tmp_path: Path,
) -> None:
    test_tree = tmp_path / "contracts"
    shutil.copytree(REPO_ROOT / "schemas", test_tree / "schemas")
    shutil.copytree(REPO_ROOT / "api", test_tree / "api")
    shutil.copytree(REPO_ROOT / "config", test_tree / "config")
    shutil.copytree(REPO_ROOT / "examples", test_tree / "examples")
    shutil.copytree(REPO_ROOT / "tools", test_tree / "tools")

    profile_path = (
        test_tree / "examples" / "language-profiles" / "zh-Hans.json"
    )
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    data["quote_pairs"] = [["“"]]  # Only 1 delimiter instead of pair
    profile_path.write_text(json.dumps(data), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(test_tree / "tools" / "validate_contracts.py")],
        capture_output=True,
        text=True,
        cwd=str(test_tree),
    )
    assert result.returncode != 0
    assert (
        "quote_pairs" in result.stdout
        or "quote_pairs" in result.stderr
        or "too short" in result.stdout
    )


def test_validate_contracts_tool_rejects_missing_chapter_rule_id(
    tmp_path: Path,
) -> None:
    test_tree = tmp_path / "contracts"
    shutil.copytree(REPO_ROOT / "schemas", test_tree / "schemas")
    shutil.copytree(REPO_ROOT / "api", test_tree / "api")
    shutil.copytree(REPO_ROOT / "config", test_tree / "config")
    shutil.copytree(REPO_ROOT / "examples", test_tree / "examples")
    shutil.copytree(REPO_ROOT / "tools", test_tree / "tools")

    profile_path = (
        test_tree / "examples" / "language-profiles" / "zh-Hans.json"
    )
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    del data["chapter_rules"][0]["id"]
    profile_path.write_text(json.dumps(data), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(test_tree / "tools" / "validate_contracts.py")],
        capture_output=True,
        text=True,
        cwd=str(test_tree),
    )
    assert result.returncode != 0
    assert (
        "'id' is a required property" in result.stdout
        or "required property" in result.stdout
    )

