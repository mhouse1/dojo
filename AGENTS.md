
# ROE — Rules Of Engagement for Development

| Status   | Date       | Project Version |
|----------|------------|-----------------|
| Active   | 2026-04-11 | 1.0.0           |

Pragmatic, system-agnostic rules for documentation, code review, and collaboration. Applies to all work in this repository, whether firmware, hardware, or other systems. All contributors must follow these rules to ensure clarity, traceability, and maintainability.

## Project Philosophy

- **Pragmatism over bureaucracy:** Commands in the Makefile are intentionally short for frequent use. Documentation is concise and actionable.
- **docs/ folder:** All documentation lives under `docs/`, with subfolders for ADRs, job aids, performance notes, code reviews, and more. All subfolders start empty and are populated as needed.
- **System-agnostic:** These rules apply to any type of project or artifact managed in this repository.


## Sequential Numbering — All `docs/` Subdirectories

Every file created under any subdirectory of `docs/` must have a zero-padded three-digit prefix:

```
001-my-document.md
002-another-document.md
```

Before creating a new file in any `docs/` subdirectory, use the **Glob tool** to list existing files in that folder — do not use shell commands (PowerShell or Bash), which may return empty results silently on this platform. Find the highest number and increment by 1. Never guess or reuse a number — gaps and collisions break the sequence across sessions.

This applies to: `docs/adr/`, `docs/job-aid/`, `docs/performance/`, `docs/code-review/`, `docs/roadmap/`, and any future subdirectory under `docs/`.


## ADR — Sequential Numbering

The general sequential numbering rule above applies. Additionally: before creating a new ADR, use the **Glob tool** to list the files in `docs/adr/` and find the highest existing number, then increment by 1.


## ADR — Performance Changes

Performance ADRs must include actual measured data, not just estimates. Before/after measurements should come directly from real system logs or test results.


## ADR — Superseding Decisions

Do not modify an ADR that has status `Accepted`. If a decision is superseded, write a new ADR and reference the old one. This keeps the decision history intact.


## Diagrams

Always use Mermaid for diagrams in documentation. Never use ASCII text diagrams (no box-drawing characters, no `┌─┐` borders, no `→` arrow art). Wrap all diagrams in a fenced code block with the `mermaid` language tag.

Use a compatibility-first Mermaid profile for shared docs:

- Default to syntax that renders across common Mermaid versions and renderers.
- Keep node labels plain-language; do not put symbolic expressions (for example `>`, `<`, `<=`, `>=`, or punctuation-heavy logic) inside node declarations.
- Put equations and conditions in nearby bullets or surrounding prose, not in decision-node text.
- **Forbidden in node labels and edge labels:** `~`, `/`, `+`, `@`, `#`, `;` — these cause silent parse failures across common renderers. Use plain English instead: "and" for `+`, "approx" for `~`, "via" for `/`, "at" for `@`.
- **Edge labels** (`-->|text|` syntax) must contain only plain alphanumeric text, spaces, hyphens, and periods. No other punctuation.
- To include a special character in a node label, wrap the label in double quotes: `A["label text"]` — this requires Mermaid v10+; prefer omitting special characters for maximum compatibility.

Advanced Mermaid features must only be used when both conditions are met:

1. The target renderer or pipeline version is known to support the feature.
2. A simplified fallback diagram, or equivalent textual explanation, is provided for portability.

After creating or editing Mermaid blocks, verify they render in the target environment, not only in one local preview.


## Document Heading Format

All new documents (job aids, performance docs, code reviews, ADRs, and any other docs under `docs/`) must begin with a title and a compact status/metadata table immediately after:

```
# <Document Type NNN> — <Title>

| Status   | Date       | Project Version |
|----------|------------|-----------------|
| Draft    | 2026-04-11 | See Makefile    |
```

- Read the version from the `VERSION` file at the repository root — never guess it.
- Use today's actual date.
- Use `Draft` for new documents; update to `Active` or `Accepted` once reviewed.
- **ADRs** must start as `Draft` when first created.
- Update an ADR to `Accepted` only after implementation is complete.


## Architecture Documents (HLDD)

Architecture documents live in `docs/hldd/`. Each file covers the high-level design for a system, subsystem, or feature.

Files follow the standard sequential numbering rule: `001-component-name.md`, `002-…`, etc.

Architecture documents must include the standard heading format with version and date — read the version from the `VERSION` file, never guess it. Use `Draft` status for new documents; update to `Active` once reviewed.


## Review Todos

Review files live in `docs/code-review/` and are numbered sequentially (`001-YYYY-MM.md`, `002-…`, etc.). Each file covers one review cycle.

Review-cycle files are immutable after closure. Do not edit a closed review to change findings, severity, or the narrative assessment.

Allowed before closure:
- Add a final resolution summary for items reviewed in that cycle.

After closure:
- Record later status changes in a new review-cycle file, not by rewriting the old file.
- Reference the original item ID and mark the current disposition explicitly: `Resolved`, `Deferred`, `Superseded`, or `Closed as stale`.
- Treat the newest review-cycle file that references the item as the authoritative current disposition.


## Requirements Documents

Requirements live in `docs/requirements/`. Each file covers a discrete requirement or requirement group for a system, subsystem, or feature.

Files follow the standard sequential numbering rule: `001-requirement-name.md`, `002-…`, etc.

Use `Draft` status for new requirements; update to `Active` once reviewed and baselined. If a requirement is obsoleted, update the status to `Obsolete` and note the reason — do not delete the file.


## Research Documents

Research and evaluation notes live in `docs/research/`. Each file covers the investigation of one
topic, component, or approach — what was found and what it implies, not a decision. When research
leads to a decision, record the decision as an ADR under `docs/adr/` and reference the research
document; when it leads to a build, record the design under `docs/hldd/`.

Files follow the standard sequential numbering rule: `001-topic-name.md`, `002-…`, etc.

Use `Draft` status while research is ongoing; update to `Active` once the findings are reviewed. If
research is superseded by later findings, update the status to `Obsolete` and reference the newer
document — do not delete the file.


## Roadmap — Planned Features

Planned and future features are tracked in `docs/roadmap/`. Each entry is a lightweight document describing what is planned and why — not a full design. Use `docs/hldd/` for detailed high-level design once work is underway.

Files follow the standard sequential numbering rule: `001-feature-name.md`, `002-…`, etc.

Roadmap documents use `Draft` status until the feature ships, then update to `Active`. If a planned feature is cancelled, update the status to `Cancelled` and note the reason — do not delete the file.