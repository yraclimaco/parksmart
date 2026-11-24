# Issue #33 deployment resource log

Region: Oregon (`us-west-2`). Yra confirmed credits for one demo deployment
covering Amplify, Lambda, API Gateway, S3, ECR and CloudWatch. Credits/alerts do
not guarantee a spending cap. Send this inventory to Yra for billing review as
resources and stored objects are added. Do not record credentials here.

## Current summary

- Backend release: `releases/issue33-pins-2026-11-23`, applied through
  `issue33-corrected-pins-r1`. Hosted readiness and registry comparison passed.
  The existing image `issue33-ui-alerts-r1` is unchanged; its digest and size
  are recorded below.
- API: https://3auautq1ga.execute-api.us-west-2.amazonaws.com — saved readiness
  returned HTTP 200; the private release loaded successfully.
- Website: https://demo.d2ru7u75tkpr69.amplifyapp.com — existing Amplify app
  `parksmart-website`, branch `demo`, updated by manual ZIP upload.
- Public first/backup cards, map markers, shorter-walk preferences and incognito
  searches passed operator checks. The updated preview description is deployed.
- Dylan reported testing the public website and confirmed it appeared to work.
  This is teammate-reported verification, not an independent check of every
  feature or failure state.
- Routing remains disabled; hosted walking/driving routes are pending. The first
  search after a long idle period has not been verified within the website's
  20-second timeout. Hosted alerts and failure-state checks remain open.
  Automated results and review status are tracked in the verification table below.
- Account-owner billing review remains necessary; this log does not verify
  actual charges or credit balances.

## Automated verification results

Results include November 16 checks and the November 23 frontend deployment.
Earlier Python and SAM results apply to their original revisions; they were not
rerun for this documentation update. Build and browser checks are recorded below.

| Check | Reported result | Scope / follow-up |
| --- | --- | --- |
| Full Python suite | 1,176 tests and 39 subtests passed; 38 warnings; 57.31 seconds | Python 3.12.16 with OpenSSL 3.5.9. Post-fix run includes the 32 new helper tests. |
| Frontend tests | 375 tests across 32 files passed on November 23 | API-mode build from merged commit `8eaaacf`, including PR #45. |
| TypeScript check | `npm run lint` (`tsc --noEmit`) passed on November 23 | Same frontend revision as the 375-test run. |
| SAM lint | Valid SAM template | Post-fix validation passed, including the updated ReleasePrefix pattern. |
| New helper tests | 32 passed in 3.19 seconds | Naming consistency, separate image tags, missing resources, build failures, and smoke-check response handling; uses synthetic temporary fixtures and stubs. |
| DS3 review | Documentation follow-up reviewed after the PR #47 revisions using `docs/codeReviewer.md` | Scope and results are recorded in the local review report. Automated test results are operator-supplied; tests were not independently rerun during review. |

The initial Python 3.9/LibreSSL run failed because dependencies and TLS support
were unsuitable. The passing full run above used the supported environment;
the earlier failures are not evidence of deployed failures. Passing automated
tests do not clear the open hosted acceptance checks or establish zero charges.

## Current resource inventory

The inventory below reflects deployment outputs and checks supplied by the
operator. Configuration limits are from the reviewed template; this is not a
live billing or account-wide resource scan.

