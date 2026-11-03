# Handoff: wiring `POST /recommendations` (Issue #20 → Daira)

**Short version:** the recommendation code is done and tested.
`src.recommender.Recommender` loads everything once at startup; your endpoint
calls `recommend()` and returns `to_api()`. About 15 lines, plus a one-word
CORS change. The sketch below has been run as a real FastAPI endpoint on the
real dataset, and its responses pass `RecommendationResponse`.

To see real output before touching the API:

```bash
python -m src.recommender --permit S --arrival 2026-11-03T09:00 --lat 32.8811 --lon -117.2376
```

## What you need to change

| # | Change | Where |
| --- | --- | --- |
| 1 | Add the `POST /recommendations` endpoint (sketch below) | `src/api/main.py` |
| 2 | Allow browser POSTs: `allow_methods=["GET", "POST"]` | `CORSMiddleware` in `src/api/main.py` |
| 3 | Serve the shared registry from `/locations` instead of the sample catalog | `src/api/locations.py` |

Without step 2 the website's request fails before reaching the endpoint: the
browser's preflight currently gets `400 Disallowed CORS method`.

## Copy-paste sketch

```python
from fastapi import HTTPException

from src.recommender import Recommender
from .schemas import RecommendationRequest, RecommendationResponse

# Once at startup (about 1 s): dataset, registry, estimator, current groups.
RECOMMENDER = Recommender.from_files()


@app.post("/recommendations", response_model=RecommendationResponse)
def recommendations(request: RecommendationRequest) -> RecommendationResponse:
    coords = request.destination.coordinates
    try:
        result = RECOMMENDER.recommend(           # about 4 ms per request
            request.permit_type,
            request.arrival_time,
            destination=coords.model_dump() if coords else None,
        )
    except ValueError as error:                   # unknown permit, bad times
        raise HTTPException(status_code=422, detail=str(error))
    return RecommendationResponse(
        **result.to_api(), is_example=False, arrival_time=request.arrival_time,
    )
```

**Missing data.** If `data/processed/pipeline/analysis_dataset.csv` doesn't
exist, `Recommender.from_files()` raises `FileNotFoundError` naming the build
commands. Let it stop startup, or catch it, keep `RECOMMENDER = None`, and
return HTTP 503 from the endpoint so `/health` and `/locations` still work.

`result.to_api()` returns exactly `status`, `first_choice`, `backup_choice`,
`explanation` and `limitations`. You only add `is_example` and `arrival_time`.

## What comes back

| `status` | Meaning | Choices |
| --- | --- | --- |
| `ready` | Found a first choice | `first_choice` set; `backup_choice` can be null if only one place qualifies |
| `no_suitable_location` | Nothing eligible within a 20 min walk | Both null. Does **not** mean parking is full |
| `predictions_unavailable` | Eligible parking exists, but none has an estimate | Both null. Not proof parking is full |

All three are accepted by `RecommendationResponse` and the website.
`tests/test_ranking.py::test_every_ranking_status_is_accepted_by_backend_and_website`
fails if the ranking, the schema and `frontend/src/api/recommendations.ts`
ever disagree. With today's baseline, `predictions_unavailable` can't happen
(the model always has a fallback), but a future model that returns `NaN` can
trigger it.

Example (`S` permit, Geisel, Tue 2026-11-03 9:00 AM):

```text
ready
first:  Torrey Pines Center North Parking Structure
        "S permit valid in S stalls. Past surveys: about 90% open (8:00 AM surveys). About 18 min walk."
backup: Pangea Parking Structure
```

## How estimates are labeled

Surveys only happen at 8:00 AM, 10:00 AM, 12:00 PM and 2:00 PM on weekdays near
the start of each quarter. `AvailabilityEstimator.attach` uses the nearest
survey time (ties go earlier) and the quarter from the official 2026-27
calendar, then keeps each estimate's basis. When an estimate isn't a full
match for the request, the choice's explanation says so in parentheses and
`limitations` gets a line such as:

```text
First choice estimate is limited: 2:00 PM surveys; none cover 10:00 PM.
```

