# Eligibility and ranking (Issue #20)

`src/eligibility.py` decides whether a permit may use a parking group at a
time. `src/ranking.py` turns predicted availability into a first choice and a
distinct backup. Both are plain functions so the FastAPI endpoint (#19) can
call them; no prediction or ranking logic belongs in endpoint handlers.

```bash
python -m pytest tests/test_eligibility.py tests/test_ranking.py -q
```

## Calling it from the backend

```python
from src.location_registry import load_registry, current_groups
from src.ranking import recommend

locations = load_registry()                    # config/locations.json
groups = current_groups(locations, records)    # latest-quarter parking groups
groups["estimated_available_fraction"] = ...   # Vivaan's predictor, 0-1 or NaN
groups["estimate_basis"] = ...                 # optional, e.g. fallback level
result = recommend(groups, locations, permit="S", arrival=arrival,
                   destination={"latitude": 32.881, "longitude": -117.238},
                   departure=None)
result.to_api()   # status, first_choice, backup_choice, explanation, limitations
```

`to_api()` choices match `src.api.schemas.ParkingChoice`. The result also keeps
`parking_group`, `score`, `estimate_basis`, `allowed_until` and `counts`
(why candidates were skipped) for the website and debugging.

Result `status`:

| Status | Meaning |
| --- | --- |
| `ready` | First choice found; `backup_choice` may be null if only one location qualifies. |
| `no_suitable_location` | Evaluation found nothing eligible within the walking limit. Not proof parking is full. |
| `predictions_unavailable` | Eligible parking exists but none has an estimate. **Proposed addition** to the API status list; needs Daira's agreement. |

## Permit rules

Source: the team's *UCSD Parking Domain Research v1.2* (Oct 11, 2026), rules
checked 2026-10-28. Official pages it cites: permits
<https://transportation.ucsd.edu/commute/permits/index.html>, Fall 2026 notices
<https://transportation.ucsd.edu/contact/news.html>, visitor parking
<https://transportation.ucsd.edu/visit/parking.html>, citation guidance
<https://transportation.ucsd.edu/contact/citations/avoiding.html>. Recheck those
pages before relying on the rules.

Permit codes: `A`, `B`, `S`, `SR`, `D`, `V` (V = pay-station visitor permit).

| Permit | Any time | 4 PM–8 AM weekdays, all weekend | Other |
| --- | --- | --- | --- |
| A | A, B, S, D\*; posted A 24/7 | — | |
| B | B, S, D\* | A | |
| S | S, D\* | A, B | |
| SR | SR, S, D\* | A, B | |
| D | D | A, B, S | |
| V | Visitor, D\* | B, S until 7:30 AM | A 5 PM–7:30 AM every day (no all-day weekend access) |

\* Published privilege, but returned as `needs_verification` (see D stalls below).
Pairs not listed (for example S in SR stalls) are `not_allowed`.

Each check returns `allowed`, `not_allowed` or `needs_verification`. Only
`allowed` is ever recommended. Conservative choices:

- **D stalls** for any non-D permit: `needs_verification`. The Sept 18, 2026
  notice restricts D parking and its effect on other permits is unresolved (C1).
- **Specialized stalls** (reserved, accessible, carpool, EV, SuperSaver,
  motorcycle, UC vehicle, patient, Preuss, SIO, oversized and similar):
  always `needs_verification`.
- **Posted A 24/7 stalls:** A permits only.
- **Time-limited stalls** (`2 Hours`, `5 Min`, ...): `needs_verification`
  without a departure time; with one, allowed only if the stay fits the limit.
- **University holidays 2026-27** (Nov 11, Nov 26-27, Dec 24-25, Dec 31,
  Jan 1): fees are waived but category rules are unconfirmed, so any result that
  would differ between weekday and weekend rules is `needs_verification`.
- **Gliderport P386:** overnight parking is banned but the boundary is not
  published; outside the 6 AM-6 PM (Nov-Mar) / 6 AM-8 PM (Apr-Oct) daylight
  window it is `needs_verification`.
- **Lot-wide supplemental permits** (SIO, Preuss, Medical Center, International
  Center, Sanford): the registry marks these `restricted`, so they are never
  candidates.
- With a `departure`, the whole stay is checked every 15 minutes (elapsed time,
  so DST changes are handled). Without one, only arrival is checked and a
  limitation says so.

Not modeled: OPH, NW, CPP, SuperSaver, AMYRV, M, OB and other special permits;
accessible placards; carpool registration; ParkMobile V (C7); posted closures.

## Ranking

1. **Candidates:** parking groups observed in the latest surveyed quarter
   (`current_groups`). Older groups (e.g. 2018 level-by-level splits) may not
   match today's allocation.
2. **Filter:** registry status `supported`, eligibility `allowed`, walk at most
   20 minutes, and an availability estimate present. Skipped counts are in
   `result.counts`; missing estimates are never filled in.
3. **Walking time:** straight-line distance × 13 min/km + 2 min, minimum
   3 min — the website's formula. It is an approximation, not a routed path.
   Unknown when the destination has no coordinates. Pins marked approximate
   (Gliderport) are labeled in the explanation.
4. **Score** (0-1), same weights as the website:
   `0.65 × availability + 0.35 × walk score`, where walk score is
   `(20 − minutes) / 20` clipped to 0-1. With no destination, availability alone
   is the score. If only some candidates have walking times, unknown walks
   score 0.
5. **One group per location:** the location's best-scoring eligible group
   represents it. First choice and backup are always different locations.
6. **Ties:** higher score, then higher availability, then shorter walk, then
   `location_id` alphabetically, so results are deterministic.

Explanations stay under the API's 200-character limit and name the permitted
stall type and cutoff (e.g. "valid in B stalls until Wed 8:00 AM"). Choices at
or below 10% expected availability say "Often nearly full."

## Limitations

- Estimates come from historical surveys at four times a day, mostly the start
  of each quarter; they are not live availability.
- Permit rules are simplified from official pages and can be overridden by
  posted signs, closures and events.
- Weights (65/35) and the 20-minute limit are product choices carried over
  from the prototype, not tuned against user data.
