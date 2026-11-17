# AWS backend deployment — Issues #26 and #33

Issue #26 prepared the backend infrastructure; Issue #33 is validating and
deploying one reviewed demo in Oregon. Yra confirmed credit coverage for the
planned services. Track created resources and usage for his billing review;
credits are not a hard spending cap. Do not enable paid upgrades, add unapproved
services, or execute the first CloudFormation change set before his review.

## Issue #33 deployment checkpoint — updated 2026-11-15

Target region: **Oregon (`us-west-2`)**. The backend stack and private ECR
repository are both named `parksmart-backend`. The assigned private artifact
bucket is `parksmart-artifacts-684494100594`. Use the existing
`ParkSmartLambdaRuntime` role for Lambda and `ParkSmartCloudFormationExecution`
for deployment. These are deployment identifiers, not credentials; keep their
configuration parameterized for migration.

Local Docker Desktop is running on Apple Silicon. A local `linux/amd64` check
of the Lambda image printed **Python 3.12.16** using this exact image reference:

```text
public.ecr.aws/lambda/python@sha256:696fcc2a052fc8f335f9b34c6ec4e50ad54dbe5dd35134ec997c4f97bd150b22
```

This verifies only the base image's Python version, not application readiness.
Use this digest and `--platform linux/amd64` for subsequent release/build checks;
the serving and preparation Dockerfiles now use this pinned default. Vivaan's documented
Issue #27 verification used Python 3.12.10, so regenerate the approved model in
this compatible container rather than changing artifact metadata. Follow
`docs/model_storage.md` for the metadata-bound release and bundle commands.
Preserve existing releases and use a new immutable release ID/prefix.

Current status:

- Console sign-in, temporary-password change and MFA completed by the operator.
- AWS CLI is installed; SAM CLI installation was verified by the operator.
- Local base image downloaded and Python version checked; no cloud resources
  created or application artifacts uploaded during these checks.
- Yra confirmed credits cover Amplify, Lambda, API Gateway, S3, ECR and CloudWatch
  and authorized one demo deployment in Oregon. Record usage/resources for his
  billing check. Oregon quota was checked: Total=10, Unreserved=10. Yra
  approved shared concurrency for the demo; the template no longer reserves it.
- Local Lambda-compatible bundle generation and configured-app verification
  passed (operator-run): saved readiness, two successful requests with distinct
  choices, one startup artifact load and fitting forbidden during serving.
  The template reuses the existing runtime role. The revised template validation
  and serving-image build passed in the operator terminal. The actual serving
  container also passed Lambda-emulator requests: saved readiness and two requests
  with distinct first/backup choices. This is local verification, not AWS startup.
- Created resource: private ECR `parksmart-backend` in Oregon, URI
  `684494100594.dkr.ecr.us-west-2.amazonaws.com/parksmart-backend`.
  Lambda image-pull policy was confirmed by Yra. Both the original and updated
  serving images were uploaded; digests and sizes are recorded in
  `docs/deployment_resources.md`. Continue sending proposed CloudFormation change
  sets to Yra **before execution**; do not use defaults that execute without review.
- The backend stack reached UPDATE_COMPLETE after the reviewed image-and-CORS
  update. `/readiness` returned HTTP 200 with saved predictions ready.
- The updated frontend is deployed through manual Amplify hosting. Public
  searches displayed first-choice and backup cards with matching map markers,
  and a shorter-walk preference search also succeeded. GitHub authorization is
  not configured for this manual deployment. See `docs/frontend_deployment.md`
  for update instructions; share verified URLs with Dylan and Hanrong.
- Dylan reported a successful public website check. Hosted alerts and failure-state
  checks remain pending; automated results are in the resource log.
- Routing is disabled, so hosted walking/driving routes are not verified. The
  first search after a long idle period has not been verified within the website's
  20-second timeout. Successful warm/incognito searches do not establish that
  cold-start result. Both hosted checks remain pending and need not be fixed or
  redeployed for this documentation review.

