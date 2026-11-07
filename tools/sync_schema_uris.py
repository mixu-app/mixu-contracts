#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sync schema $ids, cross-schema $ref prefixes, and OpenAPI servers from config.

Usage:
    python3 tools/sync_schema_uris.py [--check] [--config PATH] [--base-uri URI]

Exit codes:
    0 = clean / updated successfully
    1 = error or in --check mode when changes are needed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from uri_config import derive_api_url, load_config


def rewrite_refs(obj: Any, new_base_uri: str) -> bool:
    """Rewrite absolute URI prefixes in $ref values to new_base_uri."""
    changed = False
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                if v.startswith(("http://", "https://")):
                    parsed_ref = urlparse(v)
                    subpath = parsed_ref.path.lstrip("/")
                    fragment_part = (
                        f"#{parsed_ref.fragment}" if parsed_ref.fragment else ""
                    )
                    new_ref = f"{new_base_uri.rstrip('/')}/{subpath}{fragment_part}"
                    if new_ref != v:
                        obj[k] = new_ref
                        changed = True
            elif isinstance(v, (dict, list)) and rewrite_refs(v, new_base_uri):
                changed = True
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)) and rewrite_refs(item, new_base_uri):
                changed = True
    return changed


def compute_schema_id(schema_path: Path, current_id: str, new_base_uri: str) -> str:
    parsed_id = urlparse(current_id)
    if parsed_id.path.strip("/"):
        subpath = parsed_id.path.lstrip("/")
    else:
        rel = schema_path.relative_to(ROOT / "schemas")
        parts = rel.parts
        if (
            len(parts) >= 2
            and parts[0] in ("graph", "api")
            and not parts[1].startswith("v")
        ):
            subpath = f"{parts[0]}/v1/{rel.name}"
        else:
            subpath = str(rel)
    return f"{new_base_uri.rstrip('/')}/{subpath}"


def sync_schema_file(
    schema_path: Path, new_base_uri: str, check_only: bool
) -> tuple[bool, str]:
    content = schema_path.read_text(encoding="utf-8")
    doc = json.loads(content)
    changed = False

    current_id = doc.get("$id", "")
    new_id = compute_schema_id(schema_path, current_id, new_base_uri)
    if current_id != new_id:
        doc["$id"] = new_id
        changed = True

    if rewrite_refs(doc, new_base_uri):
        changed = True

    if changed and not check_only:
        new_content = json.dumps(doc, indent=2) + "\n"
        schema_path.write_text(new_content, encoding="utf-8")

    return changed, new_id


def sync_openapi_servers(
    openapi_path: Path, new_server_url: str, check_only: bool
) -> bool:
    content = openapi_path.read_text(encoding="utf-8")
    pattern = r"(servers:\s*\n\s*-\s*url:\s*)['\"]?([^'\"\s\n]+)['\"]?"
    match = re.search(pattern, content)
    if not match:
        raise ValueError(f"Could not find 'servers: - url:' block in {openapi_path}")

    current_url = match.group(2)
    if current_url == new_server_url:
        return False

    if not check_only:
        new_content = (
            content[: match.start(2)] + new_server_url + content[match.end(2) :]
        )
        parsed = yaml.safe_load(new_content)
        servers = parsed.get("servers", [])
        if not servers or servers[0].get("url") != new_server_url:
            raise ValueError(f"Failed to update servers URL in {openapi_path}")
        openapi_path.write_text(new_content, encoding="utf-8")

    return True


def sync_uris(
    config_path: Path | str | None = None,
    override_base_uri: str | None = None,
    check_only: bool = False,
) -> int:
    if override_base_uri:
        schema_base = override_base_uri.rstrip("/")
        api_base = derive_api_url(schema_base)
        cfg_path_display = "(cli override)"
    else:
        schema_base, api_base, cfg_path = load_config(config_path)
        try:
            cfg_path_display = str(cfg_path.relative_to(ROOT))
        except ValueError:
            cfg_path_display = str(cfg_path)

    schema_files = sorted(ROOT.glob("schemas/**/*.json"))
    updated_schemas: list[str] = []
    for schema_file in schema_files:
        changed, _ = sync_schema_file(schema_file, schema_base, check_only=check_only)
        if changed:
            updated_schemas.append(str(schema_file.relative_to(ROOT)))

    openapi_path = ROOT / "api" / "openapi.yaml"
    openapi_changed = False
    if openapi_path.exists():
        openapi_changed = sync_openapi_servers(
            openapi_path, api_base, check_only=check_only
        )

    total_changes = len(updated_schemas) + (1 if openapi_changed else 0)

    if check_only:
        if total_changes > 0:
            print(
                f"OutOfSync: {total_changes} file(s) differ from base URI {schema_base} ({cfg_path_display}):"
            )
            for rel in updated_schemas:
                print(f"  {rel}")
            if openapi_changed:
                print(f"  {openapi_path.relative_to(ROOT)}")
            return 1
        print(f"Up to date: all schemas and openapi.yaml match base URI {schema_base}")
        return 0

    if total_changes == 0:
        print(
            f"Up to date: all {len(schema_files)} schemas and openapi.yaml already match base URI {schema_base}"
        )
        return 0

    print(
        f"Synced {total_changes} file(s) using base URI {schema_base} ({cfg_path_display}):"
    )
    for rel in updated_schemas:
        print(f"  updated $id/$ref: {rel}")
    if openapi_changed:
        print(f"  updated server URL to {api_base}: {openapi_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", help="Path to base URI configuration file")
    parser.add_argument("--base-uri", help="Override base URI directly")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write changes; exit 1 if files need update",
    )
    args = parser.parse_args()

    try:
        return sync_uris(
            config_path=args.config,
            override_base_uri=args.base_uri,
            check_only=args.check,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
