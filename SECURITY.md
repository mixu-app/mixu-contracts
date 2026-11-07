# Security policy

## Supported versions

Pre-release. No version is supported for production use yet; security fixes
land on `main`. An iOS, desktop or hosted-service support matrix does not
exist yet.

## Reporting a vulnerability

Do **not** open a public issue for a security problem.

Use GitHub private vulnerability reporting on this repository: **Security** tab
→ **Report a vulnerability**. That channel is private to the maintainers.

Include:

- the affected component and version/commit,
- a minimal reproduction (synthetic text, not a copyrighted book),
- the impact (data exposure, spoiler leak, billing, denial of service),
- whether reader notes, book content, tokens or account data are involved,
- the severity you believe applies.

Do not attach EPUB files, book excerpts or personal notes. If a real book is
required to reproduce a defect, describe the structural property instead and
the maintainers will supply a synthetic fixture.

## What counts as a security issue here

- A reader can see narrative information beyond the knowledge horizon
  (a spoiler leak is treated as a correctness and trust defect, not a
  cosmetic bug).
- Another account's books, notes, overlays or uploads are readable.
- A presigned URL, token or credential leaks through logs, telemetry, an
  exported settings file or a client bundle.
- A malicious EPUB escapes the parser sandbox, exhausts device storage, or
  triggers network fetches the reader did not request.
- A billable action runs without an approved maximum, or settlement is not
  idempotent.

## Disclosure and response

We aim to acknowledge a report promptly and to agree a disclosure timeline
with the reporter. No fixed SLA is promised for this pre-release phase.
Please do not disclose publicly before a fix or a coordinated date.
