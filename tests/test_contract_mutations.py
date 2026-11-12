# SPDX-License-Identifier: Apache-2.0
"""Mutation tests for the contract validator and JSON schemas (Issue #4).

These tests deliberately mutate valid contracts, schemas, and OpenAPI
specifications to prove that the validator and schema gates catch drift:
1. Every schema rejects payloads missing any required field (or set to null/invalid).
2. Schema and OpenAPI validators catch broken $ref pointers (internal, cross-schema,
   and unresolvable URIs).
3. OpenAPI validator catches duplicate operationIds and invalid configurations.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import validate_contracts as val_mod
from uri_config import load_config


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict]:
    """Load all JSON schemas in the repository and verify Draft 2020-12 compliance."""
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
    """Build a referencing registry containing all loaded schemas."""
    return Registry().with_resources(
        [
            (uri, Resource.from_contents(doc, default_specification=DRAFT202012))
            for uri, doc in schemas.items()
        ]
    )


@pytest.fixture
def isolated_contracts_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[Path, None, None]:
    """Provide an isolated tree of schemas, api, config, and examples with monkeypatched ROOT."""
    test_tree = tmp_path / "contracts"
    shutil.copytree(REPO_ROOT / "schemas", test_tree / "schemas")
    shutil.copytree(REPO_ROOT / "api", test_tree / "api")
    shutil.copytree(REPO_ROOT / "config", test_tree / "config")
    shutil.copytree(REPO_ROOT / "examples", test_tree / "examples")

    monkeypatch.setattr(val_mod, "ROOT", test_tree)
    yield test_tree


@pytest.fixture(scope="module")
def baseline_samples() -> dict[str, dict]:
    """Baseline valid payloads for all 14 schemas across the repository."""
    return {
        "https://schemas.mixu.app/api/v1/error.schema.json": {
            "code": "AUTH_REQUIRED",
            "message": "Authentication required",
            "request_id": "req-baseline-001",
        },
        "https://schemas.mixu.app/common/edition-fingerprint.schema.json": json.loads(
            (
                REPO_ROOT / "examples/edition-fingerprints/study-in-scarlet-en.json"
            ).read_text(encoding="utf-8")
        ),
        "https://schemas.mixu.app/common/language-profile.schema.json": json.loads(
            (REPO_ROOT / "examples/language-profiles/en.json").read_text(
                encoding="utf-8"
            )
        ),
        "https://schemas.mixu.app/common/locator.schema.json": json.loads(
            (REPO_ROOT / "examples/locators/locator-start.json").read_text(
                encoding="utf-8"
            )
        ),
        "https://schemas.mixu.app/graph/v1/assertion.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/assertion.json").read_text(encoding="utf-8")
        ),
        "https://schemas.mixu.app/graph/v1/assertion-transition.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/assertion-transition.json").read_text(
                encoding="utf-8"
            )
        ),
        "https://schemas.mixu.app/graph/v1/entity.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/entity.json").read_text(encoding="utf-8")
        ),
        "https://schemas.mixu.app/graph/v1/entity-name.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/entity-name.json").read_text(encoding="utf-8")
        ),
        "https://schemas.mixu.app/graph/v1/event.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/event.json").read_text(encoding="utf-8")
        ),
        "https://schemas.mixu.app/graph/v1/evidence-anchor.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/evidence-anchor.json").read_text(
                encoding="utf-8"
            )
        ),
        "https://schemas.mixu.app/graph/v1/graph-pack-manifest.schema.json": json.loads(
            (REPO_ROOT / "examples/graph-pack-manifest.json").read_text(
                encoding="utf-8"
            )
        ),
        "https://schemas.mixu.app/graph/v1/identity-link.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/identity-link.json").read_text(
                encoding="utf-8"
            )
        ),
        "https://schemas.mixu.app/graph/v1/reveal-anchor.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/reveal-anchor.json").read_text(
                encoding="utf-8"
            )
        ),
        "https://schemas.mixu.app/graph/v1/user-overlay.schema.json": json.loads(
            (REPO_ROOT / "examples/graph/user-overlay.json").read_text(encoding="utf-8")
        ),
    }


def _assert_mutations_rejected(
    schema: dict,
    base_payload: dict,
    registry: Registry,
    field: str,
) -> None:
    """Helper to verify deletion and None assignment for a required field fail validation."""
    validator = Draft202012Validator(schema, registry=registry)

    # 1. Field removal mutation
    mutated_del = copy.deepcopy(base_payload)
    del mutated_del[field]
    with pytest.raises(ValidationError) as exc_info:
        validator.validate(mutated_del)
    assert field in exc_info.value.message or "required" in exc_info.value.message

    # 2. Field set to None mutation
    mutated_none = copy.deepcopy(base_payload)
    mutated_none[field] = None
    with pytest.raises(ValidationError):
        validator.validate(mutated_none)


# ==============================================================================
# Required Fields Mutation Tests (One Per Schema)
# ==============================================================================


def test_rule_error_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: Error schema requires code, message, and request_id."""
    schema_id = "https://schemas.mixu.app/api/v1/error.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {"code", "message", "request_id"}
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_edition_fingerprint_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: EditionFingerprint requires content_hash, language, versions, and spine_order."""
    schema_id = "https://schemas.mixu.app/common/edition-fingerprint.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "content_hash",
        "language",
        "profile_version",
        "normalization_version",
        "spine_order",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_language_profile_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: LanguageProfile requires id, version, script_family, and typographics rules."""
    schema_id = "https://schemas.mixu.app/common/language-profile.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
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
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_locator_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: Locator requires doc_id, edition_fingerprint, and progression."""
    schema_id = "https://schemas.mixu.app/common/locator.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {"doc_id", "edition_fingerprint", "progression"}
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_assertion_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: Assertion requires assertion_id, subject_id, predicate, attribution, etc."""
    schema_id = "https://schemas.mixu.app/graph/v1/assertion.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "assertion_id",
        "subject_id",
        "predicate",
        "object_ref",
        "attribution",
        "first_reveal",
        "evidence_anchor_id",
        "epistemic_status",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_assertion_transition_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: AssertionTransition requires transition_id, assertion_id, reveal_ordinal, status."""
    schema_id = "https://schemas.mixu.app/graph/v1/assertion-transition.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "transition_id",
        "assertion_id",
        "reveal_ordinal",
        "status",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_entity_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: Entity requires entity_id, entity_type, and first_reveal."""
    schema_id = "https://schemas.mixu.app/graph/v1/entity.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {"entity_id", "entity_type", "first_reveal"}
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_entity_name_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: EntityName requires name_id, entity_id, display_text, first_reveal, and name_kind."""
    schema_id = "https://schemas.mixu.app/graph/v1/entity-name.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "name_id",
        "entity_id",
        "display_text",
        "first_reveal",
        "name_kind",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_event_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: Event requires event_id, event_type, and first_reveal."""
    schema_id = "https://schemas.mixu.app/graph/v1/event.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {"event_id", "event_type", "first_reveal"}
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_evidence_anchor_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: EvidenceAnchor requires evidence_id, reveal_ordinal, locator, excerpt_policy."""
    schema_id = "https://schemas.mixu.app/graph/v1/evidence-anchor.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "evidence_id",
        "reveal_ordinal",
        "locator",
        "excerpt_policy",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_graph_pack_manifest_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: GraphPackManifest requires full package identification and provenance fields."""
    schema_id = "https://schemas.mixu.app/graph/v1/graph-pack-manifest.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "graph_schema_version",
        "work_id",
        "edition_id",
        "graph_version",
        "reveal_anchor_map_version",
        "checksum_sha256",
        "package_format",
        "publication_policy",
        "source_excerpt_policy",
        "created_at",
        "copyright_basis",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_identity_link_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: IdentityLink requires link_id, entity_ids, kind, and first_reveal."""
    schema_id = "https://schemas.mixu.app/graph/v1/identity-link.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {"link_id", "entity_ids", "kind", "first_reveal"}
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_reveal_anchor_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: RevealAnchor requires anchor_id, edition_id, ordinal, locator, and reveal_kind."""
    schema_id = "https://schemas.mixu.app/graph/v1/reveal-anchor.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "anchor_id",
        "edition_id",
        "ordinal",
        "locator",
        "reveal_kind",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