| Basis (`estimate_basis`) | Label |
| --- | --- |
| `level_1`: same stalls, weekday, survey time, quarter | none if the survey time equals the arrival time, else e.g. "8:00 AM surveys" |
| `level_2`: same stalls and survey time | "same time, any weekday or quarter" |
| `level_3`: same stalls, any time | "all-day average for these stalls" |
| `global`: no history for these stalls | "campus-wide average; no history for these stalls" |

Arrivals outside 8 AM to 2 PM also get "none cover <time>". The full basis is
kept on each `Choice` (`estimate_basis`, `estimate_survey_time`,
`estimate_note`) if you want to expose it later.

**Swapping in Vivaan's model (#18).** Only the startup line changes:

```python
from src.availability import AvailabilityEstimator

estimator = AvailabilityEstimator(
    vivaans_model,                                   # loaded from his artifact
    survey_times=["08:00", "10:00", "12:00", "14:00"],
    basis_descriptions={...},                        # labels for his basis values
)
RECOMMENDER = Recommender.from_files(estimator=estimator)
```

His model needs `predict(features)` returning `prediction` (0–1, or NaN when
unsupported) and `baseline_group`. NaN rows are never filled in; if nothing
eligible has an estimate, the result is `predictions_unavailable`. If the
estimator was never fitted or given survey times, `attach` raises a clear
`ValueError` naming what is missing, instead of a confusing error.

## Request fields: what's used

| Field | Used? | Notes |
| --- | --- | --- |
| `destination.coordinates` | Yes | Straight-line walking estimate from each lot. Null means availability alone decides, and a limitation says so |
| `destination.name` | No | Display only |
| `arrival_time` | Yes | Eligibility, survey time, quarter, holidays |
| `permit_type` | Yes | `A`, `B`, `S`, `SR`, `D` or `V` (pay-station visitor). Anything else returns 422 |
| `starting_location` | **No** | Not used yet. There is no routing; walking is lot → destination only |

**Eligibility checks arrival only.** The request has no departure time, so
permit rules are checked at the arrival moment, and `limitations` always says
"Permit rules were checked at arrival only; they can change during your stay."
`recommend()` already accepts `departure=` and then checks every rule boundary
during the stay. If we add a `departure_time` field later, pass it through.

**Dates.** Holidays and quarters are verified for Sep 21, 2026 to
Sep 6, 2027 (`src/ucsd_calendar.py`). Requests outside that range still get
results, with a limitation saying the date wasn't checked.

## Serving the registry from `/locations`

The sample catalog's fictional IDs won't match recommendation IDs or the
website's map pins. The registry already has a converter:

```python
from src.location_registry import api_locations, load_registry

locations = api_locations(load_registry())   # [{location_id, name, coordinates}, ...]
```

Only verified pins are passed; everything else has `coordinates: null`, as the
schema requires. These are real registry IDs, so `data_status` can become
`"verified"`, but the registry also lists `restricted`, `unresolved` and
`excluded` locations. Either filter to `registry_status == "supported"` or keep
all and add a limitation saying only supported locations are recommended. Your
call.

## Things handled for you

- **Permit rules**: only `allowed` parking is recommended. Unknown or
  conflicting rules return `needs_verification` and are never recommended
  (`src/eligibility.py`).
- **Unsupported locations**: `unresolved`, `restricted` and `excluded` registry
  entries are skipped.
- **Coordinates**: only verified pins go out.
- **Explanations** stay within the schema's 200-character limit.

## Still open

- **Global fallback (Vivaan).** Groups with no history get the campus-wide
  mean, clearly labeled. Should they be treated as no estimate (`NaN`, which
  leads to `predictions_unavailable`) instead?

## Test it

```bash
python -m pytest tests/test_recommender.py tests/test_ranking.py tests/test_eligibility.py tests/test_availability.py tests/test_ucsd_calendar.py tests/test_location_registry.py -q
python -m uvicorn src.api.main:app --reload    # then try POST /recommendations at /docs
```

The website calls this endpoint when `VITE_RECOMMENDATION_SOURCE=api` is set in
`frontend/.env.local` (see `frontend/src/api/recommendations.ts`).

More detail on scoring weights, walking estimates and permit rule sources:
`docs/recommendations.md`.
