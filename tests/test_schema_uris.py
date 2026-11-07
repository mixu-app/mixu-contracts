#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for schema URI synchronization and validation."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from sync_schema_uris import compute_schema_id, rewrite_refs, sync_uris
from uri_config import derive_api_url, get_base_uris_from_dict, get_domain
from validate_contracts import check_openapi, load_schemas


def test_get_domain_and_derive_api_url() -> None:
    assert get_domain("https://schemas.mixu.app") == "mixu.app"
    assert get_domain("https://schemas.mixu.app/path") == "mixu.app"
    assert get_domain("https://schema.example.com") == "example.com"
    assert get_domain("https://api.test.org") == "test.org"
    assert get_domain("https://mixu.xuepoo.xyz") == "mixu.xuepoo.xyz"

    assert derive_api_url("https://schemas.mixu.app") == "https://api.mixu.app/v1"
    assert derive_api_url("https://schemas.example.com") == "https://api.example.com/v1"
    assert derive_api_url("http://localhost:8080") == "http://api.localhost:8080/v1"


def test_get_base_uris_from_dict() -> None:
    data = {"schema_base_uri": "https://schemas.mixu.app"}
    schema_base, api_base = get_base_uris_from_dict(data)
    assert schema_base == "https://schemas.mixu.app"
    assert api_base == "https://api.mixu.app/v1"

    data_base = {"base_uri": "https://schemas.custom.io"}
    schema_base, api_base = get_base_uris_from_dict(data_base)
    assert schema_base == "https://schemas.custom.io"
    assert api_base == "https://api.custom.io/v1"

    # Mismatched domain should follow schema_base
    data_mismatch = {
        "schema_base_uri": "https://schemas.newdomain.com",
        "api_base_uri": "https://api.olddomain.com/v1",
    }
    schema_base, api_base = get_base_uris_from_dict(data_mismatch)
    assert schema_base == "https://schemas.newdomain.com"
    assert api_base == "https://api.newdomain.com/v1"


def test_compute_schema_id() -> None:
    p = Path("/dummy/schemas/graph/assertion.schema.json")
    old_id = "https://schemas.old.app/graph/v1/assertion.schema.json"
    new_id = compute_schema_id(p, old_id, "https://schemas.new.app")
    assert new_id == "https://schemas.new.app/graph/v1/assertion.schema.json"


def test_rewrite_refs() -> None:
    doc = {
        "local": {"$ref": "#/$defs/thing"},
        "relative": {"$ref": "other.schema.json#/$defs/locator"},
        "absolute": {
            "$ref": "https://schemas.old.app/graph/v1/entity.schema.json#/$defs/name"
        },
        "nested": [{"$ref": "https://schemas.old.app/graph/v1/event.schema.json"}],
    }
    changed = rewrite_refs(doc, "https://schemas.new.app")
    assert changed is True
    assert doc["local"]["$ref"] == "#/$defs/thing"
    assert doc["relative"]["$ref"] == "other.schema.json#/$defs/locator"
    assert (
        doc["absolute"]["$ref"]
        == "https://schemas.new.app/graph/v1/entity.schema.json#/$defs/name"
    )
    assert (
        doc["nested"][0]["$ref"] == "https://schemas.new.app/graph/v1/event.schema.json"
    )


@pytest.fixture
def isolated_contracts_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Path, None, None]:
    repo_root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Copy schemas, api, config, examples
        shutil.copytree(repo_root / "schemas", tmp_path / "schemas")
        shutil.copytree(repo_root / "api", tmp_path / "api")
        shutil.copytree(repo_root / "config", tmp_path / "config")
        shutil.copytree(repo_root / "examples", tmp_path / "examples")

        import sync_schema_uris as sync_mod
        import uri_config as config_mod
        import validate_contracts as val_mod

        monkeypatch.setattr(config_mod, "ROOT", tmp_path)
        monkeypatch.setattr(sync_mod, "ROOT", tmp_path)
        monkeypatch.setattr(val_mod, "ROOT", tmp_path)

        yield tmp_path


def test_sync_uris_end_to_end(isolated_contracts_tree: Path) -> None:
    tmp_path = isolated_contracts_tree
    cfg_file = tmp_path / "config" / "schema-base-uri.json"

    # 1. Initially in sync
    import uri_config as config_mod

    initial_base, _, _ = config_mod.load_config()
    schemas, problems = load_schemas(initial_base)
    assert not problems
    assert len(schemas) == 11

    # 2. Change base URI in config
    new_base = "https://schemas.staging.mixu.io"
    cfg_file.write_text(json.dumps({"schema_base_uri": new_base}), encoding="utf-8")

    # 3. Before sync, check_only reports out of sync
    assert sync_uris(check_only=True) == 1

    # Before sync, validator fails because schema $id doesn't start with new_base
    schemas, problems = load_schemas(new_base)
    assert len(problems) == 11
    assert "does not start with configured base URI" in problems[0]

    # 4. Run sync_uris
    ret = sync_uris(check_only=False)
    assert ret == 0

    # 5. After sync, check_only reports up to date
    assert sync_uris(check_only=True) == 0

    # All schemas have updated $id
    for path in tmp_path.glob("schemas/**/*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["$id"].startswith(new_base)

    # OpenAPI server URL is updated
    openapi_doc = yaml.safe_load(
        (tmp_path / "api" / "openapi.yaml").read_text(encoding="utf-8")
    )
    assert openapi_doc["servers"][0]["url"] == "https://api.staging.mixu.io/v1"

    # Validator passes cleanly
    schemas, problems = load_schemas(new_base)
    assert not problems
    problems_api = check_openapi(schemas, new_base, "https://api.staging.mixu.io/v1")
    assert not problems_api


def test_validator_fails_on_wrong_id(isolated_contracts_tree: Path) -> None:
    tmp_path = isolated_contracts_tree
    import uri_config as config_mod

    current_base, _, _ = config_mod.load_config()
    target_schema = tmp_path / "schemas" / "graph" / "assertion.schema.json"
    doc = json.loads(target_schema.read_text(encoding="utf-8"))
    doc["$id"] = "https://malicious.domain/graph/v1/assertion.schema.json"
    target_schema.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    _, problems = load_schemas(current_base)
    assert len(problems) == 1
    assert "schemas/graph/assertion.schema.json" in problems[0]
    assert "does not start with configured base URI" in problems[0]
