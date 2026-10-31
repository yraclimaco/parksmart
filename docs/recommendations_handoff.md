# Handoff: wiring `POST /recommendations` (Issue #20 → Daira)

**Short version:** the ranking code is done and tested. Your endpoint needs to
do four things: load data once, attach predictions, call `recommend()`, and
return its output. About 30 lines. Everything below has been run against the
real dataset, and the response passes `RecommendationResponse`.

## The four steps

| Step | What you call | When |
| --- | --- | --- |
| 1. Load | `load_registry()`, `load_analysis_dataset()`, `HistoricalAverage().fit(...)` | Once, at startup |
| 2. Candidates | `current_groups(locations, records)` | Once, at startup |
| 3. Predict | `model.predict(...)` for the requested time | Every request |
| 4. Rank | `recommend(...)` then `.to_api()` | Every request |

## Copy-paste sketch

```python
from fastapi import HTTPException

from src.location_registry import current_groups, load_registry
from src.parking_benchmarks import HistoricalAverage, load_analysis_dataset
from src.ranking import recommend
from .schemas import RecommendationRequest, RecommendationResponse

# --- Step 1 and 2: once at startup ---
RECORDS = load_analysis_dataset()            # data/processed/pipeline/analysis_dataset.csv
MODEL = HistoricalAverage().fit(RECORDS)
LOCATIONS = load_registry()                  # config/locations.json
CANDIDATES = current_groups(LOCATIONS, RECORDS)

SURVEY_TIMES = ["08:00", "10:00", "12:00", "14:00"]   # the only times in the data


def nearest_survey_time(arrival):
    """Snap an arrival to the closest survey time (see open question 2)."""
    minutes = arrival.hour * 60 + arrival.minute
    return min(SURVEY_TIMES,
               key=lambda t: abs(int(t[:2]) * 60 + int(t[3:]) - minutes))


@app.post("/recommendations", response_model=RecommendationResponse)
def recommendations(request: RecommendationRequest) -> RecommendationResponse:
    arrival = request.arrival_time           # already UCSD local time

    # --- Step 3: predict for this request ---
    groups = CANDIDATES.copy()
    features = groups.assign(
        weekday=arrival.strftime("%A"),
        observation_time=nearest_survey_time(arrival),
        quarter="Fall",                      # see open question 3
    )
    prediction = MODEL.predict(features)
    groups["estimated_available_fraction"] = prediction["prediction"]
    groups["estimate_basis"] = prediction["baseline_group"]

    # --- Step 4: rank ---
    coords = request.destination.coordinates
    try:
        result = recommend(
            groups, LOCATIONS,
            permit=request.permit_type,
            arrival=arrival,
            destination=coords.model_dump() if coords else None,
        )
    except ValueError as error:              # unknown permit, bad times
        raise HTTPException(status_code=422, detail=str(error))

    return RecommendationResponse(
        **result.to_api(), is_example=False, arrival_time=arrival,
    )
```

`result.to_api()` returns exactly these keys: `status`, `first_choice`,
`backup_choice`, `explanation`, `limitations`. You only add `is_example` and
`arrival_time`.

## What comes back

| `status` | Meaning | Choices |
| --- | --- | --- |
| `ready` | Found a first choice | `first_choice` set; `backup_choice` can be null if only one place qualifies |
| `no_suitable_location` | Nothing eligible within a 20 min walk | Both null. Does **not** mean parking is full |
| `predictions_unavailable` | Eligible parking exists, but none has an estimate | Both null. **Not in the schema yet**, see open question 1 |

Example (`S` permit, Geisel, Tue 2026-11-03 9:00 AM):

```text
ready
first:  Torrey Pines Center North Parking Structure
        "S permit valid in S stalls. Past surveys: about 90% open. About 18 min walk."
backup: Pangea Parking Structure
```

## Things handled for you

- **Permit rules**: only `allowed` parking is ever recommended. Unknown or
  conflicting rules count as not allowed (`src/eligibility.py`).
- **Unsupported locations**: `unresolved`, `restricted` and `excluded` registry
  entries are skipped.
- **Coordinates**: only verified pins go out; everything else is `null`.
- **Missing destination coordinates**: ranking falls back to availability only.
- **Limitations text**: estimate and walking caveats are always included.

## Open questions (need a decision)

1. **`predictions_unavailable` status (Daira).** `schemas.py` only allows
   `ready`, `no_suitable_location` and `not_implemented`, so this status would
   fail validation today. Proposal: add it to the `Literal`. With today's
   `HistoricalAverage` it can't happen, because the model always falls back to
   the overall mean. A future model that returns `NaN` could trigger it.
2. **Arrival times between surveys (Daira + Vivaan).** Surveys only happen at
   08:00, 10:00, 12:00 and 14:00. If you pass the raw time (for example 09:00),
   the model silently skips its two time-aware levels and uses the group's
   all-day average. The sketch snaps to the nearest survey time (ties go
   earlier, so 09:00 uses 08:00). It matters: for the example above, raw 09:00
   gives about 63% open and snapped 08:00 gives about 90%. Times outside
   8 AM to 2 PM have no survey data at all; we could say so in `limitations`.
3. **Which quarter (Daira + Vivaan).** The sketch hardcodes `"Fall"`. It
   should come from the arrival date. Confirm with Vivaan which quarter labels
   the model expects.
4. **Global-mean fallback (Vivaan).** Groups with no history get the overall
   mean (`estimate_basis = "global"`), so they still get a number. Should
   those count as "no estimate" (`NaN`) instead?

## Test it

```bash
python -m pytest tests/test_ranking.py tests/test_eligibility.py tests/test_location_registry.py -q
python -m uvicorn src.api.main:app --reload    # then try POST /recommendations at /docs
```

The website calls this endpoint when `VITE_RECOMMENDATION_SOURCE=api` is set in
`frontend/.env.local` (see `frontend/src/api/recommendations.ts`).

More detail on scoring weights, walking estimates and permit rule sources:
`docs/recommendations.md`.