The six approved bundle objects were uploaded successfully under
`releases/issue33-lambda-2026-11-14/`, with AES256 and the manifest last. ECR
image upload and the subsequent application update completed; image digests and
sizes are recorded in `docs/deployment_resources.md`. The six S3 objects were
inspected: 24,210,536 bytes total, all AES256. The approved credit coverage is
reported by the account owner; actual usage remains subject to billing review.

## Generate and check the Lambda-compatible release locally

Docker Desktop must be running. SAM CLI is used later for template validation;
it is not needed for this artifact-generation command. From the repository root:

```bash
bash scripts/prepare_lambda_release.sh
```

The helper builds `infra/Dockerfile.release` for `linux/amd64` using the pinned
image above and model dependency versions documented in `docs/model_storage.md`.
Only source, the public registry and dependency files enter the build context.
Image pulls and Python package downloads require internet access during build.
The generation container runs with networking disabled, no AWS credentials,
a read-only mount of the existing analysis CSV, and a writable mount only for
`models/issue33/`. It never rebuilds the dataset or changes model selection.

It invokes the existing approved artifact generator, metadata-bound bundler and
backend release verifier. A successful result must show saved readiness, distinct
first/backup choices and one artifact load, with fitting forbidden during serving.
Training occurs only during this explicit offline preparation, never requests.
The new release is `models/issue33/issue33-lambda-2026-11-14/bundle/`, gitignored.
Existing releases are refused; after a failed or completed attempt, use a new ID:

```bash
bash scripts/prepare_lambda_release.sh issue33-lambda-2026-11-14-r2
```

Operator-run verification on 2026-11-14 passed using the real local dataset.
The release is `models/issue33/issue33-lambda-2026-11-14/bundle/`. Saved readiness
was ready; both requests returned `torrey-pines-center-north-ps` first and
`pangea-ps` as backup, with one artifact load and fitting forbidden during serving.
Routing was disabled and generation ran without networking. No objects were
uploaded. This verifies the preparation image, not Lambda invocation or live routing.
Stop on dependency-install, compatibility or readiness failure; do not bypass
version checks. The source checkout/hash provenance is recorded by the existing
generator; the container has no Git history and may record a null source commit.
Retain the reviewed checkout reference alongside the release metadata.

This is local preparation, not AWS deployment or verification of cloud costs.
Do not upload the image or generated files until the spending prerequisites,
permissions and release checks are satisfied. The final serving image must use
the same base digest and the generated dependency pins, then pass its own runtime
readiness checks; the preparation image alone does not verify Lambda invocation.

## Build the serving image locally

After successful release preparation, run from the repository root:

```bash
bash scripts/build_lambda_serving.sh
sam validate --lint --template-file infra/template.yaml --region us-west-2
```

The helper stages only the generated model dependency lock in ignored
`.lambda-build/`, then builds `parksmart-backend:issue33-lambda-2026-11-14` using
the pinned Lambda base and `linux/amd64`. It disables build provenance to avoid
an extra attestation image index for Lambda. It does not log in, push an image,
upload the bundle, or deploy resources. Build completion does not establish
runtime readiness: invoke the actual serving container locally next.
For a different prepared release, pass its ID as the helper's first argument.
For an application-code update that reuses the same model bundle, pass a new
image tag as the second argument:

```bash
bash scripts/build_lambda_serving.sh issue33-lambda-2026-11-14 issue33-ui-alerts-r2
```

This reuses the existing bundle's dependency lock without generating or training
a model, and builds `parksmart-backend:issue33-ui-alerts-r2` locally. Choose a new
tag for each application version before uploading to the immutable ECR repository.
Omitting the second argument keeps the original behavior: the image tag equals
the release ID. Neither form uploads or deploys anything.

The operator reported passing serving-image builds, SAM lint and local Lambda
invocations. The deployment preview below references an already uploaded image
by digest; it does not run `sam build` or rebuild/package an image. SAM build
metadata is retained for alternative tooling, not required by this workflow.
Track resources and verification in `docs/deployment_resources.md`.

### Invoke the serving container locally

From the repository root, start the verified release image in one terminal:

```bash
docker run --rm --name parksmart-lambda-local --platform linux/amd64 \
  --read-only --tmpfs /tmp:rw,size=512m -p 127.0.0.1:9000:8080 \
  --mount "type=bind,source=$PWD/models/issue33/issue33-lambda-2026-11-14/bundle,target=/bundle,readonly" \
  -e PARKSMART_ARTIFACT_PATH=/bundle/selected.pkl \
  -e PARKSMART_DATASET_PATH=/bundle/analysis_dataset.csv \
  -e PARKSMART_REGISTRY_PATH=/bundle/locations.json \
  -e PARKSMART_ROUTING_PROVIDER=none -e AWS_EC2_METADATA_DISABLED=true \
  parksmart-backend:issue33-lambda-2026-11-14
```

Keep it running. In a second terminal, from the repository root:

```bash
python3 scripts/check_lambda_local.py
```

The checker sends HTTP API v2 events through the local Lambda runtime emulator,
then checks saved readiness and two supported first/backup responses. It uses
only loopback, bypasses system proxies and prints a small summary. No AWS login,
credentials, S3 URI or cloud API is involved. The bundle is mounted read-only;
only temporary container storage is writable. Routing is disabled for this check.
The preparation verifier already checks one startup artifact load with fitting
forbidden; this separate check verifies actual serving-image request handling.
Stop with Ctrl+C after success. The operator supplied a passing checker result:
saved readiness, two recommendation requests, and distinct first/backup IDs
`torrey-pines-center-north-ps` and `pangea-ps`. External routing and S3 were not
involved in this local test.

### Initial change set uses the uploaded image

The template accepts `BackendImageUri` as a private ECR URI pinned by SHA-256
digest. It is required when DeploymentApproved=yes. For the verified release:

```text
684494100594.dkr.ecr.us-west-2.amazonaws.com/parksmart-backend@sha256:8dd0f74cd7efc3a0fa35ea6e5dd4045e3305b17311e165cdbdc4d52d6ab6deaf
```

Reference that uploaded image when preparing the initial change set. Do not
rebuild an image and assume it is the same tested digest. Build metadata remains
for deliberate future local builds, not as a requirement to rebuild this release.
SAM lint and the initial deployment completed successfully. The subsequent
reviewed update, `issue33-ui-cors-r1`, deployed image `issue33-ui-alerts-r1` and
the exact Amplify origin. Current image digests and verification results are
recorded in `docs/deployment_resources.md`. Future application updates should
use a new image tag, local verification, and a reviewed change-set preview
before execution. Routing remains disabled; successful preference checks do not
establish routed walking or driving support.

### Existing roles

`LambdaRuntimeRoleName` defaults to `ParkSmartLambdaRuntime`; SAM resolves its
ARN using the deployment account and AWS partition. This assumes a pathless
role, as named by the mentor; confirm its actual ARN before cloud deployment.
There is no generated execution role or inline IAM policy in this template.
The account owner manages trust, least-privilege S3 read access and CloudWatch
logging on the existing role. The separate `ParkSmartCloudFormationExecution`
role is supplied to the deployment command, not assigned as Lambda's role.
Do not modify either role or repository policy to work around AccessDenied;
send the exact error to Yra. ECR's Lambda pull policy is a separate checkpoint.

## Deployment parameter checklist — prepare before creating the change set