| Resource | Identifier | Current status / evidence | Removal or ownership |
| --- | --- | --- | --- |
| Private ECR repository | `parksmart-backend` | Two confirmed uploaded tags: original `issue33-lambda-2026-11-14` and deployed `issue33-ui-alerts-r1`. Digests and sizes below; Lambda pull policy confirmed by Yra. | Outside stack; remove unused images/repository only after approved shutdown. |
| Private artifact bucket | `parksmart-artifacts-684494100594` | Original six-object release totals 24,210,536 bytes; five additional objects under `releases/issue33-pins-2026-11-23/` total 24,211,553 bytes. HeadObject reports AES256 for all five and sizes matching local files; hashes are recorded below. Original object checks reported AES256; all four Block Public Access settings were true. AWS saved readiness confirms runtime access. Bucket-level encryption/ownership inspection remains denied by scoped permissions. | Outside stack; retain or remove releases only with data-owner approval. |
| CloudFormation stack | `parksmart-backend` | Latest update used `issue33-corrected-pins-r1`; hosted readiness and corrected coordinates passed afterward. Final stack-status output is not recorded for this update. | Approved stack deletion removes managed resources; S3, ECR and Amplify remain separate. |
| Lambda function | `parksmart-backend-BackendFunction-zp73rvpICDuS` | Saved readiness and recommendations passed. Reviewed configuration: 1024 MB, 30-second timeout, shared concurrency; no provisioned concurrency. | Stack-managed; runtime role is retained separately. |
| API Gateway HTTP API and default stage | `3auautq1ga`, `$default` | HTTPS API serves public website requests. Reviewed stage throttle: rate 1 / burst 2. | Stack-managed, including two Lambda invocation permissions. |
| CloudWatch log group | `/aws/lambda/parksmart-backend-BackendFunction-zp73rvpICDuS` | Runtime logs read successfully; reviewed retention is seven days. | Stack-managed; verify removal during approved teardown. |
| Amplify Hosting app | `parksmart-website`, app ID `d2ru7u75tkpr69`, branch `demo` | Merged frontend `8eaaacf` deployed by manual ZIP upload on November 23; public first/backup cards and matching markers confirmed. No Git-connected automatic deployment. | Outside backend stack; delete separately only after approval. |
| Runtime/deployment IAM roles | `ParkSmartLambdaRuntime`, `ParkSmartCloudFormationExecution` | Existing roles supplied and managed by Yra; not created by this issue. | Retain; do not delete or replace during stack cleanup. |

The public API and website URLs are in the current summary above. Resource names,
app/API IDs, image digests and account identifiers are deployment metadata, not
credentials; they do not grant access. Do not include passwords, access keys,
session tokens, private keys, raw model files or dataset contents in this log.

Local Docker builds, model bundles and website ZIPs are not additional AWS
resources. Stored ECR layers can be shared between image versions, so reported
image sizes are not additive billable storage. Actual usage and credit coverage
must be checked by the account owner.

## Historical checkpoints

Earlier pending statements below apply only to their checkpoint. The current
summary and inventory above, together with later verification entries, supersede
them. The initial inventory covered ECR, S3 and the existing IAM roles before the
backend stack and Amplify deployment were completed.

## Integration dependencies — before PRs #36 and #37 merged

Dylan reports PR #37 includes both the preference controls and backend scoring,
larger walking times, historical labels, color tiers and revised fit reasons.
He reports routed walks verified end to end and 1003 tests passing on his branch;
these are teammate-reported results, not verification of this deployment branch.
His landing page lives in a separate repository and needs the public planner URL.
Do not duplicate his frontend or scoring changes. Yra handles review/merging.

The earlier checkout (394a747) used RecommendationRequest with `extra="forbid"`
and no preference fields. A frontend sending unknown fields would receive 422;
we cannot assume the older backend ignores them. Once PR #37 is approved/merged,
update this branch, inspect its exact request fields and backend mapping, resolve
conflicts without dropping either feature, rebuild the serving image, and verify
default and changed preferences. Regenerate model/data bundles only if their
relevant inputs or reproduction code changed; do not select a new model here.

Dylan also reports PR #36 has conflicts with main in main.py, test_api.py and
AGENTS.md. Check actual merge order/status before updating; preserve both sets
of reviewed changes and rerun affected tests. No merge status has been verified.
Provide the public website URL for his landing-page button and a joint test,
and provide the API URL to Hanrong. No deployed preference-control verification
or joint test is recorded yet.

## Historical local verification and access blockers — 2026-11-15

The operator supplied passing local serving-image build, revised SAM lint and
Lambda-emulator results: saved readiness and two requests with distinct first
and backup choices. The local model release verifier also established one
startup artifact load with fitting forbidden during serving. These are local
checks, not cloud deployment or live routing verification.

CLI login returned browser 400 for regular and remote flows, including private
browsing. ECR listing returned an explicit identity-policy denial for
`ecr:DescribeRepositories` for the assigned operator. This prevents inspecting
the repo, not proof it was deleted. Permission/login resolution is pending with
Yra. No replacement repo, image upload, S3 upload or change set was created.

## Access and concurrency update — 2026-11-15

CLI identity and repository-specific ECR inspection now succeed after the CLI
update. Broad ECR listing is intentionally unavailable; the repository exists.
Oregon's Lambda quota returned Total=10 and Unreserved=10. Yra approved shared
concurrency; reserved concurrency was removed from the local template. API rate
1/burst 2, timeout 30 seconds and memory 1024 MB remain; no provisioned
concurrency. Actual memory/latency measurements remain pending. The account
billing alert is reported by Yra, not independently inspected here.

