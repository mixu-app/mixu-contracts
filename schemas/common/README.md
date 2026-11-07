# Common schemas

Status: **Proposed** · Owner: mixu-core

Shared foundational schemas consumed across domains (reading engine, graph engine,
and cloud extraction workers).

## Files

| Schema | Purpose |
|---|---|
| `locator.schema.json` | Edition-bound reading locator with spine coordinates, character offsets, progression, EPUB CFI, and text quote |
| `language-profile.schema.json` | Data-driven language profile specification for segmentation, chapter boundaries, quotation marks, honorifics, alias markers, and ruby text handling |
| `edition-fingerprint.schema.json` | Exact edition binding manifest capturing content hash, BCP-47 language tag, profile version, text normalization version, and spine ordering |

## Normative rules

- **A locator never carries a rendered page number**: Page numbers vary dynamically
  with screen size, font scale, margins, and device DPI. Locators bind to an exact
  `edition_fingerprint` and reference content via spine items, character offsets,
  and relative progression.
- **Language profiles are pure, parameterized data models**: All language-specific
  characteristics (chapter regex patterns, quote delimiters, honorifics, alias
  markers, and ruby text policies) are data-driven configuration instances with zero
  code-level branching.
- **An edition fingerprint missing any version field is strictly invalid**: Both
  `profile_version` and `normalization_version` are mandatory. Text offsets, token
  boundaries, and locators directly depend on normalizer and profile semantics;
  changing either version invalidates locators the same way a content change does.
- **Strict schema**: Extraneous properties are rejected (`additionalProperties: false`)
  to prevent smuggling volatile UI or display-specific state into durable contracts.