| Setting | Proposed value | Check before execution |
| --- | --- | --- |
| AWS account / region | `684494100594` / `us-west-2` | Successful CLI identity check; never assume the browser authenticates the terminal |
| Stack / ECR | `parksmart-backend` | Existing private repo, approved pull policy, immutable image tag/digest |
| Lambda runtime role | `ParkSmartLambdaRuntime` | Verify actual ARN/trust, S3 prefix read access and logging; retain existing role |
| CloudFormation execution role | `ParkSmartCloudFormationExecution` | Verify actual ARN and operator pass-role permission; supply as deployment role |
| ArtifactBucket | `parksmart-artifacts-684494100594` | Verify existing bucket region/privacy and approved upload access |
| ReleasePrefix | `releases/issue33-lambda-2026-11-14` | Match local manifest and successfully uploaded immutable release; publish manifest last |
| Serving image | Current deployed digest recorded in `docs/deployment_resources.md` | Use a new tag for future application updates; do not silently rebuild a different image during packaging |
| DeploymentApproved | Default `no`; reviewed deployment uses `yes` | Shared concurrency approved by Yra; deployment is invokable once created, so no separate reserved-concurrency activation gate remains |
| FrontendOrigins | `https://demo.d2ru7u75tkpr69.amplifyapp.com` | Configured and browser search verified; retain exact HTTPS origin, no wildcard or trailing slash |
| Routing | Currently `none` | Approve provider/configuration and limits before claiming working public routes |
| Frontend preferences | PR #37 merged; default and shorter-walk searches verified on the deployed website | Keep matching frontend/backend contracts; verify changed priority and max walk after future updates |

CLI login succeeded after the AWS CLI update; identity and repository-specific
ECR checks succeeded. Broad ECR listing is intentionally denied by scoped access;
use `describe-repositories --repository-names parksmart-backend`. The assigned S3 bucket was created by the operator after Yra confirmed it was
missing. HeadBucket confirms Oregon/expected owner; all four Block Public Access
settings returned true. Verify encryption and ownership before private uploads.

After bucket access is confirmed, verify immutable image/bundle uploads,
then prepare a nonexecuted change set using the existing execution role. Send
Yra the change-set name/link, exact proposed resources/parameters and current
resource inventory. Review replacements/deletions and unexpected IAM, storage or
network additions. Apply only after his review; do not use deployment defaults
that automatically execute it. Initial deployment and the combined image-and-origin
update were reviewed and approved by Yra, then executed successfully. Continue
obtaining review of future change-set previews before execution.

## Create an unexecuted CloudFormation preview

These commands document the current review workflow; they are not needed to
address this documentation-only PR feedback. Run from the repository root only
when preparing an approved deployment change. Local builds and ECR uploads must
already be checked. This workflow uses the uploaded digest directly: do not run
`sam build` or `sam deploy` as an intermediate step. The local template is sent
as the proposed configuration; CloudFormation does not build the Docker image.

### 1. Set the proposed configuration

The values below identify the existing demo. For a real application update,
replace the image URI with the new verified ECR digest and use a fresh change-set
name. For another account or release, replace the role, bucket, prefix and origin
with its approved values. These variables contain no credentials.

```bash
parksmart_region=us-west-2
parksmart_stack=parksmart-backend
parksmart_change_type=UPDATE
parksmart_changeset="issue33-preview-$(date -u +%Y%m%dT%H%M%SZ)"
parksmart_execution_role=arn:aws:iam::684494100594:role/ParkSmartCloudFormationExecution
parksmart_image_uri=684494100594.dkr.ecr.us-west-2.amazonaws.com/parksmart-backend@sha256:4b153ba7a6c605d6d6a293b38bc1b8d0f713103697f81a18de4f900f89d68748
parksmart_artifact_bucket=parksmart-artifacts-684494100594
parksmart_release_prefix=releases/issue33-lambda-2026-11-14
parksmart_runtime_role=ParkSmartLambdaRuntime
parksmart_frontend_origin=https://demo.d2ru7u75tkpr69.amplifyapp.com
```

UPDATE targets the existing stack. For an initial stack that does not yet exist,
set `parksmart_change_type=CREATE` instead. Do not use CREATE against the live
stack. Before an update, inspect the current parameters and preserve settings
that are not part of the intended change:

```bash
aws cloudformation describe-stacks \
  --stack-name "$parksmart_stack" \
  --region "$parksmart_region" \
  --query 'Stacks[0].{Status:StackStatus,Parameters:Parameters}' \
  --no-cli-pager
```

Skip that lookup for a genuinely new stack. It should not be treated as proof
that a denied console listing means a stack is missing.

### 2. Create the preview without executing it

