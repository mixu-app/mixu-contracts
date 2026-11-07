# mixu-contracts quality gates. Run via `just check`, never bare tool invocations.
set shell := ["bash", "-euo", "pipefail", "-c"]

check: lint-md validate

lint-md:
    markdownlint-cli2 --config .markdownlint-cli2.jsonc

validate:
    python3 tools/validate_contracts.py

# Regenerate example payloads from the schemas' required fields (review the diff).
examples:
    python3 tools/render_examples.py
