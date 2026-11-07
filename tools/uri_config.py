#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""URI configuration loader and derivation utilities for mixu-contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

CONFIG_CANDIDATES = [
    ROOT / "config" / "schema-base-uri.json",
    ROOT / "config.json",
    ROOT / "base-uri.json",
]


def find_config_path(explicit_path: Path | str | None = None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        return path

    candidates = [
        ROOT / "config" / "schema-base-uri.json",
        ROOT / "config.json",
        ROOT / "base-uri.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def get_domain(uri: str) -> str:
    parsed = urlparse(uri)
    host = parsed.netloc or parsed.path
    if ":" in host:
        host = host.split(":", 1)[0]
    for prefix in ("schemas.", "schema.", "api."):
        if host.startswith(prefix):
            return host[len(prefix) :]
    return host


def derive_api_url(schema_base_uri: str, api_path: str = "/v1") -> str:
    parsed = urlparse(schema_base_uri)
    domain = get_domain(schema_base_uri)
    scheme = parsed.scheme or "https"

    port_str = ""
    host = parsed.netloc or parsed.path
    if ":" in host:
        port_str = ":" + host.split(":", 1)[1]

    return f"{scheme}://api.{domain}{port_str}{api_path}"


def get_base_uris_from_dict(data: dict[str, Any]) -> tuple[str, str]:
    schema_base = data.get("schema_base_uri") or data.get("base_uri")
    if not schema_base:
        raise ValueError("Configuration must define 'schema_base_uri' or 'base_uri'")
    schema_base = schema_base.rstrip("/")

    api_base = data.get("api_base_uri") or data.get("api_server_url")
    derived_api = derive_api_url(schema_base)
    if not api_base:
        api_base = derived_api
    else:
        # If schema_base domain changed from api_base domain, follow schema_base
        if get_domain(schema_base) != get_domain(api_base):
            api_base = derived_api

    return schema_base, api_base


def load_config(explicit_path: Path | str | None = None) -> tuple[str, str, Path]:
    config_path = find_config_path(explicit_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing base URI configuration file: {config_path} does not exist. "
            f"Expected one of: {[str(c.relative_to(ROOT)) for c in CONFIG_CANDIDATES]}"
        )

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{config_path}: invalid JSON: {exc}") from exc

    schema_base, api_base = get_base_uris_from_dict(data)
    return schema_base, api_base, config_path
