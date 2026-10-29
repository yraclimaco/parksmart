# ParkSmart - UCSD Parking Planner Prototype

A desktop-first web prototype for UCSD parking planning. This prototype uses sample data to explore parking options, walking times, and recommendation scoring.

> **Disclaimer**: This is a front-end only prototype using clearly labeled SAMPLE data. Nothing in it is a real prediction or live availability. It never claims guaranteed availability.

> **Where to edit**: the source of truth is [dylanwang-main/ParkSmart-Website](https://github.com/dylanwang-main/ParkSmart-Website), synced with Google AI Studio. The `frontend/` folder in [yraclimaco/parksmart](https://github.com/yraclimaco/parksmart) is a one-way copy made with `scripts/sync_frontend.sh`. Do not edit website files there; the next sync overwrites them. Make the change in ParkSmart-Website, then sync.

---

## Tech Stack

- **React 19** with **TypeScript**
- **Tailwind CSS v4** for clean, low-saturation glassmorphism UI
- **MapLibre GL JS** with two free, keyless basemaps and a Map / Satellite toggle:
  - **Satellite (default):** USGS National Map imagery (public domain, cached to zoom 16)
  - **Map:** OpenFreeMap Positron vector tiles
- **Motion (`motion/react`)** for smooth, subtle card stagger transitions
- No backend, no routing, no external authentication required

---

## Architecture & Layout

- **Full-Screen Map Canvas**: Satellite imagery by default, with a Map / Satellite toggle in the top right. Automatically fits bounds to all lots and active destination with panel offset padding (left: 404px, edges: ~60px).
- **Floating Glass Panel (`380px` wide)**: Positioned on the left with Apple Maps style frosted glass (`bg-white/45`, `backdrop-blur-2xl`, boosted saturation), a neutral palette, and color reserved for availability.
- **Corner State Simulator**: A dedicated developer switcher in the bottom-right corner to test all 4 required UI states (`Normal`, `Loading`, `Empty`, `Error`).

---

## What Is Real vs Sample

| Data | Status | Source |
|---|---|---|
| Parking structure names and pin locations | **Real** (verified 2026-10-21) | UCSD campus GIS, Building Points Public layer |
| 52 surface lots (incl. Gliderport, P386) | **Real** IDs and pins (verified 2026-10-21) | P-numbers from the team's cleaned QPASS inventory; pins at each lot's outline center in UCSD GIS layer 21 (`src/data/surfaceLots.ts`) |
| Destination names and locations (~300 buildings) | **Real** (verified 2026-10-21) | Same UCSD GIS layer, active buildings minus utility/storage/lab modules (`src/data/destinations.ts`) |
| Class-schedule codes (WLH, PCYNH, CENTR...) | **Real** (verified 2026-10-21) | 24 classroom buildings from facilities.ucsd.edu/Classrooms, plus GIS alias codes |
| "Popular" list order | **Our pick** | Swap for real search counts from `GET /destinations` |
| Lot photo on the lot card | **Real** aerial imagery (verified 2026-10-22) | USGS NAIP orthoimagery, about 0.3 m/pixel, public domain, cropped around each pin on demand (`src/utils/lotAerial.ts`) |
| Availability %, stall categories per structure, rankings | **Sample** | Placeholders until the QPASS pipeline and permit rules connect |

Lot data lives in `src/data/parkingLots.ts`. Pins mark each structure's building point, not its vehicle entrance. Mapping each structure to its official P-number (e.g. P701) is still an open question for the backend team.

---

## Permit Hours (time-aware eligibility)

`src/utils/permitRules.ts` encodes when each permit may use each stall category, from the team's **UCSD Parking Domain Research v1.2** (section 2). Example: an S permit can use S and D stalls 24/7, and A/B stalls weekdays 4 PM to 8 AM plus all weekend. Recommendations only include structures the permit can use **at the arrival time**, and cards show "Open 24/7" or "Valid until ...".

Not modeled yet (open questions in the research doc): A 24/7, reserved, accessible and SuperSaver stalls; lot-specific rules (P386, P701, SIO); holiday category rules; the Sept 2026 D restriction's effect on other permits; ParkMobile vs pay-station V; checking the whole stay rather than just arrival. Which stall categories each structure has (`spaceCategories`) is still **sample** data.

---

## Time Scrubber and "Your Usual"

- **Time scrubber** (top of the map): drag or press play to watch every pin recolor as campus fills and empties through the day. "Use this time" copies the previewed time into the arrival time. Availability by time comes from `src/utils/availabilityModel.ts`, a **sample** daily curve; swap `availabilityAt` for the real forecast when the backend connects. Labels pair numbers with confidence words: Likely open / Getting tight / Usually full.
- **Your usual**: only appears after you have searched. The last search is saved in this browser only (`localStorage`, `src/utils/usualTrip.ts`); next visit a card answers it instantly (the form is not prefilled), with "Forget my usual" to clear it.

---

## Destination Search

- **No default destination.** The box says "Where are you headed?" and Find parking stays off until you pick one.
- **Before typing:** a Popular list (lecture halls, libraries, Price Center, RIMAC).
- **While typing:** matches by name, class-schedule code (`wlh` puts Warren Lecture Hall first) and other names (`ledden`, `calit2`). Arrow keys and Enter work.
- **Parking in the same box:** typing `gilman` or `p406` shows lots under "Parking". Picking one opens its card on the map; it does not become your destination.
- **Not listed?** Tap empty map, then **Park near here**, to use that spot as a dropped-pin destination (stored as an ID like `pin:32.88012,-117.23711`).
- **Recent:** the results header lists this visit's earlier searches. Search X then Y, open Recent, pick X, and you are back on X (Y moves into Recent).

---

## Directions

After **Select this spot**, **Open in Google Maps** opens turn-by-turn driving directions to that lot in Google Maps (the app on phones), starting from the person's current location. It uses a plain Google Maps link: free, no API key, and ParkSmart never asks for or stores the user's location.

## Scoring Formula

Scoring is handled by `calculateParkingScore` in `src/data/sampleRecommendations.ts`:
- **65% Expected Availability**: Prioritizes lots with higher available capacity.
- **35% Walking Convenience**: Normalizes campus pedestrian walk times where shorter walks score higher.

---

## Local Development & Setup

Requires Node.js 20.19+ or 22.12+ (Vite 8) (tested with Node 26 and npm 11). Run these from
the `frontend/` folder.

### 1. Install Dependencies

```bash
npm ci
```

`npm ci` installs the exact versions in `package-lock.json`. Use `npm install`
only when adding or upgrading a dependency, and commit the updated lockfile.

### 2. Configure the Backend URL (optional)

The website calls the FastAPI backend at `http://127.0.0.1:8000` by default.
To use another backend, copy `.env.example` to `.env.local` and set
`VITE_API_BASE_URL`. `.env.local` is ignored by Git. Every `VITE_` variable is
bundled into the public site, so never put secrets in it.

Start the backend from the repository root (see [the backend guide](../docs/backend.md)):

```bash
python -m uvicorn src.api.main:app --reload
```

### 3. Run the Development Server

```bash
npm run dev
```

Open `http://localhost:3000`. Port 3000 is on the backend's local CORS allowlist.

### 4. Build for Production

```bash
npm run build
```

### 5. Run Tests and Type Checks

```bash
npm test        # Vitest
npm run lint    # TypeScript type check
```

Tests live next to the code they cover (for example `src/data/sampleRecommendations.test.ts`). Run both before opening a PR.

---

## Swapping in Real API Data

To connect real live parking sensor data and prediction models:

1. **API Contracts (`src/types.ts`)**:
   - `ParkingPlannerRequest`: destination, arrival date, arrival time, and permit type.
   - `ParkingPlannerResponse`: array of `ParkingRecommendation` objects.

2. **Replace Sample Service (`src/data/sampleRecommendations.ts`)**:
   - Replace the implementation of `getSampleRecommendations(request: ParkingPlannerRequest)`:
   ```typescript
   export async function getLiveRecommendations(
     request: ParkingPlannerRequest
   ): Promise<ParkingPlannerResponse> {
     const response = await fetch('/api/parking/recommendations', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify(request),
     });
     if (!response.ok) {
       throw new Error('Failed to fetch parking predictions');
     }
     return response.json();
   }
   ```

3. **Update State in `src/App.tsx`**:
   - In `runPlanner()`, call `await getLiveRecommendations(formInputs)` inside a `try/catch` block. On catch, set `isError(true)`.

---

## Accessibility & Motion

- All cards and markers support keyboard navigation (`Tab`, `Enter`, `Space`).
- Accessible semantic HTML with proper labels and ARIA attributes (`role="radiogroup"`, `role="listbox"`, `aria-pressed`, `aria-label`).
- Respects `prefers-reduced-motion` for map transitions and card entrance animations.