The earlier 404 was resolved: Yra confirmed the bucket had not existed and
authorized creation. Daira supplied successful create-bucket and head-bucket
results, with BucketRegion us-west-2 and expected owner 684494100594. All four
bucket Block Public Access settings returned true. Encryption and ownership
checks remain pending. No uploads or stack execution have occurred. The demo
uses the mentor-approved minimal-usage approach; no hard $0 guarantee is claimed.

## Confirmed private release upload

The operator supplied successful PutObject responses for all six objects under
`s3://parksmart-artifacts-684494100594/releases/issue33-lambda-2026-11-14/`:

- `selected.pkl`
- `analysis_dataset.csv`
- `locations.json`
- `metadata.json`
- `requirements-model.txt`
- `manifest.json` (uploaded last)

Each response reported ServerSideEncryption AES256 and a full-object checksum.
Uploads used expected owner 684494100594, Standard storage, no ACL changes and
If-None-Match to refuse replacement. All four bucket Block Public Access settings
were already confirmed true. Bucket-level encryption/ownership inspection was
denied; no broader permissions were requested as a deployment prerequisite.
Remote object sizes and manifest-bound runtime download checks remain pending.
Record sizes after inspection for billing review. No raw contents or credentials
are included in this log. ECR image upload and CloudFormation execution remain
pending. Earlier no-upload statements above describe previous checkpoints.

## Verified stored objects and ECR image

The operator checked all six S3 objects with HeadObject. In manifest-last upload
order, sizes are selected.pkl 531,977 bytes; analysis_dataset.csv 23,627,422;
locations.json 48,507; metadata.json 1,547; requirements-model.txt 75; and
manifest.json 1,008. Total: **24,210,536 bytes**. All reported AES256 encryption.
These are storage metadata checks, not remote manifest-bound hash verification.

The ECR push eventually succeeded after network timeouts. DescribeImages confirms
one image tagged `issue33-lambda-2026-11-14`, size **318,480,370 bytes**, digest:

```text
sha256:8dd0f74cd7efc3a0fa35ea6e5dd4045e3305b17311e165cdbdc4d52d6ab6deaf
```

Use this exact digest for the proposed deployment. The push output's 2386-byte
size describes the manifest, not the full stored image. Billing coverage/actual
usage remains for the account owner to check; neither size establishes a charge.
The template now accepts BackendImageUri pinned by digest, avoiding an implicit
rebuild of the image used for the initial change set. Revalidation is pending.
No backend stack execution or public URL had been verified at that checkpoint.

## Initial deployment and updated local image checkpoint

This checkpoint supersedes the pending statuses above. Operator-supplied AWS
output confirms stack `parksmart-backend` reached CREATE_COMPLETE after change
set `issue33-initial-demo-20261115-r3`. The earlier r2 attempt rolled back;
its stack resources were deleted and Yra removed the failed stack before r3.
The private S3 release and ECR image were retained.

- Function: `parksmart-backend-BackendFunction-zp73rvpICDuS`.
- API: `https://3auautq1ga.execute-api.us-west-2.amazonaws.com`.
- Readiness and a recommendation returned HTTP 200 in saved mode, with distinct
  first and backup choices and `is_example: false`. Routing remains disabled.
- Initial startup included a 30-second timeout; a later invocation completed in
  about 19 seconds. Cold-start latency remains unresolved. Reported peak memory
  was 386 MB with 1024 MB configured; this alone does not establish right-sizing.
- Amplify app: `parksmart-website`, hosting branch `demo`, public URL
  `https://demo.d2ru7u75tkpr69.amplifyapp.com`. The initial manual upload used
  frontend code from 394a747. A rebuild and redeployment are pending.
- CORS preview `issue33-amplify-cors-r1` is unexecuted. Yra requested a new
  combined image-and-origin preview after integrating PRs #36 and #37.

The local branch was fast-forwarded to 15ddd0f, including PRs #36 and #37;
deployment work was restored and the AGENTS.md stash conflict resolved.
An operator-run local Docker build succeeded with tag
`parksmart-backend:issue33-ui-alerts-r1`, using the existing release's dependency
lock and the pinned linux/amd64 base. Cached dependencies were reused. This
new image has not yet been checked in the emulator, pushed to ECR, or deployed.
Its full digest and remote size are recorded in the follow-up below. No new model
bundle or AWS resource was created by this local build. Hosted preference and
alert behavior, the updated frontend, and end-to-end browser verification remain
pending; merged code alone is not evidence that these features work on AWS.

