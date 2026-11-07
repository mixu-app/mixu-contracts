# mixu-contracts quality gates. Run via `just check`, never bare tool invocations.
set shell := ["bash", "-euo", "pipefail", "-c"]

py := if `which uv 2>/dev/null` != "" { "uv run" } else { "" }

check: lint-md validate test

lint-md:
    markdownlint-cli2 --config .markdownlint-cli2.jsonc

validate:
    {{py}} python3 tools/validate_contracts.py

test:
    {{py}} pytest

# Sync schema $ids and OpenAPI server URLs from the authoritative base URI config.
sync-uris:
    {{py}} python3 tools/sync_schema_uris.py

# Regenerate example payloads from the schemas' required fields (review the diff).
examples:
    {{py}} python3 tools/render_examples.py
