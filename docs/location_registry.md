# Shared location registry (Issue #20)

`config/locations.json` is the single list of parking locations shared by the
backend, ranking code, website and iOS app. `src/location_registry.py` loads and
validates it. Status as of 2026-10-28: proposed; confirmation from Daira and
Hanrong pending.

```bash
python -m src.location_registry          # check against the integrated dataset
python -m pytest tests/test_location_registry.py -q
```

## IDs

- `location_id` is lowercase kebab-case and **stable**: never rename or reuse one.
  Add a new entry instead.
- Surface lots use their P-number (`p406`). Structures use the website's
  name-based IDs (`gilman-ps`); their official P-numbers are not verified.
  Facilities with no pin use their dataset label (`tdlln`, `8980`).
- They replace Daira's fixture IDs `sample-parking-a` / `sample-parking-b`.

## How predictions connect

Each location lists the standardized dataset `facility` values it covers
(`dataset_facilities`). Predictions stay keyed by facility, category, subtype
and level; the registry only adds `location_id`. `location_groups()` lists each
location's observed groups, so `Gilman` keeps `A`, `A / Level 2`,
`Visitor / 2 Hours` and so on separate. Restricted groups (Reserved, Carpool,
Accessible, EV, time-limited) are never pooled into a general location estimate.
Every dataset facility maps to exactly one location; the test suite checks this
when the dataset is built locally.

## Fields

| Field | Meaning |
| --- | --- |
| `registry_status` | `supported` (may be recommended if eligible), `restricted` (needs a supplemental permit or authorization), `unresolved` (name, location or scope unverified), `excluded` (out of scope). Only `supported` locations may be recommended. |
| `coordinates`, `coordinate_status` | `verified` (UCSD GIS, checked 2026-10-21), `approximate`, or `missing` (null). The API passes only verified coordinates. |
| `coordinate_source`, `coordinate_verified_on` | Where the pin came from and when it was checked. |
| `access_note` | Lot restriction text from Domain Research v1.2, section 4. |

Current use is not stored in the file. `location_summary()` derives
`current_use_status` from the dataset (`observed_in_latest_quarter`,
`not_in_latest_quarter`, `no_observations`) and always sets
`current_use_verified: false`: appearing in a survey does not prove a facility
is open or that its allocation is unchanged.

## Coverage

87 locations: 86 dataset facilities plus P001 (on the map, no observations).

| Group | Count |
| --- | --- |
| Supported, verified pin | 47 |
| Supported, approximate pin (Gliderport P386) | 1 |
| Restricted (SIO P001–P017, Preuss P706, Medical Center P759, International Center P416) | 16 |
| Unresolved, no coordinates | 22 |
| Excluded (Mesa Canyon, resident housing) | 1 |

Supported locations not observed in the latest quarter (Fall 2026-2027), so
their recent use is unknown: Theatre District Parking Structure (last
2025-01-17), P384 and P385 (last 2025-07-11).

## Unsupported and unresolved locations

These are kept so no observation is dropped, but are never recommended.

| location_id | Status | Readings | Last observed | Reason |
| --- | --- | ---: | --- | --- |
| `8980` | unresolved | 1079 | 2026-10-09 | Label meaning unknown (possibly an address). |
| `tdlln` | unresolved | 1144 | 2026-10-09 | Possibly related to Theatre District Garage; not merged without evidence (Issue #3). |
| `mesa-canyon` | excluded | 294 | 2026-10-09 | Graduate-housing structure serving residents. |
| `nuevo-west` | unresolved | 120 | 2019-10-11 | Housing-area label; relationship to Nuevo West/Vela unverified. |
| `nuevo-west-vela` | unresolved | 246 | 2025-01-17 | As above. |
| `p021`, `p206`, `p359`, `p506`, `p751` | unresolved | 666–1445 each | 2026-10-09 | No UCSD GIS lot outline found. |
| `p383`, `p395`, `p760` | unresolved | 422–1189 each | 2025-01-17 | No UCSD GIS lot outline found. |
| `p752` | unresolved | 20 | 2025-07-11 | No UCSD GIS lot outline found. |
| `p102`, `p103`, `p111`, `p308`, `p309`, `p405`, `p411`, `p502`, `p511` | unresolved | 261–909 each | 2019 | Observed only through 2019; not yet checked against UCSD GIS. |

## Open questions

- Official P-numbers for the parking structures.
- Whether TDLLN, 8980 and the Nuevo West labels are public parking.
- Whether Gliderport's approximate pin is acceptable for walking estimates.
- The website still has its own copy of the pins (`frontend/src/data/`); it
  should read `/locations` once Daira serves this registry.