### Updated image verification and upload

Operator-run Lambda-emulator checks passed for `issue33-ui-alerts-r1`: saved
readiness and two default requests returned distinct first/backup choices. A
`shorter_walk` request with `max_walk_minutes: 15` returned Pangea at 10 minutes
and no backup, with the personal-limit limitation disclosed.

ECR DescribeImages confirms the new tag `issue33-ui-alerts-r1`, size
**318,501,289 bytes**, and digest:

```text
sha256:4b153ba7a6c605d6d6a293b38bc1b8d0f713103697f81a18de4f900f89d68748
```

This is an additional image version in the existing private repository, not a
new repository. Reported image sizes include shared layers and must not be
summed as exact incremental billable storage. The original image and private
model release remain available.

### Combined update and public website check

Yra reviewed and approved `issue33-ui-cors-r1`. Operator-supplied output confirms
UPDATE_COMPLETE and HTTP 200 from `/readiness`, with catalog/predictions ready
in saved mode. The update uses the new image digest above and exact origin
`https://demo.d2ru7u75tkpr69.amplifyapp.com`, without replacing resources.

The updated frontend was built with the deployed API URL and API mode, then
manually redeployed to the same Amplify app and `demo` branch. Daira reported a
quick successful search from the public website, showing both recommendation
cards and corresponding map markers. The screenshot shows Geisel Library,
November 16, 2026 at 22:00, permit S, Balanced preference, 20-minute maximum
walk, Scholars as first choice and Pangea as backup. This differs from the
suggested November 3 smoke input; the actual browser input is recorded here.
No numerical latency measurement or request-status capture was supplied for
this browser search. Warm success does not resolve the earlier cold-start
timeout. Hosted preference changes, failure states, trip alerts and another
teammate's independent search remain to be verified. Routing remains disabled.


### Hosted preference follow-up

Daira tested the same Geisel Library trip with Shorter walk and a 10-minute
maximum. The screenshot shows Hopkins first with a six-minute estimate and
Scholars as backup. A later screenshot confirmed the Scholars backup at seven minutes, also within
the selected 10-minute limit. Both recommendations disclose straight-line walk
estimates; historical time-coverage limitations remain visible.


### Private-window and preview-description verification

The operator completed incognito searches for Geisel Library, November 16, 2026,
at both 10:00 and 22:00, with permit S, Shorter walk and a 10-minute maximum.
The 10:00 screenshot shows Pangea first at 10 minutes; the 22:00 screenshot shows
Hopkins first at six minutes and Scholars as backup. The first search reportedly
had a brief delay, approximately a second, and the second felt immediate. These
are subjective timings; private browsing does not establish a Lambda cold start
or resolve the earlier timeout.

The frontend description and Open Graph description now reference a hosted API
and historical survey estimates. The operator rebuilt and manually redeployed
the site, then confirmed the new description in the deployed page source.
No new app, backend image or model release was needed for this metadata update.
Social platforms may retain older preview caches.

### Review follow-up: upstream description provenance

