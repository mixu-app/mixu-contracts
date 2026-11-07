# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Schema versions
are independent of the repository version.

## [Unreleased]

### Added

- Graph pack schema version 1 (draft): manifest, reveal anchor, entity,
  entity name, evidence anchor, event, assertion, assertion transition,
  identity link, user overlay.
- Error envelope schema with the shared error-code registry.
- `api/openapi.yaml`: draft `/v1` skeleton (`/health`, `/me`, `/sync/push`,
  `/sync/pull`, `/graphs/{pack_id}/download`) with documented invariants.
- `tools/validate_contracts.py` plus `just check`/`just validate` gates; the
  gate fails on an unresolved `$ref` and on a malformed example.
