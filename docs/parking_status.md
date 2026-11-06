# Parking-status integration proposal — Issue #26

No collector or approved source-feed contract was found in the merged source
inspected for this issue. This document prepares the handoff to Hanrong; **no
live-count endpoint or simulated live feed is implemented**. Recommendations
continue to use historical model estimates independently.

## Interface to confirm with Hanrong

A future GET `/parking-status` should return a separate envelope; it must never
reuse `estimated_available_fraction` for source counts. Suggested fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Versioned normalized feed contract |
| `status` | `available`, `stale`, `unavailable`, or `not_configured` |
| `source` | Named source and public provenance reference, no tokens |
| `retrieved_at` | UTC-offset datetime when the collector actually obtained the snapshot |
| `response_generated_at` | Optional server response time; must not replace retrieval time |
| `limitations` | Freshness, source coverage and mapping caveats |
| `records` | Source-count records; empty on failed/unconfigured retrieval |

Each record should retain `source_location_id`, `source_category`, exact shared
`location_id`, facility/category/subtype/level when resolved, `mapping_status`,
`reported_open_spaces`, optional `reported_capacity`, and `source_observed_at`
(nullable offset datetime supplied by the source). Counts are nonnegative
integers or null; zero is a real count, not a missing-value marker. A retrieval
cannot invent a source observation timestamp. The source's category must be
mapped to a reviewed parking group, not inferred from similar names.

## Mapping and freshness rules

- Dylan's `config/locations.json` is the location ID authority. Hanrong supplies
  exact source-to-registry and source-category-to-group mappings with evidence.
- Unknown/ambiguous mappings remain flagged in audit results. Do not assign
  counts to a whole location, merge restricted groups or split counts among
  levels without source evidence.
- Agree on the source's update cadence and a maximum usable age before declaring
  anything fresh. Do not invent a freshness threshold or infer freshness from
  a successful local-file read. Include both retrieval age and observation age
  when timestamps exist; a missing observation time is an explicit limitation.
- A failed feed read is unavailable. If a retained last-known snapshot is ever
  displayed, explicitly mark stale, preserve its old timestamps, and separate it
  from any current-count field. Never update retrieved_at just because the API
  returned a cached file. Never present old counts as current after a failure.
- Source counts are not model predictions and do not establish permit
  eligibility. Feed failure must not break historical recommendations or silently
  substitute a model estimate in the count fields.
- Invalid counts (negative, noninteger, or open greater than comparable capacity)
  require flags/rejection, not clipping or invented replacements.

## Collector prerequisites for the adapter

Need the collector's module/function or saved-snapshot format, provenance,
retrieval timestamp, source timestamp semantics/timezone, failure behavior,
credentials mechanism, polling limits, reviewed mappings, and freshness policy.
No dataset, private feed snapshot or token belongs in the PR. Once ready, add a
reusable normalization/validation adapter, an independent backend endpoint and
fixtures for fresh/stale/failure/missing timestamps/unresolved mappings. Until
then, keep the web/app on historical estimates rather than adding a fake feed.
