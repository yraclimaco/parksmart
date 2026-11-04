# ParkSmart iPhone prototype

SwiftUI + MapKit; iPhone with iOS 17+. Requires a Mac, Xcode 15+ and an installed
iOS simulator. No third-party Swift dependencies or API keys. Framework choice
is proposed; confirm with Yra. Android is outside this prototype.

## Run on Mac

From the repository root:

```bash
open mobile/ios/ParkSmart.xcodeproj
```

Select the **ParkSmart** scheme and an installed **iPhone simulator** at the top.
Press **Command-R**. No signing team is required for a simulator. If none appears,
install an iOS runtime in Xcode Settings → Platforms/Components. Physical-device
signing uses your own local team; never commit personal signing changes.

The app has been built and tested on Hanrong's Mac in the iPhone 17 simulator.
See STATUS.md for demonstrated behavior and remaining limitations.

## Demonstrate

1. Enter a destination, arrival date/time and permit code. DatePicker uses UCSD's
   America/Los_Angeles timezone regardless of the device timezone. Permit text
   records input, not eligibility. Destination/permit require 1–200 characters.
2. Tap **Show sample plan**. Observe loading and two selectable example cards.
   Unknown measurements display **Unavailable**. The fixed fixture arrival is
   shown; examples never evaluate or adapt to the entered preferences.
3. Select a card or catalog row to highlight its location ID. With a verified
   catalog, card/marker selection also focuses the map. An unrelated marker only
   selects its catalog row and never creates a recommendation.
4. Choose the other Sample states and tap the button: **Empty result**, **Not
   implemented**, and **Error**. Empty does not mean all lots are full. Editing
   inputs clears old results and cancels old work.
5. Expand **Prepared API request**. JSON uses snake_case and an explicit UCSD
   UTC offset. Optional nil origin/coordinates are omitted, allowed by the Python
   models. Sample mode never sends the request.

Sample JSON is separate from interface code and copied from the team's existing
examples. No numerical availability, walking times or eligibility are fabricated.
The default catalog has fictional IDs and null coordinates, so no parking markers
are drawn. MapKit searches for UCSD only to frame the campus basemap; it never
geocodes fictional parking names. The map needs network access and reports a
failed campus lookup. Parking markers require catalog data_status `verified`
and valid coordinate pairs. Coordinate provenance belongs in the shared registry.

## Backend connection

Create the Python environment using `docs/backend.md`, then from the root:

```bash
source .venv/bin/activate
python -m uvicorn src.api.main:app --reload
```

In **Connection**, enable **Use shared API**, use `http://127.0.0.1:8000`, and
tap **Done**. This requests GET /locations. The simulator uses the Mac's loopback
service. The current backend returns the shared verified location catalog.
Failures remain visible; there is no silent fallback to bundled samples. Reopen
Connection and tap Done to retry. Simulator connectivity has been demonstrated.

Physical iPhone: run the server with `--host 0.0.0.0 --port 8000` and use
`http://<Mac-LAN-address>:8000` from the same trusted network. Phone localhost
refers to the phone. Allow local-network permission and Mac incoming connections
when prompted. Campus Wi-Fi may isolate devices. If numeric HTTP is rejected by
transport policy, try the Mac's `.local` hostname or team-provided HTTPS address.
The plist permits local networking, without a global HTTP bypass. Physical-device
connectivity is a separate check and is not certified by a simulator build.

The URL is stored in simulator/device preferences, not in Git. Recommendations
reset to disabled on launch. Enable POST /recommendations in Connection
to request first-choice and backup options from the shared backend. HTTP 404/405/501 produces an unavailable message. No local prediction,
ranking, permit filtering, walking calculation or routing is implemented.

## Build and test

From the repository root on Mac:

```bash
xcodebuild -list -project mobile/ios/ParkSmart.xcodeproj
xcodebuild -showdestinations -project mobile/ios/ParkSmart.xcodeproj -scheme ParkSmart
xcodebuild -project mobile/ios/ParkSmart.xcodeproj -scheme ParkSmart \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/parksmart-ios-build CODE_SIGNING_ALLOWED=NO build
```

Replace SIMULATOR_ID below with an installed destination ID from the second command:

```bash
xcodebuild -project mobile/ios/ParkSmart.xcodeproj -scheme ParkSmart \
  -destination 'platform=iOS Simulator,id=SIMULATOR_ID' \
  -derivedDataPath /tmp/parksmart-ios-build CODE_SIGNING_ALLOWED=NO test
```

Native XCTest cases cover null/zero, backup IDs, response consistency, fraction
bounds, verified-only markers, URL guards, time offsets and disabled-endpoint
behavior. Run shared fixture/API checks and full pytest in the Python environment:

```bash
python -m pytest tests/test_mobile_fixtures.py tests/test_api.py tests/test_api_schemas.py -q
python -m pytest -q
```

Run `docs/codeReviewer.md` before requesting review; keep code_review.md local.
Capture actual screenshots using Simulator File → Save Screen (Command-S): form,
selected cards, empty/error, and API catalog. Save chosen evidence in
`mobile/ios/demo/` with descriptions. Do not substitute mockups for run evidence.
Yra handles approval/merge. See STATUS.md for unverified and blocked work.

## Layout

- Models: proposed JSON types, validation, display formatting.
- Services: URLSession transport and a separate bundled-sample provider.
- ViewModels: form/request state and cancellation.
- Views: form, selection, connection settings and map.
- Resources: exact shared JSON fixtures and fictional catalog.
- ParkSmartTests: native contract tests; Xcode project includes a shared scheme.

## Local recommendation data

Recommendations require data/processed/pipeline/analysis_dataset.csv.
Follow docs/pipeline.md to download the source workbooks and build that file.
Restart the backend after preparing the dataset. Missing prediction resources
can produce HTTP 503 even when the location catalog works.

In API mode, use Find destination and select an Apple Maps result.
The app sends the selected destination name and coordinates to the shared backend,
which calculates recommendations and walking estimates. Walking times are
straight-line estimates, not routed walking directions.
Availability is a historical estimate, not live occupancy.
Supported backend permit codes are A, B, S, SR, D and V.

For a simulator demonstration, enable both API toggles in Connection, enter
a destination, tap Find destination, select a result, enter a supported permit
code, and tap Request parking plan.
Select the backup card and confirm that its marker becomes orange and the
map moves to that location.
