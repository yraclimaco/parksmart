# UCSD published construction notices — Issue #35

Inspected the public, official [Construction Alert Approved map service](https://admin-enterprise-gis.ucsd.edu/server/rest/services/Construction/Construction_Alert_Approved/MapServer?f=pjson)
on November 13, 2026 using read-only HTTPS GET requests. No account, token,
paid service or AWS resource was needed. The service metadata has no published
update-frequency commitment, rate-limit policy, descriptive coverage statement
or copyright text; public access is not evidence of unlimited permitted use or
complete current campus coverage. A later inspection request was disconnected,
so successful access is not guaranteed.

On November 14, a bounded live check still retrieved service metadata, but both
a minimal one-object-ID feature query without geometry and the provider's full
WGS84 geometry query timed out within four seconds. Both urllib and HTTPX feature
requests failed; no proxy environment settings or detected system proxy were
present. This does not establish whether source-query slowness or access/rate
behavior caused the failure. Fresh geometry retrieval was not confirmed in that
check; the provider must report unavailable or explicitly stale data, preserving
its bounded deadlines. No TLS verification or security settings were changed.

## Actual source contract

| Layer | Source geometry | Records at inspection |
| --- | --- | ---: |
| [0: Alert Point](https://admin-enterprise-gis.ucsd.edu/server/rest/services/Construction/Construction_Alert_Approved/MapServer/0?f=pjson) | `esriGeometryPoint` | 33 |
| [1: Alert Line](https://admin-enterprise-gis.ucsd.edu/server/rest/services/Construction/Construction_Alert_Approved/MapServer/1?f=pjson) | `esriGeometryPolyline` | 9 |
| [2: Alert Poly](https://admin-enterprise-gis.ucsd.edu/server/rest/services/Construction/Construction_Alert_Approved/MapServer/2?f=pjson) | `esriGeometryPolygon` | 13 |

The 55 geometry records are not 55 independent notices: `AlertID` repeats across
features and layers. Layer 3 is an alert-report table; layers 4 and 5 are layout
and map-text presentation features. The provider uses layers 0–2 and skips their
`AlertType: Text` map-label markers (11 of the inspected point records).

Queried fields are `objectid`, `AlertID`, `AlertType`, `Comment`, `Status`,
`Project_Alert_Status`, `Subject`, `Project_Name`, `Alert_Start_Date`,
`Alert_End_Date`, `Public_Impact_Date`, `Public_Impact_End_Date` and
`Public_URL_Link_To_Map`. It does not request manager/contact fields. All 55
inspected records had `Status: Approved` and `Project_Alert_Status: APPROVED`.
Types included parking/road/access markers, pedestrian/vehicle lines,
construction sites and possible impact areas. These are the source's published
map descriptions, not ParkSmart verification of a whole-lot closure.

The metadata declares `dateFieldsTimeReference.timeZoneIANA:
America/Los_Angeles`, daylight-saving support and `datesInUnknownTimezone: false`.
Dates are UTC epoch milliseconds; inspected date values corresponded to local
midnight. Alert dates spanned August 11, 2025 through January 1, 2033; public
impact dates spanned August 25, 2025 through January 1, 2033. There were no missing
date values in this snapshot, but future records are not assumed complete.
These are project schedules; retrieval time is not an observation or work time.

The native coordinate reference is `wkid: 102646`, `latestWkid: 2230` (State Plane,
not Web Mercator). The query requests `outSR=4326`; live point, line and polygon
responses each reported WGS84 `wkid/latestWkid: 4326` with longitude/latitude
coordinates. The provider rejects native/unknown response reference systems
rather than applying an unverified projection.

Each layer advertises `maxRecordCount: 2000`, `supportsPagination: true` and
`supportsOrderBy: true`. A live `resultRecordCount=1`, `resultOffset=0/1`,
`orderByFields=objectid ASC` check returned distinct object IDs and
`exceededTransferLimit: true`. Full-layer inspection returned 33/9/13 records
without a transfer limit. Runtime pages use 500 records, explicit offsets and
ascending object IDs. Repeated IDs, empty continuing pages, malformed responses,
provider errors, more than four pages per layer or 2,000 total features fail the
refresh; incomplete pages never become a fresh empty result.

## Relevance and limitations

The provider caches complete raw features for ten minutes and rechecks each
request's aware arrival and verified/requested parking/destination coordinates.
Every source refresh shares a four-second transport budget across all layers
and pages. The shared cache backs off failed refreshes for 30 seconds and may
return an explicitly stale snapshot only while its total age is under 24 hours.
Failed attempts retain the last successful retrieval timestamp.

Only explicitly approved/active statuses are eligible. An inactive/cancelled/
completed status or a nonmatching date window is excluded. The complete public
impact date pair is preferred. If unavailable, a complete alert-date pair may
be used with a broader-timing limitation and partial status; endpoints from
different pairs are never mixed. A local-midnight end is conservatively included
through that Los Angeles calendar date, ending at the following local midnight
across daylight-saving changes. This does not establish exact working hours.

Point and line distances use a local campus approximation; polygon membership
uses the actual rings, including holes and disjoint shells. A trip point must
intersect the feature or be within 200 metres of it. This buffer is an advisory
matching choice, not a documented impact radius or route distance. Free-text
names are never geocoded or fuzzily matched. Missing or unsupported geometry,
unknown status or unusable dates that may matter produce partial coverage;
source failure produces unavailable/stale status rather than “no construction.”

Matching features are grouped by exact `AlertID` and list the matched trip
points. `intersects_geometry` means at least one listed point intersects; others
may only be nearby. Alerts say “Published construction notice” and retain source
type wording as plain text, removing HTML tags and script/style content. Long
excerpts are limited to the shared 600-character message bound with an explicit
shortening limitation. They do not modify recommendations, permit eligibility, estimated
availability, routes or avoidance instructions.

`Public_URL_Link_To_Map` is preferred only for HTTPS links on `ucsd.edu` or a
subdomain without embedded credentials. It was missing on 38 of 55 inspected
features. When absent/invalid, the alert links to the official feature query;
internal `URL_Link_To_Map` dashboards are not substituted. No linked page is
fetched as part of a trip request. No source-updated timestamp is invented.

Offline tests use synthetic examples of this schema and no real source calls:

```bash
python -m pytest tests/test_construction_alerts.py -q
```
