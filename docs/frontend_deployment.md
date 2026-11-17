# Website hosting on AWS Amplify — Issue #25

## Current Issue #33 demo: manual deployment

Website: https://demo.d2ru7u75tkpr69.amplifyapp.com

API: https://3auautq1ga.execute-api.us-west-2.amazonaws.com

The demo uses the existing Amplify app `parksmart-website`, branch `demo`, in
Oregon (`us-west-2`). GitHub app authorization was not available, so Yra directed
manual deployment. No Git connection or automatic build is configured for this
app. The Git-connected setup below is a future alternative, not the current
update procedure. See `deployment_resources.md` for verification and limitations.

The combined backend update reached UPDATE_COMPLETE and saved readiness returned
HTTP 200. Public searches displayed first/backup cards and map markers, including
Shorter walk with a 10-minute maximum. Incognito searches at 10 AM and 10 PM
also succeeded: the first had a brief perceived delay, about a second, and the
second felt immediate. These are operator observations, not measured cold-start
latency. The new historical-survey link description was redeployed and confirmed
in the page source. Dylan also reported testing the public website successfully.
Failure-state checks remain open.

### Pending hosted checks

- Routing is disabled on the hosted backend. Walking/driving routes have not
  been verified there; the displayed walking times are straight-line estimates.
- The first search after a long idle period has not been verified to complete
  within the website's 20-second timeout. Incognito searches with brief perceived
  waits are not a confirmed cold-start measurement. Retain the earlier startup
  timeout as an unresolved limitation.

Yra confirmed these checks do not need fixes or redeployment in this review PR.
Hosted alerts and browser error/retry checks also remain separate follow-ups.

### Link-preview metadata provenance

