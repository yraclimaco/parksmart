# Additional-data assessment — Issue #27

Checked November 10, 2026. No additional observations enter training or
evaluation in this issue. The working historical prediction interface remains
independent of these sources.

## Findings and recommendation

Prioritize a reviewed, timestamped history from Hanrong's collector for future
evaluation. The status response covers fewer locations than QPASS, but could
eventually cover later-quarter dates and more times of day. Its missing source
measurement times and unresolved category/scope definitions currently prevent a
training merge or an accuracy claim. Keep the existing QPASS pipeline; the
checked archive contains no new eligible workbook missing locally. Occupancy
reports remain useful historical context.

| Source | Coverage and dates | Categories and access | Appropriate use now |
| --- | --- | --- | --- |
| [UCSD QPASS archive](https://rmp-wapps.ucsd.edu/TS/Survey/QPASS/Contents.html) | Links span Summer 2018–2019 through Fall 2026–2027, with entire intervening years missing. Sixteen workbook links; the fifteen locally present files cover every nonexcluded link. | Public Excel downloads; original facility/category/subtype/level and survey date/time remain authoritative. No login required for checked index. The archive does not state a publication schedule or reuse license. | Existing training and chronological evaluation after the normal quality/capacity checks. A newly published workbook can support later evaluation only when its real survey dates are verified. |
| [Candidate parking-status endpoint](https://b2waxbcovi.execute-api.us-west-2.amazonaws.com/prod/parking/v1.1/status) | One successful read at `2026-11-10T08:24:24Z`: seven structures, 45 location/category combinations. No source observation or response-generation timestamp in the decoded payload. Historical coverage is unverified. | Nine distinct reported categories; Indect and Park Assist providers. Anonymous GET succeeded; ownership, reuse permission, update interval, rate limit and history access remain unverified. | Source-count schema and mapping assessment only. Potential separate status display and later evaluation once freshness and measurement semantics are established. |
| [UCSD quarterly occupancy archive](https://rmp-wapps.ucsd.edu/TS/Survey/Survey%20of%20Parking%20Space%20Occupancy%20Levels/Quarterly%20Tables/Contents.html) | Archive spans 2000–2001 through Summer 2026–2027, with gaps; Summer 2025–2026 is absent. Quarterly labels describe report periods, not individual measurement dates. | Public Excel/PDF reports contain category and facility summaries; these scopes need a crosswalk before comparison with exact QPASS groups. No authentication required for checked index; no verified machine-access cadence or reuse license. | Historical context and possible aggregate sanity checks after scope matching. No invented dated targets and no same-quarter summary features with unknown publication cutoffs. |

The team-excluded `QPASS 2025-2026-3 Winter.xlsm` is the only linked QPASS file
not present locally. Its continued publication does not reverse the exclusion.
No workbook was downloaded, modified or added during this assessment. Local
pipeline dates and counts remain those described in the experiment report.

UCSD's [parking-availability page](https://transportation.ucsd.edu/commute/permits/availability.html)
also advertises staff updates during the first two weeks of Fall 2026, with
day-specific and summary Google Sheets. The checked published-sheet view exposed
only its title. Those links are not evidence of a new independently measured
dataset; overlap with the QPASS workbooks must be checked before ingestion.

## Status response: concrete scope review

The response is an object containing `statusCode` and a JSON string in `body`.
Decoding `body` produces location records with `LocationId`, `LocationName`,
`LocationContext`, `LocationProvider`, `Availability`, `neighborhood` and
`isStructure`. Each reported category has `Total` and `Open`. The inspected
payload does not contain garage levels, per-stall observations, survey dates,
measurement timestamps or a history range. The retrieval timestamp above records
when this assessment obtained the response; it is **not** an observation time.
No repeated collection was started and no raw snapshot was committed.

| Source location | Provider | Reported categories | Candidate registry mapping |
| --- | --- | --- | --- |
| Athena | Indect | A, B, EV, Accessible, PV | `athena-ps` |
| First Ave | Indect | A, B, EV, Accessible, PV | No registry entry; source context is Hillcrest Medical, outside the current La Jolla scope |
| Gilman | Indect | A, B, EV, Accessible, V | `gilman-ps` |
| Hopkins | Indect | A, B, EV, Accessible, V, PV, SR, 2P Carpool | `hopkins-ps` |
| Scholars | Park Assist | A, B, EV, Accessible, V, SR, M | `scholars-ps` |
| South | Park Assist | A, B, EV, Accessible, V, SR, M, 2P Carpool | `south-ps` |
| Theatre District | Indect | A, B, EV, Accessible, V, SR, 2P Carpool | `theatre-district-ps` |

These six candidate name matches are proposals, not verified source-to-model
group mappings. A structure-level category count cannot be apportioned among
QPASS levels or restricted subtypes. Preserve source IDs, names and providers,
and verify what the sensor inventory includes and whether categories overlap.
`PV` and `V` must stay separate; so must EV, Accessible, SR, M and 2P Carpool.
The response contains no S or D category: that absence does not mean zero spaces.
Neither sensor counts nor category names establish permit eligibility.

## Hanrong's collected dataset: review status

The requested multi-snapshot dataset was **not available in the sources checked**:
the local data/results file inventory, merged `main` at `3642c19`, the fetched
`mobile-app-prototype` branch file inventory, recent repository PRs,
[Issue #28](https://github.com/yraclimaco/parksmart/issues/28) and its empty comment
thread, or accessible ParkSmart Drive search results. The November 3
[team meeting log](https://docs.google.com/document/d/1wZesLWbl_2SnTGlMqyJkPByI1GpoCLsQ5aSPdQzS4_I/edit)
assigns collection and validation work but supplies no snapshot-history link.
The user confirmed on November 10 that Hanrong has not collected this dataset
yet. Its review is therefore a pending teammate dependency.

The direct endpoint inspection above reviews a single current response, **not
Hanrong's historical dataset**. Date range, sample count, collection gaps,
duplicate responses, count validity over time, provider changes and update
cadence therefore remain unassessed. This external handoff is still needed; it
does not block artifact loading or the experiments.

When the dataset is shared, the review should establish:

1. Raw-response provenance, collector version and actual UTC retrieval times.
   Preserve any source measurement timestamp separately; leave it null when
   absent. A collector file timestamp or HTTP response date is not a measurement
   timestamp.
2. Real history range, unique retrievals, interval/gap distribution, repeated
   payloads, location/category additions and changes to comparable capacities.
   Repeated unchanged snapshots are not independent accuracy evidence.
3. Nonnegative whole counts, `Open <= Total` for comparable counts, invalid-row
   retention and flags, absent categories versus zero counts, and failed requests
   excluded from valid observations. Never clip invalid source counts.
4. Evidence for exact source-to-registry and source-category/subtype/level scope,
   reviewed with Hanrong and Daira. Exclude Hillcrest from La Jolla recommendations
   unless scope is explicitly expanded; do not silently extend the registry.
5. Provider documentation or confirmation of measurement/update semantics,
   freshness, permitted use and polling limits. There is no verified polling
   interval from the current response alone.
6. A separate chronological evaluation plan using genuinely dated, compatible
   observations. Do not reuse the already inspected QPASS holdout for selection
   or advertise an accuracy result against snapshots with unknown measurement
   times. A future sensor-only model may need its own target and support policy.

Keep any collected originals and normalized status table in a distinct,
gitignored status namespace under the collector's documented contract. Do not
append them to `analysis_dataset.csv` or retrain the approved artifact as part of
collection. [The backend proposal](parking_status.md) already separates source
counts, retrieval times, missing observation times, mapping/freshness limitations
and unavailable-feed behavior from historical predictions.

## Occupancy-report boundary

The previously inspected Fall 2025–2026 occupancy workbook and historical campus
PDF contain aggregate hourly/category summaries and some blank Date cells; see
[Issue #18's source assessment](issue18_predictions.md#occupancy-report-assessment)
for the workbook-specific evidence. This issue rechecked the archive's coverage;
it did not turn those summaries into new dated surveys. Even aggregate checks
need matched location scope, parking restrictions, survey period, hour and
denominator. Historical numeric location codes still need a reviewed crosswalk.

Quarterly summaries may include validation observations, and no verified as-of
publication cutoff has been established. They are unsuitable as prediction
features in this experiment. Request original dated readings or a documented
publication history before attempting a separate future training ablation.
