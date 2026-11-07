# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Schema versions
are independent of the repository version.

## [Unreleased]

### Added

- Shared reading locator schema (`schemas/common/locator.schema.json`) with
  edition fingerprint, spine index/href, character offsets, relative progression,
  EPUB CFI, and text quote context; enforces the normative rule against rendered
  page numbers and forbids extraneous properties.
- Realistic locator examples (`examples/locators/`) covering start, mid-chapter,
  and chapter-end positions.
- Locator test suite (`tests/test_locator_schema.py`) and validator mapping in
  `tools/validate_contracts.py`.
- Single-source schema base URI config (`config/schema-base-uri.json`) and
  generator (`tools/sync_schema_uris.py`, `just sync-uris`) to synchronize
  schema `$id`s, cross-schema `$ref` prefixes, and OpenAPI `servers`.
- Contract validator checks that all schema `$id`s and OpenAPI `servers` match
  the configured base URI.
- Graph pack schema version 1 (draft): manifest, reveal anchor, entity,
  entity name, evidence anchor, event, assertion, assertion transition,
  identity link, user overlay.
- Error envelope schema with the shared error-code registry.
- `api/openapi.yaml`: draft `/v1` skeleton (`/health`, `/me`, `/sync/push`,
  `/sync/pull`, `/graphs/{pack_id}/download`) with documented invariants.
- `tools/validate_contracts.py` plus `just check`/`just validate` gates; the
  gate fails on an unresolved `$ref` and on a malformed example.
