#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for graph pack schemas v1 and their realistic examples."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPH_SCHEMAS_DIR = REPO_ROOT / "schemas" / "graph"
GRAPH_EXAMPLES_DIR = REPO_ROOT / "examples" / "graph"


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for path in sorted(REPO_ROOT.glob("schemas/**/*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(doc)
        schema_id = doc.get("$id")
        assert schema_id, f"Schema {path} missing $id"
        result[schema_id] = doc
    return result


@pytest.fixture(scope="module")
def registry(schemas: dict[str, dict]) -> Registry:
    return Registry().with_resources(
        [
            (uri, Resource.from_contents(doc, default_specification=DRAFT202012))
            for uri, doc in schemas.items()
        ]
    )


def validator_for(schema_name: str, schemas: dict[str, dict], registry: Registry) -> Draft202012Validator:
    uri = f"https://schemas.mixu.app/graph/v1/{schema_name}.schema.json"
    assert uri in schemas, f"Schema {uri} not found in loaded schemas"
    return Draft202012Validator(schemas[uri], registry=registry)


def test_graph_schemas_id_and_structure(schemas: dict[str, dict]) -> None:
    expected_schemas = [
        "assertion",
        "assertion-transition",
        "entity",
        "entity-name",
        "event",
        "evidence-anchor",
        "graph-pack-manifest",
        "identity-link",
        "reveal-anchor",
        "user-overlay",
    ]
    for name in expected_schemas:
        uri = f"https://schemas.mixu.app/graph/v1/{name}.schema.json"
        assert uri in schemas
        doc = schemas[uri]
        assert doc["additionalProperties"] is False
        assert "$id" in doc
        assert doc["$id"] == uri


def test_graph_examples_validation(schemas: dict[str, dict], registry: Registry) -> None:
    example_files = sorted(GRAPH_EXAMPLES_DIR.glob("*.json"))
    assert len(example_files) == 9, "Expected 9 graph schema examples in examples/graph"
    for example_path in example_files:
        payload = json.loads(example_path.read_text(encoding="utf-8"))
        schema_name = example_path.stem
        val = validator_for(schema_name, schemas, registry)
        errors = list(val.iter_errors(payload))
        assert not errors, f"Validation failed for {example_path}: {errors}"


def test_entity_schema_mutations(schemas: dict[str, dict], registry: Registry) -> None:
    val = validator_for("entity", schemas, registry)
    valid_payload = json.loads((GRAPH_EXAMPLES_DIR / "entity.json").read_text(encoding="utf-8"))

    # Missing required entity_id
    bad = copy.deepcopy(valid_payload)
    del bad["entity_id"]
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Invalid enum entity_type
    bad = copy.deepcopy(valid_payload)
    bad["entity_type"] = "INVALID_TYPE"
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Negative first_reveal
    bad = copy.deepcopy(valid_payload)
    bad["first_reveal"] = -1
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Injected unknown field
    bad = copy.deepcopy(valid_payload)
    bad["unexpected_field"] = "value"
    with pytest.raises(ValidationError):
        val.validate(bad)


def test_assertion_schema_mutations(schemas: dict[str, dict], registry: Registry) -> None:
    val = validator_for("assertion", schemas, registry)
    valid_payload = json.loads((GRAPH_EXAMPLES_DIR / "assertion.json").read_text(encoding="utf-8"))

    # Missing epistemic_status
    bad = copy.deepcopy(valid_payload)
    del bad["epistemic_status"]
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Invalid epistemic_status
    bad = copy.deepcopy(valid_payload)
    bad["epistemic_status"] = "TRUE"
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Missing attribution
    bad = copy.deepcopy(valid_payload)
    del bad["attribution"]
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Invalid attribution kind
    bad = copy.deepcopy(valid_payload)
    bad["attribution"]["kind"] = "RUMOR"
    with pytest.raises(ValidationError):
        val.validate(bad)


def test_assertion_transition_schema_mutations(schemas: dict[str, dict], registry: Registry) -> None:
    val = validator_for("assertion-transition", schemas, registry)
    valid_payload = json.loads((GRAPH_EXAMPLES_DIR / "assertion-transition.json").read_text(encoding="utf-8"))

    bad = copy.deepcopy(valid_payload)
    del bad["status"]
    with pytest.raises(ValidationError):
        val.validate(bad)

    bad = copy.deepcopy(valid_payload)
    bad["reveal_ordinal"] = -5
    with pytest.raises(ValidationError):
        val.validate(bad)


def test_reveal_anchor_schema_mutations(schemas: dict[str, dict], registry: Registry) -> None:
    val = validator_for("reveal-anchor", schemas, registry)
    valid_payload = json.loads((GRAPH_EXAMPLES_DIR / "reveal-anchor.json").read_text(encoding="utf-8"))

    # Invalid progression > 1.0
    bad = copy.deepcopy(valid_payload)
    bad["locator"]["progression"] = 1.5
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Missing reveal_kind
    bad = copy.deepcopy(valid_payload)
    del bad["reveal_kind"]
    with pytest.raises(ValidationError):
        val.validate(bad)

    # Invalid hex text_hash
    bad = copy.deepcopy(valid_payload)
    bad["text_hash"] = "not_a_sha256_hash"
    with pytest.raises(ValidationError):
        val.validate(bad)


def test_identity_link_schema_mutations(schemas: dict[str, dict], registry: Registry) -> None:
    val = validator_for("identity-link", schemas, registry)
    valid_payload = json.loads((GRAPH_EXAMPLES_DIR / "identity-link.json").read_text(encoding="utf-8"))

    # Exactly 2 entity_ids required
    bad = copy.deepcopy(valid_payload)
    bad["entity_ids"] = ["e_ishida"]
    with pytest.raises(ValidationError):
        val.validate(bad)

    bad = copy.deepcopy(valid_payload)
    bad["entity_ids"] = ["e_ishida", "e_grey", "e_third"]
    with pytest.raises(ValidationError):
        val.validate(bad)
