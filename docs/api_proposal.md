# Proposed API format — for Dylan and Hanrong

**Proposed contract; Hanrong's confirmation is pending.** The current proposal
with real location IDs and statuses is the Issue #20 update at the end.

Coordination status (reported by Daira): Dylan said he is willing to make his
frontend work with the proposed format. Hanrong has not started his app yet;
this contract and the examples provide a starting point for that work. His
confirmation is pending. Neither client integration nor agreement on every field
and production ID has been verified.

The backend uses the proposed `location_id`, `name`, and `coordinates` fields
and the fixture IDs `sample-parking-a` and `sample-parking-b` now, so Hanrong
can build his app against a concrete response while providing feedback.

This week's backend exposes `GET /health` and `GET /locations`, with interactive
docs at `/docs`. `/locations` currently uses two fictional fixtures, explicitly
marked `data_status: "sample"`. Proposed IDs are `sample-parking-a` and
`sample-parking-b`; they are not production UCSD IDs. Coordinates are null.

Please review these proposed conventions:

- JSON fields use snake_case. Locations contain `location_id`, `name`, and
  `coordinates` (null or a complete `latitude`/`longitude` object).
- Recommendation input contains `destination`, `arrival_time`, `permit_type`,
  and optional `starting_location`. Destination/origin have `name` and optional
  coordinates. Permit codes and the future destination representation still
  need confirmation; no permit eligibility is implied.
- Arrival uses ISO 8601 in `America/Los_Angeles`. Prefer an explicit UTC offset.
  An omitted offset means UCSD local time; nonexistent spring times are rejected
  and ambiguous autumn times need an offset. Other explicit offsets are
  converted to UCSD time.
- Proposed output contains `first_choice`, `backup_choice`, an explanation and
  limitations. Each choice has a location, `estimated_available_fraction` (0–1
  or null), `estimated_walking_minutes` (minutes or null), and an explanation.
- Unknown means JSON null, never zero. `not_implemented` means no recommendation
  evaluation exists; `no_suitable_location` is reserved for a future evaluation
  that finds no defensible choice. Neither means all parking is full.

No recommendation endpoint, model, ranking, or verified coordinates are
available. All recommendation JSON files are labeled static examples and use
null estimates. See [examples and full contract](backend.md).

Record agreed changes to field names, permit values, units, or time/null handling
here. Real location IDs and facility/level details need review before replacing
the sample catalog. The current proposal can be used for interface development
while feedback is pending.

## Issue #20 update (Dylan, 2026-10-31): proposed shared interface

Proposed, not yet confirmed by Daira, Vivaan and Hanrong. Everything below is
implemented and tested on `feature/recommendations` (PR #21).

**Location IDs.** Use the registry IDs in `config/locations.json` (for example
`gilman-ps`, `p406`) everywhere: `/locations`, recommendation results, website
and app map markers. IDs never change or get reused. To build the catalog:

```python
from src.location_registry import api_locations, load_registry

api_locations(load_registry())   # [{location_id, name, coordinates}], verified pins only
```

The registry also says which locations may be recommended (`registry_status`:
`supported`, `restricted`, `unresolved`, `excluded`); see
`docs/location_registry.md`. Hanrong can build the app against this list now.

**Permit codes.** `A`, `B`, `S`, `SR`, `D`, `V` (pay-station visitor). Any other
value is rejected with 422.

**Statuses.** `ready`, `no_suitable_location`, `predictions_unavailable`
(eligible parking exists but has no estimate) and `not_implemented`. Only
`ready` has choices. None of them means parking is full. The schema accepts all
four and a test keeps ranking, schema and website in sync.

**Request fields.** Eligibility checks `arrival_time` only (there is no
departure field yet). `destination.coordinates` drives straight-line walking
estimates. `starting_location` is accepted but unused (no routing).

**Predictions (for Vivaan).** `src/availability.AvailabilityEstimator` takes any
model with `predict(features)` returning `prediction` (0–1, or NaN when
unsupported) and `baseline_group` (a basis label). It picks the survey time and
quarter for the arrival and labels estimates that use another survey time or a
fallback. A model loaded from a saved artifact plugs in with
`AvailabilityEstimator(model, survey_times=[...])`; the default is today's
`HistoricalAverage`. NaN predictions become `predictions_unavailable`, never a
substituted estimate. Full contract: module docstring of `src/availability.py`.

**Endpoint (for Daira).** `Recommender.from_files()` once at startup, then
`.recommend(permit, arrival, destination)` per request. Copy-paste sketch, CORS
change and `/locations` swap: `docs/recommendations_handoff.md`. Try real output
with `python -m src.recommender --permit S --arrival 2026-11-03T09:00`.