def test_rule_user_overlay_schema_requires_mandatory_fields(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: UserOverlay requires overlay_id, object_type/id, timestamps, kind, payload."""
    schema_id = "https://schemas.mixu.app/graph/v1/user-overlay.schema.json"
    schema = schemas[schema_id]
    sample = baseline_samples[schema_id]
    expected_required = {
        "overlay_id",
        "object_type",
        "object_id",
        "created_at",
        "created_at_reveal",
        "kind",
        "payload",
    }
    assert set(schema.get("required", [])) == expected_required

    for field in expected_required:
        _assert_mutations_rejected(schema, sample, registry, field)


# ==============================================================================
# Validator Check Examples Integration Test
# ==============================================================================


def test_rule_validator_check_examples_fails_on_missing_required_property(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
    registry: Registry,
) -> None:
    """Rule protected: validate_contracts.check_examples must report failure when an example omits required fields."""
    entity_example = isolated_contracts_tree / "examples" / "graph" / "entity.json"
    doc = json.loads(entity_example.read_text(encoding="utf-8"))
    del doc["entity_id"]
    entity_example.write_text(json.dumps(doc), encoding="utf-8")

    problems = val_mod.check_examples(schemas, registry)
    assert any(
        "examples/graph/entity.json" in p and "entity_id" in p for p in problems
    ), f"Expected missing required property problem for entity.json, got: {problems}"


# ==============================================================================
# Broken $ref Pointer Mutation Tests
# ==============================================================================


def test_rule_openapi_ref_pointers_must_resolve(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: api/openapi.yaml local $ref pointers must resolve to valid component definitions."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    # Mutate a valid ref to point to a non-existent definition
    mutated = text.replace(
        "#/components/schemas/Health", "#/components/schemas/NonExistentHealth"
    )
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert any(
        "unresolved pointer #/components/schemas/NonExistentHealth" in p
        for p in problems
    ), f"Expected unresolved pointer problem, got: {problems}"


def test_rule_openapi_malformed_pointer_must_be_caught(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: api/openapi.yaml pointers to invalid path hierarchies must be detected."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    # Mutate to an invalid path pointer
    mutated = text.replace(
        "#/components/schemas/Health", "#/broken/nonexistent/pointer"
    )
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert any(
        "unresolved pointer #/broken/nonexistent/pointer" in p for p in problems
    ), f"Expected unresolved pointer problem, got: {problems}"


def test_rule_schema_internal_ref_pointer_must_resolve(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: JSON schema internal $ref pointers (#/$defs/...) must resolve within the document."""
    schema_id = "https://schemas.mixu.app/graph/v1/event.schema.json"
    doc = copy.deepcopy(schemas[schema_id])
    # Break internal pointer #/$defs/story_time -> #/$defs/nonexistent_time
    doc["properties"]["story_time"]["$ref"] = "#/$defs/nonexistent_time"

    val = Draft202012Validator(doc, registry=registry)
    sample = baseline_samples[schema_id]

    # Referencing raises when encountering a pointer to nowhere during validation
    with pytest.raises(Exception) as exc_info:
        list(val.iter_errors(sample))
    assert (
        "nonexistent_time" in str(exc_info.value)
        or "PointerToNowhere" in str(exc_info.value)
        or "Unresolvable" in str(exc_info.value)
    )


def test_rule_schema_cross_schema_ref_pointer_must_resolve(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: Cross-schema $ref pointers must resolve to valid target definitions in registry."""
    schema_id = "https://schemas.mixu.app/graph/v1/evidence-anchor.schema.json"
    doc = copy.deepcopy(schemas[schema_id])
    # Break cross-schema definition pointer to non-existent definition
    doc["properties"]["locator"]["$ref"] = (
        "reveal-anchor.schema.json#/$defs/nonexistent_locator"
    )

    val = Draft202012Validator(doc, registry=registry)
    sample = baseline_samples[schema_id]

    with pytest.raises(Exception) as exc_info:
        list(val.iter_errors(sample))
    assert (
        "nonexistent_locator" in str(exc_info.value)
        or "PointerToNowhere" in str(exc_info.value)
        or "Unresolvable" in str(exc_info.value)
    )


def test_rule_schema_nonexistent_uri_ref_must_fail(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: Schema $ref pointers referencing unresolvable schema URIs must be rejected."""
    schema_id = "https://schemas.mixu.app/graph/v1/evidence-anchor.schema.json"
    doc = copy.deepcopy(schemas[schema_id])
    # Point to completely non-existent schema file
    doc["properties"]["locator"]["$ref"] = "nonexistent-schema.json#/$defs/locator"

    val = Draft202012Validator(doc, registry=registry)
    sample = baseline_samples[schema_id]

    with pytest.raises(Exception) as exc_info:
        list(val.iter_errors(sample))
    assert "Unresolvable" in str(exc_info.value) or "nonexistent-schema" in str(
        exc_info.value
    )


# ==============================================================================
# Duplicate operationId Mutation Tests
# ==============================================================================


def test_rule_openapi_operation_ids_must_be_unique(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: api/openapi.yaml operationId values must be globally unique."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    # Duplicate operationId getMe onto patchMe
    mutated = text.replace("operationId: patchMe", "operationId: getMe")
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert "api/openapi.yaml: duplicate operationId getMe" in problems, (
        f"Expected duplicate operationId getMe problem, got: {problems}"
    )


def test_rule_openapi_multiple_duplicate_operation_ids_all_reported(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: Multiple duplicate operationIds in api/openapi.yaml must all be reported."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    # Duplicate two distinct operationIds
    mutated = text.replace("operationId: patchMe", "operationId: getMe")
    mutated = mutated.replace(
        "operationId: pullSyncChanges", "operationId: pushSyncMutations"
    )
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert "api/openapi.yaml: duplicate operationId getMe" in problems
    assert "api/openapi.yaml: duplicate operationId pushSyncMutations" in problems


# ==============================================================================
# Additional OpenAPI Validator Mutation Tests
# ==============================================================================


def test_rule_openapi_servers_block_must_match_api_base(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: api/openapi.yaml servers URL must match configured api_base_uri."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    # Mutate server URL to mismatched hostname
    mutated = text.replace("https://api.mixu.app/v1", "https://api.wrongdomain.org/v1")
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert any("does not start with configured API base URI" in p for p in problems)


def test_rule_openapi_unknown_error_code_token_rejected(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: api/openapi.yaml upper-case error tokens must be in error.schema.json enum."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    # Inject an unknown upper-case token
    mutated = text + "\n# Description token UNKNOWN_ERROR_CODE_XYZ\n"
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert any("unknown upper-case token UNKNOWN_ERROR_CODE_XYZ" in p for p in problems)


def test_rule_openapi_job_lifecycle_operations_defined() -> None:
    """Rule protected: api/openapi.yaml must declare all required job lifecycle operationIds."""
    path = REPO_ROOT / "api" / "openapi.yaml"
    text = path.read_text(encoding="utf-8")
    expected_ops = {
        "createUploadIntent",
        "createJob",
        "listJobs",
        "getJob",
        "cancelJob",
        "getJobResult",
    }
    found_ops = set(re.findall(r"operationId:\s*(\S+)", text))
    assert expected_ops.issubset(found_ops), (
        f"Missing operations: {expected_ops - found_ops}"
    )


def test_rule_openapi_job_lifecycle_schemas_defined() -> None:
    """Rule protected: api/openapi.yaml components/schemas must declare all required job lifecycle schemas."""
    path = REPO_ROOT / "api" / "openapi.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    schemas = doc.get("components", {}).get("schemas", {})
    expected_schemas = {
        "UploadIntentRequest",
        "UploadIntentResponse",
        "CreateJobRequest",
        "JobSummary",
        "JobDetail",
        "JobStatus",
        "JobProgress",
        "JobListResponse",
        "JobCancelResponse",
        "JobResultResponse",
    }
    assert expected_schemas.issubset(set(schemas.keys())), (
        f"Missing schemas: {expected_schemas - set(schemas.keys())}"
    )


def test_rule_openapi_job_duplicate_operation_id_caught(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: Duplicate operationId in job lifecycle must be caught by validator."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    mutated = text.replace("operationId: cancelJob", "operationId: createJob")
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert "api/openapi.yaml: duplicate operationId createJob" in problems


def test_rule_openapi_job_broken_ref_pointer_caught(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: Broken $ref pointer in job lifecycle must be detected."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    mutated = text.replace(
        "#/components/schemas/JobDetail", "#/components/schemas/NonExistentJobDetail"
    )
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert any(
        "unresolved pointer #/components/schemas/NonExistentJobDetail" in p
        for p in problems
    )


def test_rule_openapi_billing_marketplace_and_storage_contracts_defined() -> None:
    """Rule protected: api/openapi.yaml must declare ADR-030 and ADR-040 operations and schemas."""
    path = REPO_ROOT / "api" / "openapi.yaml"
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    expected_ops = {
        "getBillingWallet",
        "createAdRewardQrChallenge",
        "verifyAdReward",
        "publishMarketplacePack",
        "purchaseMarketplacePack",
        "getStorageQuota",
    }
    found_ops = set(re.findall(r"operationId:\s*(\S+)", text))
    assert expected_ops.issubset(found_ops), (
        f"Missing operations: {expected_ops - found_ops}"
    )

    schemas = doc.get("components", {}).get("schemas", {})
    expected_schemas = {
        "WalletSummary",
        "AdRewardQrChallengeRequest",
        "AdRewardQrChallengeResponse",
        "AdRewardVerifyRequest",
        "AdRewardVerifyResponse",
        "PublishMarketplacePackRequest",
        "MarketplacePackSummary",
        "PurchaseMarketplacePackRequest",
        "PurchaseMarketplacePackResponse",
        "StorageSubscriptionStatus",
        "StorageQuotaSummary",
    }
    assert expected_schemas.issubset(set(schemas.keys())), (
        f"Missing schemas: {expected_schemas - set(schemas.keys())}"
    )
    wallet_props = schemas["WalletSummary"]["properties"]
    for field in (
        "promo_credits_minor",
        "sub_credits_minor",
        "paid_credits_minor",
        "available_balance_minor",
        "reserved_balance_minor",
    ):
        assert field in wallet_props, f"Missing {field} in WalletSummary"
    assert schemas["StorageSubscriptionStatus"]["enum"] == [
        "ACTIVE",
        "GRACE_PERIOD",
        "OVER_QUOTA_EVICTED",
    ]
    assert "grace_period_ends_at" in schemas["StorageQuotaSummary"]["properties"]


def test_rule_error_schema_includes_storage_file_size_and_egress_codes(
    schemas: dict[str, dict],
    registry: Registry,
    baseline_samples: dict[str, dict],
) -> None:
    """Rule protected: error.schema.json must include FILE_SIZE_LIMIT_EXCEEDED and DAILY_DOWNLOAD_QUOTA_EXCEEDED."""
    schema_id = "https://schemas.mixu.app/api/v1/error.schema.json"
    schema = schemas[schema_id]
    code_enum = set(schema["properties"]["code"]["enum"])
    for code in ("FILE_SIZE_LIMIT_EXCEEDED", "DAILY_DOWNLOAD_QUOTA_EXCEEDED"):
        assert code in code_enum, f"Missing error code {code} in error.schema.json"
        payload = copy.deepcopy(baseline_samples[schema_id])
        payload["code"] = code
        Draft202012Validator(schema, registry=registry).validate(payload)


def test_rule_openapi_storage_levels_and_egress_contracts_defined() -> None:
    """Rule protected: api/openapi.yaml must declare 5-level storage progression, check-in/makeup, download-intent, and ad-boost contracts."""
    path = REPO_ROOT / "api" / "openapi.yaml"
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)

    expected_ops = {
        "checkInStorage",
        "makeupStorageCheckIn",
        "createDownloadIntent",
        "verifyDownloadAdBoost",
    }
    found_ops = set(re.findall(r"operationId:\s*(\S+)", text))
    assert expected_ops.issubset(found_ops), (
        f"Missing operations: {expected_ops - found_ops}"
    )

    paths = doc.get("paths", {})
    assert paths["/storage/check-in"]["post"]["operationId"] == "checkInStorage"
    assert (
        paths["/storage/check-in/makeup"]["post"]["operationId"]
        == "makeupStorageCheckIn"
    )
    assert (
        paths["/storage/objects/{uploadId}/download-intent"]["post"]["operationId"]
        == "createDownloadIntent"
    )
    assert (
        "429"
        in paths["/storage/objects/{uploadId}/download-intent"]["post"]["responses"]
    )
    assert (
        paths["/storage/download-boost/verify"]["post"]["operationId"]
        == "verifyDownloadAdBoost"
    )

    schemas = doc.get("components", {}).get("schemas", {})
    expected_schemas = {
        "StorageLevel",
        "StorageCheckInRequest",
        "StorageCheckInResponse",
        "MakeupCheckInRequest",
        "DownloadIntentRequest",
        "DownloadIntentResponse",
        "DownloadAdBoostVerifyRequest",
        "DownloadAdBoostVerifyResponse",
    }
    assert expected_schemas.issubset(set(schemas.keys())), (
        f"Missing schemas: {expected_schemas - set(schemas.keys())}"
    )
    for name in expected_schemas - {"StorageLevel"}:
        assert schemas[name].get("additionalProperties") is False, (
            f"{name} must set additionalProperties: false"
        )

    assert schemas["StorageLevel"]["enum"] == ["LV1", "LV2", "LV3", "LV4", "LV5"]
    assert schemas["UploadIntentRequest"]["properties"]["purpose"]["enum"] == [
        "graph_build",
        "edition_validation",
        "bookshelf_backup",
    ]

    quota_schema = schemas["StorageQuotaSummary"]
    assert quota_schema["required"] == [
        "user_id",
        "quota_limit_bytes",
        "used_bytes",
        "subscription_status",
    ]
    quota_props = quota_schema["properties"]
    expected_quota_props = {
        "storage_level",
        "base_quota_bytes",
        "subscription_bonus_bytes",
        "max_file_size_bytes",
        "daily_download_quota_bytes",
        "daily_download_used_bytes",
        "daily_download_ad_boost_bytes",
        "daily_ad_boosts_used",
        "daily_ad_boosts_cap",
        "monthly_download_used_bytes",
        "monthly_download_cap_bytes",
        "checkin_days",
        "checkin_streak",
        "checked_in_today",
        "monthly_makeup_used",
        "monthly_makeup_cap",
        "reading_minutes",
        "chapters_read",
        "graph_downloads",
        "ai_queries",
        "completed_graph_builds",
        "active_plan_id",
    }
    assert expected_quota_props.issubset(set(quota_props.keys())), (
        f"Missing StorageQuotaSummary properties: {expected_quota_props - set(quota_props.keys())}"
    )
    assert quota_props["storage_level"]["type"] == "integer"
    assert quota_props["storage_level"]["minimum"] == 1
    assert quota_props["storage_level"]["maximum"] == 5
    assert quota_props["checked_in_today"]["type"] == "boolean"
    assert quota_props["active_plan_id"]["type"] == ["string", "null"]

    assert set(schemas["StorageCheckInResponse"]["required"]) == {
        "already_checked_in",
        "newly_leveled_up",
        "quota_summary",
    }
    assert set(schemas["MakeupCheckInRequest"]["required"]) == {
        "target_day_key",
        "challenge_or_ad_id",
        "signature",
    }
    assert set(schemas["DownloadIntentResponse"]["required"]) == {
        "upload_id",
        "download_url",
        "expires_at",
        "size_bytes",
        "sha256",
        "daily_download_remaining_bytes",
        "monthly_download_remaining_bytes",
    }
    assert set(schemas["DownloadAdBoostVerifyRequest"]["required"]) == {
        "challenge_or_ad_id",
        "signature",
    }
    assert set(schemas["DownloadAdBoostVerifyResponse"]["required"]) == {
        "challenge_or_ad_id",
        "granted_boost_bytes",
        "daily_download_ad_boost_bytes",
        "daily_ad_boosts_used",
        "daily_ad_boosts_cap",
        "quota_summary",
    }

    verify_ad_desc = paths["/billing/ad-rewards/verify"]["post"]["description"]
    assert "+500 minor_units" in verify_ad_desc
    assert "5 promo_credits" in verify_ad_desc
    assert "3000 minor_units" in verify_ad_desc


def test_rule_openapi_storage_egress_broken_ref_and_duplicate_op_caught(
    isolated_contracts_tree: Path,
    schemas: dict[str, dict],
) -> None:
    """Rule protected: Duplicate operationIds and broken $ref pointers in storage egress endpoints are caught."""
    base_uri, api_base, _ = load_config()
    api_yaml = isolated_contracts_tree / "api" / "openapi.yaml"
    text = api_yaml.read_text(encoding="utf-8")

    mutated = text.replace(
        "operationId: makeupStorageCheckIn", "operationId: checkInStorage"
    )
    mutated = mutated.replace(
        "#/components/schemas/DownloadIntentResponse",
        "#/components/schemas/NonExistentDownloadIntentResponse",
    )
    api_yaml.write_text(mutated, encoding="utf-8")

    problems = val_mod.check_openapi(schemas, base_uri, api_base)
    assert "api/openapi.yaml: duplicate operationId checkInStorage" in problems
    assert any(
        "unresolved pointer #/components/schemas/NonExistentDownloadIntentResponse" in p
        for p in problems
    )
