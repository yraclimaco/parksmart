# AWS backend preparation — Issue #26

**Preparation only. No deployment or AWS calls were performed.** Week 7 deployment
requires verified DS3 account access, mentor approval and checked allowances.
Do not enable paid usage, switch billing plans, provision NAT, or run cloud commands
below merely to prepare for the local demo. Nothing here is a spending guarantee.

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
- **IAM role** grants this Lambda only S3 GetObject within the release prefix and
  basic logging. The deployment operator needs separately approved permissions;
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
- `DeploymentApproved=no` by default means no backend resources are created by
  the template. Reserved concurrency defaults to zero (invocations disabled).
  Keep both gates closed until cloud use is actually approved.
- Routing defaults to `none`. A later one-instance pilot can enable a reviewed
  provider under `docs/routing.md` limits. No VPC/NAT, provisioned concurrency,
  public data bucket, persistent database or automatic paid service is configured.

These files are initial configuration, **not yet container-built/SAM-validated
or deployed**. Local Python checks and DS3 review are complete; current results
and commands are in `docs/issue26_handoff.md`. Python tests do not establish
container compatibility or successful AWS deployment.

## Prepare a private release locally

First complete the saved-artifact demo in `docs/issue26_handoff.md`. Existing
artifact Python/numpy/pandas/sklearn/scipy/joblib versions must match exactly.
After installing the agreed requirements, this command copies already prepared
files and checks the dataset registry mapping; it never trains or uploads:

```bash
python -m scripts.prepare_serving_bundle --s3-prefix releases/demo-2026-11-05
```

It creates the ignored `.serving-bundle/` directory with selected.pkl,
analysis_dataset.csv, locations.json, manifest.json and requirements-model.txt.
It refuses to overwrite an existing output directory. Keep it private and out of
Git. The manifest contains hashes, model name and exact dependency versions.
Use a new immutable prefix for each approved release. Record the approved model
identity and artifact hash with Vivaan before provisioning it.

For local build validation, with Docker and SAM CLI installed:

```bash
docker build --platform linux/amd64 -f infra/Dockerfile -t parksmart-backend:local .
docker run --rm --platform linux/amd64 --entrypoint python parksmart-backend:local -c 'import platform; print(platform.python_version())'
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml
```

The template targets x86_64; the explicit linux/amd64 Docker platform matches
that target, including on Apple Silicon hosts. These commands have not been run
in this review environment. Before deployment, pin the reviewed base-image digest
using the Dockerfile's LAMBDA_BASE_IMAGE build argument and validate the identical
image/model release through SAM. Do not assume the mutable Python tag is compatible.

The .dockerignore allowlist permits only the generated dependency lock from the
private bundle into the image context; the model/data files stay out. Run the
container locally with the bundle mounted read-only and explicit local file
paths to verify readiness. No S3 access is needed for that check:

```bash
docker run --rm --platform linux/amd64 -p 9000:8080 -v "$PWD/.serving-bundle:/bundle:ro" \
  -e PARKSMART_ARTIFACT_PATH=/bundle/selected.pkl \
  -e PARKSMART_DATASET_PATH=/bundle/analysis_dataset.csv \
  -e PARKSMART_REGISTRY_PATH=/bundle/locations.json \
  -e PARKSMART_ROUTING_PROVIDER=none parksmart-backend:local
```

Use Lambda's runtime invocation endpoint on localhost:9000 with a documented
API Gateway v2 event (see tests/test_lambda_handler.py), not `/readiness` directly.
`sam local start-api --template .aws-sam/build/template.yaml` provides an HTTP
frontend when supplied equivalent reviewed local environment overrides. Do not
use real AWS credentials for a local invocation whose inputs are local paths.

**Compatibility:** Python patch version must also match the artifact. If the
Lambda base image differs from the Mac environment, do not edit the artifact's
version envelope. Pin a reviewed base-image digest and reproduce the artifacts
in that exact serving environment using Vivaan's existing offline training
command. This requires the dataset mounted locally; never train on Lambda cold
start. Pin the generated dependency lock and image identity for that release.
The saved loader enforces compatibility and readiness stays unavailable on
mismatch. Do not upload/deploy a release until the container readiness passes.

## Reserved concurrency prerequisite — check before enabling

Reserved concurrency is a per-function capacity reservation and limit, not a
cost guarantee. Lambda requires at least 100 concurrency units to remain
unreserved. Before enabling ReservedConcurrency=1, an approved operator must
check the target account AND region in Lambda's account settings/Service Quotas,
or use this read-only command with their approved profile:

```bash
aws lambda get-account-settings --profile <approved-profile> --region <approved-region>
```

Inspect AccountLimit.ConcurrentExecutions and UnreservedConcurrentExecutions.
There must be room to reserve one unit while leaving at least 100 unreserved;
account for existing reservations and recheck immediately before deployment.
Small/new accounts may not have sufficient quota. If unsupported, leave
DeploymentApproved=no and ReservedConcurrency=0, keep using the local demo,
and ask the mentor/account owner to resolve quota eligibility or approve a
revised deployment design. Do not remove the limit to bypass this prerequisite
or enable paid usage. These checks have not been performed for a DS3 account.

References: [reserved concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html),
[account settings](https://docs.aws.amazon.com/cli/latest/reference/lambda/get-account-settings.html).
CloudFormation also rejects DeploymentApproved=yes with an empty ArtifactBucket;
the disabled preparation template can retain the empty default.

## Later: approved private S3 provisioning and deployment

Do not execute this section during preparation. Check the actual DS3 account,
region, credit/free-plan eligibility, intended request volume, storage/log/image
costs and cleanup plan first. Use [AWS Free Tier](https://aws.amazon.com/free/),
[Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/) and
[S3 pricing](https://aws.amazon.com/s3/pricing/) at deployment time. Budgets and
throttles are alerts/traffic controls, not hard guarantees of zero spend.

1. Work with Vivaan to choose a private existing bucket and immutable release
   prefix. Keep S3 Block Public Access enabled. An approved operator uploads the
   three prepared files, then manifest.json last. Never upload .env or keys.
   If the bucket uses customer-managed KMS, review a narrowly scoped decrypt
   permission before deployment; the current template does not grant it.
2. Use role-based AWS access. The Lambda role has GetObject on only that release
   prefix; it needs no S3 list, write, public access or administrator permission.
   Registry and dataset are provisioned with the same manifest as the model,
   avoiding mismatched release files. Downloads run only on cold initialization.
3. Verify the exact allowed frontend origins. Account, region and bucket are
   parameters/operator configuration; no account ID or ARN is hardcoded.
4. After explicit deployment approval, use `sam deploy --guided` with the built
   image template and an approved image repository. Supply DeploymentApproved=yes,
   ArtifactBucket, ReleasePrefix, and FrontendOrigins, initially leaving
   ReservedConcurrency=0. Review the proposed changeset before executing it.
   Never apply this template to another account by reusing personal credentials.
5. For the approved short pilot only, enable ReservedConcurrency=1, capture the
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

Disable invocations (reserved concurrency zero), stop website traffic, then use
`sam delete --stack-name <stack>` with the correct approved account/region. Verify
Lambda, API Gateway, IAM role and the explicit log group are removed. Verify
remaining generated SAM deployment buckets/ECR repositories and delete approved
unused image artifacts separately. The private model bucket is external and is
not deleted by this stack; retain/delete its release objects only with the data
owner's approval. Check for remaining logs/images/storage charges afterward.

Moving to DS3's account means using its approved operator role, private bucket,
image repository, region and exact origins; code is unchanged. Rebuild/verify the
same approved dependency/image/model release instead of copying personal keys.
