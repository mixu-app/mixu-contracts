# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Schema versions
are independent of the repository version.

## [Unreleased]

### Added

- Frozen graph schema v1 with realistic examples in `examples/graph/` (entity,
  entity-name, reveal-anchor, evidence-anchor, event, assertion,
  assertion-transition, identity-link, user-overlay), field optionality
  justification, compatibility semantics, version negotiation rules, and
  mutation tests (`tests/test_graph_schemas.py`).

- Language profile schema (`schemas/common/language-profile.schema.json`) for
  data-driven, parameterized language configurations (chapter detection regexes,
  quote delimiters, honorifics, alias markers, ruby policies, naming conventions)
  without code-level language branching.
- Edition fingerprint schema (`schemas/common/edition-fingerprint.schema.json`)
  enforcing exact edition and normalizer binding; fingerprints missing either
  `profile_version` or `normalization_version` are strictly invalid.
- Language profile examples (`examples/language-profiles/`) for `zh-Hans`, `en`,
  `ja`, and universal `generic` fallback.
- Edition fingerprint examples (`examples/edition-fingerprints/`) with SHA-256
  checksums, spine orders, and semver bindings.
- Test suite (`tests/test_language_profile_schemas.py`) covering profile/fingerprint
  schema invariants, negative test cases, and validator gate integration.
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
