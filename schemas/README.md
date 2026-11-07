# Graph pack schemas — version 1 (draft)

Status: **Proposed** · Schema version: `1` · Owner: mixu-core

These files define what a graph pack contains and what a projection may expose
at a given reveal ordinal. The prose authority is
`mixu-docs` → `docs/specifications/narrative-graph.md`; if the two disagree,
that is a defect in both and must be fixed in one change.

## Files

| Schema | Purpose |
|---|---|
| `graph-pack-manifest.schema.json` | Package identity, checksums, provenance, rights basis |
| `reveal-anchor.schema.json` | Edition-bound ordinal and normalized locator (defines the shared `locator` shape) |
| `entity.schema.json` | Person, persona, location, organization, object |
| `entity-name.schema.json` | Display name or alias with its own reveal boundary |
| `evidence-anchor.schema.json` | Source location behind a claim, with excerpt policy |
| `event.schema.json` | Story-world happening with optional partial/uncertain time |
| `assertion.schema.json` | Typed claim with attribution and epistemic status |
| `assertion-transition.schema.json` | Append-only later status change |
| `identity-link.schema.json` | Reveal-scoped same-person link |
| `user-overlay.schema.json` | Private reader annotation referencing stable IDs |

Every schema carries an absolute `$id` under
`https://schemas.mixu.app/graph/v1/`. Cross-schema references use those ids, so
validation works offline from a local registry and never fetches a URL.

## Invariants the schemas cannot express

A schema validates one record. The following are projection rules and must be
enforced by the query layer, with fixtures:

- No projection at ordinal `r` exposes a label, alias, relation, identity
  merge, evidence preview, count or layout hint whose reveal exceeds `r`.
- `assertion_transitions` are append-only; viewing an earlier ordinal shows the
  earlier status, not the latest one.
- `identity_links` at a boundary later than `r` must not merge entities in the
  `r` projection, and must not retroactively rename them.
- `user_overlay` with `visibility = FROM_CREATION` stays hidden during a
  historical replay earlier than `created_at_reveal`.
- Search/FTS/autocomplete are built from the same filtered projection, never
  from the full pack.

## Changing a schema

1. Additive, backward-compatible change: extend the schema, keep version `1`,
   update `difficulty`-free examples, note it in `CHANGELOG`.
2. Breaking change: new schema version directory (`v2`), migration note in
   `mixu-docs`, updated fixtures, and a consumer review from both
   `mixu-client` and `mixu-server`.
3. Never reuse a removed field name for a different meaning.

## Validation

`tools/validate_contracts.py` (run through `just validate`) checks schema
validity, `$id` uniqueness, local `$ref` resolution, example conformance and
OpenAPI pointer integrity. It must fail when any of those is broken; a gate that
cannot fail is not a gate.
