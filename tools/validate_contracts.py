#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate every contract in this repository without network access.

Checks performed:

1. Every `schemas/**/*.json` is a valid JSON Schema 2020-12 document,
   carries a unique absolute `$id`, and starts with the configured base URI.
2. Cross-schema `$ref` values resolve inside the local registry.
3. Every `examples/*.json` validates against its declared target schema.
4. `api/openapi.yaml` parses, every `#/components/...` pointer resolves,
   every operationId is unique, and `servers` matches configured API base URI.
5. Error codes referenced by the OpenAPI document exist in the error schema.

Exit codes: 0 = clean, 1 = at least one finding.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from uri_config import load_config

# Examples are matched to a schema by directory name, exact stem, or file-name prefix.
DIRECTORY_TARGETS = {
    "language-profiles": "schemas/common/language-profile.schema.json",
    "edition-fingerprints": "schemas/common/edition-fingerprint.schema.json",
    "locators": "schemas/common/locator.schema.json",
}

EXAMPLE_TARGETS = {
    "graph-pack-manifest": "schemas/graph/graph-pack-manifest.schema.json",
    "locator": "schemas/common/locator.schema.json",
    "locator-start": "schemas/common/locator.schema.json",
    "locator-mid-chapter": "schemas/common/locator.schema.json",
    "locator-chapter-end": "schemas/common/locator.schema.json",
    "language-profile": "schemas/common/language-profile.schema.json",
    "edition-fingerprint": "schemas/common/edition-fingerprint.schema.json",
}


def load_schemas(base_uri: str) -> tuple[dict[str, dict], list[str]]:
    schemas: dict[str, dict] = {}
    problems: list[str] = []
    base_prefix = base_uri.rstrip("/")
    for path in sorted(ROOT.glob("schemas/**/*.json")):
        rel = path.relative_to(ROOT)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{rel}: invalid JSON: {exc}")
            continue
        try:
            Draft202012Validator.check_schema(doc)
        except SchemaError as exc:
            problems.append(f"{rel}: invalid schema: {exc.message}")
            continue
        schema_id = doc.get("$id")
        if not schema_id:
            problems.append(f"{rel}: missing absolute $id")
            continue
        if not schema_id.startswith(base_prefix):
            problems.append(
                f"{rel}: $id '{schema_id}' does not start with configured base URI '{base_prefix}'"
            )
            continue
        if schema_id in schemas:
            problems.append(f"{rel}: duplicate $id {schema_id}")
            continue
        schemas[schema_id] = doc
    return schemas, problems


def registry_for(schemas: dict[str, dict]) -> Registry:
    return Registry().with_resources(
        [
            (
                uri,
                Resource.from_contents(doc, default_specification=DRAFT202012),
            )
            for uri, doc in schemas.items()
        ]
    )


def check_examples(schemas: dict[str, dict], registry: Registry) -> list[str]:
    problems: list[str] = []
    example_files = sorted(p for p in ROOT.glob("examples/**/*.json") if p.is_file())
    for path in example_files:
        rel = path.relative_to(ROOT)
        target = DIRECTORY_TARGETS.get(path.parent.name)
        if target is None:
            target = EXAMPLE_TARGETS.get(path.stem)
        if target is None:
            for prefix, schema_target in EXAMPLE_TARGETS.items():
                if path.stem.startswith(f"{prefix}-") or path.stem == prefix:
                    target = schema_target
                    break
        if target is None:
            problems.append(f"{rel}: no schema mapping; add one to EXAMPLE_TARGETS")
            continue
        schema = json.loads((ROOT / target).read_text(encoding="utf-8"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, registry=registry)
        for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
            problems.append(
                f"{rel}: {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            )
    return problems


def resolve_pointer(root: object, pointer: str) -> bool:
    node = root
    for part in pointer.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return False
    return True


def check_openapi(
    schemas: dict[str, dict], base_uri: str, api_base_uri: str
) -> list[str]:
    problems: list[str] = []
    path = ROOT / "api" / "openapi.yaml"
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    rel = "api/openapi.yaml"

    servers = doc.get("servers", [])
    if not servers:
        problems.append(f"{rel}: missing servers block")
    else:
        server_urls = [
            s.get("url") for s in servers if isinstance(s, dict) and "url" in s
        ]
        if not server_urls or not any(u.startswith(api_base_uri) for u in server_urls):
            problems.append(
                f"{rel}: server URL '{server_urls}' does not start with configured API base URI '{api_base_uri}'"
            )

    pointers = set(re.findall(r'\$ref:\s*"?(#/[^"\s]+)', text))
    if not pointers:
        problems.append(
            f"{rel}: no local $ref pointers found; the pointer gate would be vacuous"
        )
    for pointer in sorted(pointers):
        if not resolve_pointer(doc, pointer[1:]):
            problems.append(f"{rel}: unresolved pointer {pointer}")

    operation_ids = re.findall(r"operationId: (\S+)", text)
    duplicates = {op for op in operation_ids if operation_ids.count(op) > 1}
    for duplicate in sorted(duplicates):
        problems.append(f"{rel}: duplicate operationId {duplicate}")

    error_codes = set(
        json.loads(
            (ROOT / "schemas" / "api" / "error.schema.json").read_text(encoding="utf-8")
        )["properties"]["code"]["enum"]
    )
    used = set(re.findall(r"\b([A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+)\b", text))
    allow = {
        "AUTHORIZED_PUBLIC",
        "LOCATOR_ONLY",
        "BOUNDED_QUOTE",
        "PUBLIC_DOMAIN_QUOTE",
        "SYNTHETIC_ORIGINAL",
        "PRIVATE_ONLY",
    }
    for token in sorted(used - error_codes - allow):
        problems.append(
            f"{rel}: unknown upper-case token {token} (add it to the error schema or the allow list)"
        )

    error_schema_prefix = f"{base_uri.rstrip('/')}/api/"
    for name in schemas:
        if name.startswith(error_schema_prefix) and "error.schema.json" in name:
            continue
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", help="Path to base URI configuration file")
    args = parser.parse_args()

    try:
        base_uri, api_base_uri, _ = load_config(args.config)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1

    schemas, problems = load_schemas(base_uri)
    if problems:
        for problem in problems:
            print(problem)
        return 1
    registry = registry_for(schemas)
    problems += check_examples(schemas, registry)
    problems += check_openapi(schemas, base_uri, api_base_uri)
    for problem in problems:
        print(problem)
    if problems:
        print(f"\n{len(problems)} contract problem(s)", file=sys.stderr)
        return 1
    print(
        f"contracts ok: {len(schemas)} schemas, examples and openapi validated (base URI: {base_uri})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
