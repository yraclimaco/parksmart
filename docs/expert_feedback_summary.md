# Domain expert feedback: what we addressed

Meeting: Fri 2026-11-06 with Ellen Schwartz (UCLA Center for Parking Policy) and
Jonathan Wicks (Walker Consultants). This lists the advice that shaped the
website and backend for Issue #32, and what we chose not to build.

## Addressed

| Advice | What changed |
| --- | --- |
| Make walking distance prominent ("emphasize walk") | Walk time is shown large, with a footprints icon, at the top of each result card. |
| Color-code availability; colors read faster than text | Green 20–100% open, yellow 10–20%, red under 10%, on cards, bars and map pins. Each color also has a text label ("Usually open", "Usually tight", "Usually full"), worded as past-survey patterns, not live availability. |
| Say availability comes from historical patterns | Cards read "Based on historical patterns for 10:00 AM"; the page footer and every result list say these are historical estimates, not live availability. |
| Let users trade walking against availability | The shared backend accepts `preference` (shorter walk, balanced, more space) and `max_walk_minutes` on `POST /recommendations`, so the website and the iOS app can share the same behavior. The website planner later dropped these controls: every search there uses balanced with the default 20-minute walk limit, because a saved short limit made searches return no results. |
| Explain why a pick ranks where it does | Each ranked location carries a `fit_reason`, for example "16 min walk (mapped path); 53% open in past surveys. Ranks below Pangea Parking Structure: 7 min longer walk, though more space (53% vs 9% open)". |
| Show weather and construction near the trip | `POST /trip-alerts` returns Open-Meteo forecasts and published UCSD construction notices for the chosen lot and destination; the website shows them inside the result card. They are information only and never change eligibility, estimates or ranking (Issue #35). |
| Do not mistake an estimate for a guarantee | Percentages are described as the share of spaces open in past surveys, never as a chance of finding a space. |

## Not building for the final version

| Advice | Why not |
| --- | --- |
| Visitor and daily-pay pricing | Out of scope for this release. Permit V stays selectable. |
| Photos of structure entrances | Out of scope for this release. |
| Which levels are open for which permit | Not reliably recoverable from the data we have. |
| Live occupancy (dynamic signs, payment systems, phone pings) | Needs university permission and data access; the planner keeps working on historical data. Yra is following up with UCSD Transportation Services. |
| Event alerts | Deferred; no reliable event source is connected. |
| "Did you find a spot?" feedback | Needs new storage and an endpoint; listed as a future idea. |
| Ground truthing with physical counts | A good way to validate the historical model; not feasible before the demo. |
| Renaming the project | Yra owns the name decision (the experts noted "ParkSmart" is an existing brand). |

## Open items

- Starting location: the backend accepts a starting location but does not use it
  for ranking. The website asks `POST /routes` for a drive time from the
  browser's location when routing is on; the hosted demo has routing off.
- The two non-default weightings (20/80 and 85/15) are starting points, not
  tuned values; revisit them with the experts.
