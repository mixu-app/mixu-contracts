# mixu-contracts agent guide

## Scope and authority

- Governs only this repository. Workspace rules in `../AGENTS.md` apply.
- Public repository, **Apache-2.0**. Schemas are consumed by `mixu-client`,
  `mixu-server` and `mixu-ai-worker`; a field name decided here is a
  cross-repository contract.
- No business logic here: no prompts, no model routing, no pricing, no
  credentials.
- Prose authority: `mixu-docs` → `docs/specifications/narrative-graph.md` and
  `api-contracts.md`. A disagreement between prose and schema is a defect in both
  and is fixed in one change.

## Versioning (four independent numbers)

| Version | Lives in | Rule |
|---|---|---|
| Graph schema version | `graph-pack-manifest.schema.json` | Breaking change ⇒ new major version (`v2`), migration note, fixture update |
| Graph content version | same manifest | Per-edition content release (`1.2.0`) |
| API version | `api/openapi.yaml` (`/v1`) | Breaking change ⇒ new path version |
| Client app version | `mixu-client` | Never a proxy for the three above |

- Additive changes stay in the current major version; removals and semantic
  changes never do.
- Never reuse a removed field name for a different meaning.
- Every schema keeps an absolute `$id` under `https://schemas.mixu.app/...` and
  cross-references by that id, so validation works offline.

## Schema design rules

- Every schema has `additionalProperties: false` and an explicit `required` list;
  an implicit field is a bug.
- Data with a reveal boundary carries `first_reveal` (or `reveal_ordinal`); a
  future disclosure must not be inferable from an earlier record.
- `description` is English, states the invariant, and does not restate the field
  name.
- Examples live in `examples/` and must validate; a schema change without an
  updated example is incomplete.
- Error codes are a closed enum in `schemas/api/error.schema.json`; adding one is
  a contract change that consumers must accept.

## Gates

```sh
just check      # markdownlint + contract validation
just validate   # schemas, $refs, examples, OpenAPI pointers
just sync-uris  # sync schema $ids and OpenAPI servers from config
```

The validator must be able to fail: break a `$ref` character or an example field
and confirm a non-zero exit before trusting a green run.

## Never

- Do not encode a business rule in a schema (who may see what, at what price).
- Do not add a required field without a migration note; consumers pin an exact
  commit and an unannounced requirement breaks them.
- Do not paste book text into an example; use synthetic values.

## CarryCtx

- `cd` here before `carryctx` or Git; branches `ctx-XXXX/<type>-<slug>`.
- A schema change both surfaces consume needs review from the affected commander
  before merge.
- No commit, push or release without authorization.

## Review checklist

1. Is the change additive, or does it need a new major version?
2. Does an example prove the new field is usable?
3. Can an earlier reveal state still be reconstructed with this schema?
4. Did a consumer's pinned version break without a note?
5. Does `just validate` still fail when the contract is wrong?
