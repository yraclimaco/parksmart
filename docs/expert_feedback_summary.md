# Domain expert feedback: what we addressed

Meeting: Fri 2026-11-06 with Ellen Schwartz (UCLA Center for Parking Policy) and
Jonathan Wicks (Walker Consultants). This lists the advice that shaped the
website and backend for Issue #32, and what we chose not to build.

## Addressed

| Advice | What changed |
| --- | --- |
| Make walking distance prominent ("emphasize walk") | Walk time is shown large, with a footprints icon, at the top of each result card. |
| Color-code availability; colors read faster than text | Green 20–100% open, yellow 10–20%, red under 10%, on cards, bars and map pins. Each color also has a text label ("Spaces open", "Usually full"). |
| Say availability comes from historical patterns | Cards read "Based on historical patterns for 10:00 AM"; the page footer and every result list say these are historical estimates, not live availability. |
| Let users trade walking against availability | A Prioritize control (Shorter walk, Balanced, More space) and a Max walk limit (5, 10, 15, 20 minutes). Scoring runs in the shared backend (`preference` and `max_walk_minutes` on `POST /recommendations`), so the website and the iOS app can share the same behavior. |
| Explain why a pick ranks where it does | Each ranked location carries a `fit_reason`, for example "8 min longer walk than Pangea, but more space in past surveys (53% vs 9% open)". |
| Do not mistake an estimate for a guarantee | Percentages are described as the share of spaces open in past surveys, never as a chance of finding a space. |

## Not building for the final version

| Advice | Why not |
| --- | --- |
| Visitor and daily-pay pricing | Out of scope for this release. Permit V stays selectable. |
| Photos of structure entrances | Out of scope for this release. |
| Which levels are open for which permit | Not reliably recoverable from the data we have. |
| Live occupancy (dynamic signs, payment systems, phone pings) | Needs university permission and data access; the planner keeps working on historical data. Yra is following up with UCSD Transportation Services. |
| "Did you find a spot?" feedback | Needs new storage and an endpoint; listed as a future idea. |
| Weather, construction and event alerts | Needs backend integration work that is not part of this release. |
| Ground truthing with physical counts | A good way to validate the historical model; not feasible before the demo. |
| Renaming the project | Yra owns the name decision (the experts noted "ParkSmart" is an existing brand). |

## Open items

- Starting location and drive time: the backend accepts a starting location but
  does not use it yet.
- The two non-default weightings (20/80 and 85/15) are starting points, not
  tuned values; revisit them with the experts.
