# Issue #33 deployment resource log

Region: Oregon (`us-west-2`). Yra confirmed credits for one demo deployment
covering Amplify, Lambda, API Gateway, S3, ECR and CloudWatch. Credits/alerts do
not guarantee a spending cap. Send this inventory to Yra for billing review as
resources and stored objects are added. Do not record credentials here.

## Current summary

- Stack `parksmart-backend`: UPDATE_COMPLETE after Yra approved and the operator
  executed `issue33-ui-cors-r1`. The current image is `issue33-ui-alerts-r1`;
  exact digest and size are recorded below.
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

Local verification completed on November 16, 2026. Build, container, and browser
checks are recorded below.

| Check | Reported result | Scope / follow-up |
| --- | --- | --- |
| Full Python suite | 1,176 tests and 39 subtests passed; 38 warnings; 57.31 seconds | Python 3.12.16 with OpenSSL 3.5.9. Post-fix run includes the 32 new helper tests. |
| Frontend tests | 205 tests across 16 files passed | No frontend implementation changes since this run. |
| TypeScript check | `npm run lint` (`tsc --noEmit`) passed | No frontend implementation changes since this run. |
| SAM lint | Valid SAM template | Post-fix validation passed, including the updated ReleasePrefix pattern. |
| New helper tests | 32 passed in 3.19 seconds | Naming consistency, separate image tags, missing resources, build failures, and smoke-check response handling; uses synthetic temporary fixtures and stubs. |
| DS3 review | Refreshed using `docs/codeReviewer.md` after fixes | Six Should fix findings resolved; no remaining Must fix or Should fix findings in the reviewed scope. One optional documentation Nit remains. Report stays local; hosted acceptance checks remain separate. |

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
| Private artifact bucket | `parksmart-artifacts-684494100594` | Six release objects total 24,210,536 bytes. All object checks reported AES256; all four Block Public Access settings were true. AWS saved readiness confirms runtime access. Bucket-level encryption/ownership inspection remains denied by scoped permissions. | Outside stack; retain or remove releases only with data-owner approval. |
| CloudFormation stack | `parksmart-backend` | UPDATE_COMPLETE after approved `issue33-ui-cors-r1`; manages the backend resources below. | Approved stack deletion removes managed resources; S3, ECR and Amplify remain separate. |
| Lambda function | `parksmart-backend-BackendFunction-zp73rvpICDuS` | Saved readiness and recommendations passed. Reviewed configuration: 1024 MB, 30-second timeout, shared concurrency; no provisioned concurrency. | Stack-managed; runtime role is retained separately. |
| API Gateway HTTP API and default stage | `3auautq1ga`, `$default` | HTTPS API serves public website requests. Reviewed stage throttle: rate 1 / burst 2. | Stack-managed, including two Lambda invocation permissions. |
| CloudWatch log group | `/aws/lambda/parksmart-backend-BackendFunction-zp73rvpICDuS` | Runtime logs read successfully; reviewed retention is seven days. | Stack-managed; verify removal during approved teardown. |
| Amplify Hosting app | `parksmart-website`, app ID `d2ru7u75tkpr69`, branch `demo` | Updated frontend and preview description deployed by manual ZIP upload; public browser and incognito searches passed. No Git-connected automatic deployment. | Outside backend stack; delete separately only after approval. |
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
