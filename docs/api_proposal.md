# Proposed API format — for Dylan and Hanrong

**Proposed contract; Hanrong's confirmation is pending.**

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