```bash
aws cloudformation create-change-set \
  --stack-name "$parksmart_stack" \
  --change-set-name "$parksmart_changeset" \
  --change-set-type "$parksmart_change_type" \
  --template-body file://infra/template.yaml \
  --role-arn "$parksmart_execution_role" \
  --parameters \
    ParameterKey=DeploymentApproved,ParameterValue=yes \
    "ParameterKey=ArtifactBucket,ParameterValue=$parksmart_artifact_bucket" \
    "ParameterKey=ReleasePrefix,ParameterValue=$parksmart_release_prefix" \
    "ParameterKey=LambdaRuntimeRoleName,ParameterValue=$parksmart_runtime_role" \
    "ParameterKey=BackendImageUri,ParameterValue=$parksmart_image_uri" \
    "ParameterKey=FrontendOrigins,ParameterValue=$parksmart_frontend_origin" \
  --region "$parksmart_region" \
  --no-cli-pager
```

This submits a change-set preview using the existing execution role; it does not
apply resource changes. No IAM role, image build or private data upload is
performed by this command. The template's deployment gate is proposed as yes,
but the live stack remains unchanged until separate execution after review.

### 3. Wait, then inspect parameters and resource changes

```bash
aws cloudformation wait change-set-create-complete \
  --stack-name "$parksmart_stack" \
  --change-set-name "$parksmart_changeset" \
  --region "$parksmart_region"
```

```bash
aws cloudformation describe-change-set \
  --stack-name "$parksmart_stack" \
  --change-set-name "$parksmart_changeset" \
  --region "$parksmart_region" \
  --query '{Name:ChangeSetName,Id:ChangeSetId,Status:Status,Reason:StatusReason,ExecutionStatus:ExecutionStatus,Parameters:Parameters,Changes:Changes}' \
  --no-cli-pager
```

Run the inspection command even if the waiter fails, so StatusReason is visible.
A ready preview has CREATE_COMPLETE and ExecutionStatus AVAILABLE. Inspect the
full Changes entries for replacements/deletions, unexpected IAM or network
resources, the image digest, and exact origin. If the preview reports no changes,
confirm the proposed settings already match the deployment. No deployment action
is needed in that case. CloudFormation can mark such a preview FAILED with a
no-changes reason; this does not mean the running deployment failed. Send any
other failure's exact reason to Yra.

**Stop here. Send Yra the change-set name/ID and inspection output before
execution.** This preview section intentionally contains no execution command.
After approval, execution and stack completion are separate steps; verify saved
readiness before testing the website. Do not execute an older preview after a
new image or configuration is proposed.

## Understand the path

```text
Website / app → API Gateway HTTP API → Lambda / Mangum → FastAPI
                                            ├─ in-memory saved estimator + groups
                                            ├─ private S3 release bundle (cold start)
                                            └─ optional route provider (off initially)
Logs → CloudWatch; permissions → Lambda's IAM execution role
```

- **API Gateway** provides the HTTPS endpoint and forwards HTTP events to Lambda.
- **Lambda** runs the backend on invocation; a cold environment loads resources,
  then warm invocations reuse them. No per-request training or dataset builds.
- **Mangum** converts API Gateway events into FastAPI's ASGI calls. This adapter
  explicitly enters lifespan once and uses `lifespan="off"` on subsequent calls,
  preventing per-invocation resource setup/teardown. Each cold environment has its
  own model, cache and routing throttle; these are not shared across instances.
- **IAM role** is the existing mentor-managed runtime role. It must grant
  S3 GetObject within the release prefix and basic logging. The deployment operator needs separately approved permissions;
  do not put access keys in templates, images, Git or frontend VITE variables.
- **CloudWatch Logs** records cold-start errors and runtime diagnostics. Do not
  log requests, source counts, raw datasets or credential-bearing configuration.
- **S3** holds a private trusted release, not a public prediction endpoint.
  Checksums prevent mixing/corruption, not malicious pickle execution: only load
  team-prepared trusted artifacts from the approved private bucket/prefix.