The hosted-API description is maintained upstream in
[ParkSmart-Website commit 971e8ce](https://github.com/dylanwang-main/ParkSmart-Website/commit/971e8ce06f56f40ef2353576d309ec1cf81fec9c),
which is contained in that repository's `main` branch. It updates the page,
Open Graph and Twitter descriptions in upstream `index.html`, plus the description
in `metadata.json`.

For this PR, a metadata-only sync from an export of that exact commit checked and
copied the two existing local description tags (`description`, `og:description`)
and the JSON description. They already matched, so no content change was needed.
The local page does not have the upstream Twitter-description tag; it was not
added by this limited sync. The earlier edit in ParkSmart now has the same
description maintained in the source repository.

The full sync dry run also proposed landing-page, component and styling changes
outside this review request. Those were not applied. This is not a claim that
the entire `frontend/` directory matches that commit; broader UI integration is
separate. No files were deleted and no AWS redeployment was performed.

### Rebuild and update the existing site

Use a reviewed checkout containing matching frontend and backend interfaces.
If the request contract changes, first build/check/deploy its matching backend
image through a reviewed change set. Then, from the repository root:

```bash
cd frontend
npm ci
npm test
npm run lint
VITE_API_BASE_URL=https://3auautq1ga.execute-api.us-west-2.amazonaws.com \
VITE_RECOMMENDATION_SOURCE=api \
npm run build
(cd dist && zip -r ../parksmart-site-NEW-REVISION.zip .)
```

Replace NEW-REVISION with a new identifier for each package; ZIP updates can
retain old entries if an existing archive is reused. `index.html` and `assets/`
must be at archive root. Upload the ZIP using Deploy updates on the existing
Amplify app and `demo` branch; do not create another app. Keep ZIPs ignored.
The production build, frontend tests and TypeScript check passed. See
[verification results](deployment_resources.md#automated-verification-results)
for counts and the remaining post-review checks.

The backend `FrontendOrigins` parameter must be the exact website HTTPS origin
above, with no path or trailing slash. Updates use a nonexecuted CloudFormation
preview and Yra's review before execution. VITE values are public build inputs;
never put credentials in them. Rebuild after changing the API URL or API mode.
Routing is currently disabled, so directions unavailable and straight-line walk
estimates are expected. Hosted trip-alert verification is still pending.

Yra confirmed that account credits cover the demo services and that a billing
alert is configured. Keep a record of created resources for his billing review.
Continue following the project's $0 out-of-pocket constraint; any changes beyond
the approved demo need confirmation with Yra.

## How the pieces fit

```text
Browser ── loads static files ──> Amplify Hosting (built from frontend/)
   │
   └── POST /recommendations, POST /routes ──> API Gateway ──> Lambda (FastAPI, Daira)
                                                                 └─> routing provider (key on Lambda only)
```

- The frontend is built with `npm run build`; Amplify serves `frontend/dist/`
  (static HTML/JS/CSS) over HTTPS on an `*.amplifyapp.com` address.
- The website calls the backend from the browser, so the backend must allow the
  Amplify origin with CORS (`PARKSMART_CORS_ORIGINS`, below).
- `VITE_*` values are copied into the public JavaScript at build time. They must
  never contain secrets; the routing key stays on the backend.

## Git-connected configuration (future alternative)

Build settings live in `amplify.yml` at the repository root (monorepo format,
`appRoot: frontend`).

| Where | Setting | Value |
| --- | --- | --- |
| Amplify environment variables | `AMPLIFY_MONOREPO_APP_ROOT` | `frontend` (must equal `appRoot`; the console sets it) |
| Amplify environment variables | `VITE_RECOMMENDATION_SOURCE` | `api` |
| Amplify environment variables | `VITE_API_BASE_URL` | API Gateway invoke URL from Daira, e.g. `https://abc123.execute-api.us-west-2.amazonaws.com` (no trailing slash needed) |
| Amplify build image settings | Live package updates → Node.js | `22` (an exact version, never `latest`) |
| Backend (Lambda) environment | `PARKSMART_CORS_ORIGINS` | The Amplify URL, e.g. `https://main.d1abc2345.amplifyapp.com` (comma-separate several; exact origins only, no wildcards) |
| Backend (Lambda) environment | `ORS_API_KEY` (optional) | Routing key (see `docs/routing.md`); without it the public OSRM servers are used. Never in Amplify or Git |

Entries are normalized the way browsers send them (lowercase host, no default
`:443`/`:80`). A malformed entry (a wildcard, no `https://`, a path, query or bad
port) stops
the backend at startup with a message naming the entry, rather than failing later
as an unexplained CORS error in the browser. Check CloudWatch logs if the backend
will not start after changing it.

Credentials stay outside Git. Nonsecret app IDs, URLs and resource identifiers
are documented in the resource log; runtime configuration remains in deployment
parameters and hosting settings. Moving accounts requires its own approved
resources, roles, allowances and URLs rather than reusing the demo settings.

## Git-connected deployment (future alternative)

1. Sign in to the DS3 AWS account and pick the same region as the backend
   (`us-west-2`, as specified by Yra).
2. Amplify → **Create new app** → GitHub → authorize access to
   `yraclimaco/parksmart` (Yra or a repository admin may need to approve).
3. Branch: `main`. Tick **My app is a monorepo** and enter `frontend`.
4. Amplify detects `amplify.yml`. Under **Advanced settings**, add the
   environment variables from the table, then set Node.js 22 under build image
   settings.
5. Save and deploy. Note the app URL (`https://main.<app-id>.amplifyapp.com`).
6. Send that URL to Daira to add to `PARKSMART_CORS_ORIGINS` on the backend.

Builds run automatically on every push to `main`, which only changes through
reviewed PRs.

## Verification checklist

- Build log prints `VITE_API_BASE_URL=https://...` (not `unset`) and
  `VITE_RECOMMENDATION_SOURCE=api`, and tests, type check and build pass.
- The page loads over HTTPS and the footer says "Historical estimates from past
  surveys" (API mode), not "Sample data".
- Search Geisel Library, S permit, a weekday at 10:00 AM: cards and pins show
  backend results; the browser's network tab shows `POST .../recommendations` 200
  with no CORS error.
- The directions box shows a walking route; **Use my location** asks for
  permission and then shows a driving route. If routing is off on the backend, the
  box says directions are not set up.
- A Saturday search shows "No availability estimate", not an error.
- With the backend unreachable, the error card says "Couldn't reach ParkSmart"
  and Try again works once it is back.
- The first search after a long idle period may take several seconds (Lambda cold
  start); it must finish or show "taking too long" within 20 seconds.

## Cost guardrails

- Check the current AWS Free Tier and Amplify pricing pages before creating the
  app; allowances change and are not recorded here.
- Set an AWS Budgets alert on the DS3 account before deploying.
- Keep one hosting branch: `demo` for the current manual deployment. A future
  Git-connected deployment may use reviewed `main`; keep automatic PR previews
  off unless the team agrees.

## Cleanup

1. Amplify → the app → **App settings → General → Delete app**. This removes the
   hosting, builds and the `amplifyapp.com` URL.
2. Remove the Amplify URL from `PARKSMART_CORS_ORIGINS` on the backend.
3. Only if a Git connection was configured: in GitHub → Settings → Applications,
   revoke the AWS Amplify app's access if no other app uses it. The current
   manual deployment has no Git connection.