Dylan supplied [ParkSmart-Website commit 971e8ce](https://github.com/dylanwang-main/ParkSmart-Website/commit/971e8ce06f56f40ef2353576d309ec1cf81fec9c).
The operator's Git inspection confirmed the description change and that the
commit is contained in upstream `main`. A full sync dry run showed additional
landing-page/UI changes and proposed local ZIP deletions; the full sync was not
applied. A metadata-only sync from that commit's export verified/copied the two
existing local page/Open Graph descriptions and JSON description. Values already
matched, so the frontend content stayed unchanged. This records source provenance
without claiming a full frontend sync or bringing unrelated UI changes into
Issue #33. No files were deleted or resources redeployed. Scope and the omitted
upstream Twitter-description tag are documented in `docs/frontend_deployment.md`.


## Corrected registry and frontend deployment — 2026-11-23

Release preparation used source commit `8eaaacfcd51879cfaed65aa615134723409116c2`
([merged PR #45](https://github.com/yraclimaco/parksmart/commit/8eaaacfcd51879cfaed65aa615134723409116c2)). The deployed backend reads its
registry from S3, so the backend release was updated before uploading the website.
The new private bundle `issue33-pins-2026-11-23` reuses the existing approved
`selected.pkl` and `analysis_dataset.csv` unchanged, with the corrected registry,
new manifest and dependency pins. It does not retrain or switch to Fall 2026-only
data. Old reproduction metadata was omitted because it binds the old registry.
The original immutable release remains available.

The rebuilt pinned Lambda-compatible preparation image passed local verification:
saved readiness, one artifact load and two requests returning distinct first and
backup choices, with training forbidden and routing disabled. Five files were
uploaded to the existing private bucket under the new release prefix, requesting
AES256 encryption and refusing overwrites; the manifest was uploaded last.
No new ECR image or repository was needed. The five new objects total
24,211,553 bytes; the original six-object release is retained separately.


### Release identity and stored-object evidence

The operator computed SHA-256 values from local bundle bytes and checked S3
ContentLength and ServerSideEncryption with HeadObject for each new object.
All five remote sizes match local sizes, and all five report `AES256` (SSE-S3).
HeadObject size/encryption checks do not independently establish remote SHA-256
values. The release verifier checked the local manifest-bound runtime files;
the serving loader verifies manifest hashes when materializing its runtime files.
No remote full-object rehash is claimed here.

| New release object | SHA-256 of local file | Local and S3 bytes |
| --- | --- | ---: |
| `selected.pkl` | `5f94df4c9c60772421e5a190fc75153716f264b1360f42db3a6843fac8c8a940` | 531,977 |
| `analysis_dataset.csv` | `9660b051971facacb12b34a6722223416051b0e5f9e43656688df04a1150384b` | 23,627,422 |
| `locations.json` | `06fecc3beffca21b3f019e032a3958a9cea48cf238afea9b591f0b8d521885a9` | 51,250 |
| `requirements-model.txt` | `6c51abc4852c31b99a34e334b1cfeee39afb7366fd149009a6923c96f5badb24` | 75 |
| `manifest.json` | `4e9036127fa6040e2c1f2ccd39a30915b7ae283f9f5be97e5b681ffaf0c98af7` | 829 |
| **Total** | | **24,211,553** |

Direct local SHA-256 comparisons with the previous
`issue33-lambda-2026-11-14/bundle` returned equal hashes for both `selected.pkl`
and `analysis_dataset.csv`: the previous hashes are identical to their new-release
values in the table. The new bundle registry hash also matches the working-tree
`config/locations.json` from the release source commit recorded above. This
provides byte-level evidence for unchanged model/data and the corrected registry,
without publishing their contents. Object sizes are storage inventory, not a
measurement of charges or remaining credits.

### Hosted and browser verification

Change set `issue33-corrected-pins-r1` retained the deployed image digest, exact
frontend origin and other parameters. Its preview showed a Lambda environment
update and a dependent API integration update, both without replacement. Yra's
request covered this deployment. After execution, hosted
`/readiness` returned HTTP 200 with saved predictions ready. A comparison of
`/locations` against every supported registry entry found no ID or coordinate
mismatches. Approximate coordinates intentionally become null in the API,
including P386. Supported P503 was included in this catalog comparison. P001
is not supported and was not verified through `/locations`; non-supported pins
were checked locally with `python -m pytest tests/test_location_registry.py -q`:
25 tests passed in 4.40 seconds, including registry/website coordinate consistency
and lot-outline checks. These checks do not verify vehicle entrances or permit
rules.

A hosted recommendation for Geisel Library (32.8811, -117.2376), November 24,
2026 at 10:00 America/Los_Angeles, S permit, Balanced and a 20-minute maximum
walk returned `ready` and `is_example: false`. First choice was Torrey Pines
Center North (53% estimated open, 18-minute walk); backup was Pangea (9%,
10-minute walk). Both disclose historical availability and straight-line walks.
This verifies response behavior, not independent permit-policy accuracy.

`bash scripts/build_site.sh issue33-pins-8eaaacf-20261123` completed API readiness,
375 frontend tests, TypeScript checking and the API-mode production build.
The install audit reported zero vulnerabilities; no dependency changes were
made for this deployment. The bundle-size warning did not fail the build.
The generated ZIP was uploaded to the existing Amplify app's `demo` branch.
The operator confirmed the updated public page, first-choice/backup cards and
matching map markers. No ZIP, model, dataset or credentials belong in this PR.

Remaining work: verify first-search timing after long idle; hosted routing is
disabled; complete alert freshness and failure-state checks; review permit and
location mappings; and integrate Vivaan's Fall 2026 release when ready. Existing
alert displays do not establish source completeness. These are separate from
the completed coordinate and frontend deployment. Account-owner billing review
remains pending.