The requested [API Gateway + Lambda introduction](https://docs.aws.amazon.com/apigateway/latest/developerguide/getting-started.html)
walks through creating an HTTP API, invoking it and cleanup. Read it now; do not
create its example cloud resources until access/allowances are approved.
Official references: [SAM function](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-function.html),
[SAM HTTP API](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-httpapi.html),
[Mangum adapter](https://mangum.fastapiexpert.com/adapter/),
[Mangum lifespan](https://mangum.fastapiexpert.com/lifespan/).

## Prepared files and defaults

- `template.yaml`: SAM image Lambda + HTTP API + seven-day log retention.
- `Dockerfile`: Python 3.12 Lambda container; copies source and public registry,
  not private CSVs, pickles, .env, local environments or notebooks.
- `requirements-lambda.txt`: serving-only libraries. Exact model dependency pins
  are generated from the trusted artifact, not guessed from example versions.
- `src/api/lambda_handler.py`: lazy cold-start adapter; imports do not contact AWS.
- `src/api/bundle.py`: downloads one S3 manifest and three checksummed files to
  `/tmp`, with atomic replacements and no uploads or embedded credentials.
- `DeploymentApproved=no` by default means no backend resources are created.
  Once approved and executed with yes, Lambda uses the shared account pool and
  can be invoked immediately; there is no reserved-concurrency zero gate.
- Routing defaults to `none`. A later reviewed demo configuration can enable an approved
  provider under `docs/routing.md` limits. No VPC/NAT, provisioned concurrency,
  public data bucket, persistent database or automatic paid service is configured.

The serving image build, SAM lint, local Lambda-emulator checks, AWS saved-model
startup and public website searches have passed operator checks. See
`docs/deployment_resources.md` for verification results and remaining limitations,
including cold-start latency. Issue #26 history is in `docs/issue26_handoff.md`.

## Existing compatible artifacts and earlier setup

For a previously prepared artifact, use the metadata-bound bundling instructions
in `docs/model_storage.md`. Issue #26 setup history is retained in
`docs/issue26_handoff.md`; use the current build and loopback-only invocation
example above for this demo. There is no second Docker/SAM deployment path here.

Python patch and model-library versions must match the pinned serving image.
Never edit compatibility metadata to bypass validation or train during Lambda
startup. If versions differ, prepare a new immutable release in the compatible
container, then check the actual serving image before upload. The Docker build
context permits the generated dependency lock, not private model/data files.

## Shared concurrency and demo safeguards

The operator checked Oregon's quota: Total=10 and Unreserved=10. This cannot
support the earlier positive reserved-concurrency setting. Yra approved using
the shared pool, so the template omits ReservedConcurrentExecutions entirely.
Do not request provisioned concurrency. A quota increase is optional and is not
a prerequisite for the shared-pool demo; coordinate any request with the owner.

The HTTP API stage retains rate 1 request/second and burst 2. Lambda retains a
30-second timeout and 1024 MB memory as initial settings; measure cloud startup,
request latency and Max Memory Used before calling these right-sized. Reduce
memory/timeout only after a successful measured readiness/search check. API
throttles and the account concurrency cap limit traffic/capacity, not total
spending; credits and billing alerts are not hard spending caps.

Yra confirmed credit coverage and approved one minimal-usage demo with shared
concurrency. The bucket was created and private uploads completed. Continue
tracking resources for the account owner's billing review; low usage, credits
and alerts do not guarantee zero out-of-pocket spend. New accounts or expanded
usage require their own verified allowances and approval. Never enable paid
upgrades or unapproved services.

CloudFormation rejects DeploymentApproved=yes with an empty ArtifactBucket.
A nonempty name alone does not prove bucket existence, privacy or access.


## Private S3 provisioning and reviewed deployment workflow

For a new deployment or release, first verify approval. Check the actual account,
region, credit/free-plan eligibility, intended request volume, storage/log/image
costs and cleanup plan first. Use [AWS Free Tier](https://aws.amazon.com/free/),
[Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/) and
[S3 pricing](https://aws.amazon.com/s3/pricing/) at deployment time. Budgets and
throttles are alerts/traffic controls, not hard guarantees of zero spend.

1. Work with Vivaan to choose a private existing bucket and immutable release
   prefix. Keep S3 Block Public Access enabled. An approved operator uploads the
   model, dataset, registry, release metadata and dependency lock, then
   manifest.json last: six objects in this release. Runtime downloads use the
   manifest and its three checked model/data/registry files; metadata and the lock
   support reproducibility. Use standard S3 AES256 encryption for this demo and
   conditional uploads that refuse replacement. Never upload .env or keys.
   If the bucket uses customer-managed KMS, review a narrowly scoped decrypt
   permission before deployment; the current template does not grant it.
2. Use role-based AWS access. The existing runtime role must have GetObject on only the approved
   release prefix; it needs no S3 list, write, public access or administrator permission.
   Registry and dataset are provisioned with the same manifest as the model,
   avoiding mismatched release files. Downloads run only on cold initialization.
3. Verify the exact allowed frontend origins. Account, region and bucket are
   parameters/operator configuration; no account ID or ARN is hardcoded.
4. Build and locally verify the serving image, push a new immutable tag to the
   approved private ECR repository, then record its full digest and size. Create
   a CloudFormation change set using the existing deployment role and digest-pinned
   BackendImageUri. Use CREATE for an initial stack and UPDATE for later changes.
   Application-only updates can use `--use-previous-template` and
   `UsePreviousValue=true` for parameters that must remain unchanged. Include
   DeploymentApproved, ArtifactBucket, ReleasePrefix, LambdaRuntimeRoleName,
   BackendImageUri and the exact FrontendOrigins in the reviewed configuration.
   Wait for change-set creation and inspect its parameters and resource changes.
   Follow the exact commands in [Create an unexecuted CloudFormation preview](#create-an-unexecuted-cloudformation-preview).
   Send the named preview to Yra, execute only after approval, and wait for the
   stack to complete before checking readiness. Shared concurrency means the
   function is invokable when created. Do not reuse another account's credentials.
5. For the approved short demo, capture the
   stack ApiUrl output and test `/health`, `/readiness`, `/locations` and a real
   POST `/recommendations`. Expect saved readiness and `is_example: false`.
   Configure Dylan's VITE_API_BASE_URL to that HTTPS URL in his source deployment,
   not by editing the synced frontend. App origin/base URL is separate setup.
6. Keep routing off until its rate/budget policy is reviewed. No key is bundled
   into the image/template; credentials, if approved, are backend-only through
   the role's secret-management path or controlled server configuration.
7. No user-auth authorizer is prepared in this initial template. Before exposing
   a persistent public deployment, agree on audience/authentication and abuse
   controls with the mentor. CORS alone is not authentication.

## Endpoint testing, logs and failures

Record actual deployment outputs, never assume a URL. API Gateway forwards the
same JSON shape used locally. Model errors give readiness/recommendations 503;
unsupported saved requests give predictions_unavailable rather than sample
results. CloudWatch log group is `/aws/lambda/<stack-function-name>`; use
`sam logs -n BackendFunction --stack-name <stack> --tail` with the approved profile
and region. Diagnostic logs include version/path errors, not raw input data.
Look for checksum failure, AccessDenied, missing objects, dependency mismatch,
no writable /tmp space, or cold-start timeout before changing model policy.
Warm requests must not repeat model loading/S3 reads/training. New environments
still have cold-start costs and the documented timeout/memory sizes are initial
pilot settings that must be measured, not promised latency.

## Cleanup and migration

For emergency shutdown, have the authorized owner throttle the function to
reserved concurrency zero, stop website traffic, then use
`sam delete --stack-name <stack>` with the correct approved account/region. Verify
Lambda, API Gateway and the explicit log group are removed. The existing
mentor-managed IAM roles are external to the stack and must be retained. Verify
remaining generated SAM deployment buckets/ECR repositories and delete approved
unused image artifacts separately. The private model bucket is external and is
not deleted by this stack; retain/delete its release objects only with the data
owner's approval. Check for remaining logs/images/storage charges afterward.

Moving to DS3's account means using its approved operator role, private bucket,
image repository, region and exact origins; code is unchanged. Rebuild/verify the
same approved dependency/image/model release instead of copying personal keys.
