# Website hosting on AWS Amplify — Issue #25

Preparation only. Deploy in Week 7, **once funded DS3 AWS access is confirmed**.
Do not enable paid usage or use a personal payment method.

## How the pieces fit

```text
Browser ── loads static files ──> Amplify Hosting (built from frontend/)
   │
   └── POST /recommendations, POST /routes ──> API Gateway ──> Lambda (FastAPI, Daira)
                                                                 └─> routing provider (key on Lambda only)
```

- Amplify builds `frontend/` with `npm run build` and serves `frontend/dist/`
  (static HTML/JS/CSS) over HTTPS on an `*.amplifyapp.com` address.
- The website calls the backend from the browser, so the backend must allow the
  Amplify origin with CORS (`PARKSMART_CORS_ORIGINS`, below).
- `VITE_*` values are copied into the public JavaScript at build time. They must
  never contain secrets; the routing key stays on the backend.

## Configuration

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

A malformed `PARKSMART_CORS_ORIGINS` entry (a wildcard, or no `https://`) stops
the backend at startup with a message naming the entry, rather than failing later
as an unexplained CORS error in the browser. Check CloudWatch logs if the backend
will not start after changing it.

Everything account-specific (app ID, URLs, region) lives in console settings, not
in the repository, so moving to the funded DS3 account only means repeating the
steps below there.

## Deploy steps (Week 7)

1. Sign in to the DS3 AWS account and pick the same region as the backend
   (`us-west-2` unless Daira chooses otherwise).
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
- Keep one branch deployment (`main`); turn off automatic preview builds for pull
  requests unless the team agrees.

## Cleanup

1. Amplify → the app → **App settings → General → Delete app**. This removes the
   hosting, builds and the `amplifyapp.com` URL.
2. Remove the Amplify URL from `PARKSMART_CORS_ORIGINS` on the backend.
3. In GitHub → Settings → Applications, revoke the AWS Amplify app's access if no
   other app uses it.
