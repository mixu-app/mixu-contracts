# Common schemas

Status: **Proposed** · Owner: mixu-core

Shared foundational schemas consumed across domains (reading engine, graph engine,
and cloud extraction workers).

## Files

| Schema | Purpose |
|---|---|
| `locator.schema.json` | Edition-bound reading locator with spine coordinates, character offsets, progression, EPUB CFI, and text quote |

## Normative rules

- **A locator never carries a rendered page number**: Page numbers vary dynamically
  with screen size, font scale, margins, and device DPI. Locators bind to an exact
  `edition_fingerprint` and reference content via spine items, character offsets,
  and relative progression.
- **Strict schema**: Extraneous properties are rejected (`additionalProperties: false`)
  to prevent smuggling volatile UI or display-specific state into durable contracts.
