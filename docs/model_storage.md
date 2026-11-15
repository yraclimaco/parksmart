# Approved prediction release and S3 preparation — Issue #27

Historical averages remain the approved serving method from PR #23. Experiments
use separate outputs; none of the commands below overwrites `models/issue18/`.
This work is local preparation. No AWS bucket, IAM resource, S3 upload,
deployment or billing change was made.

## Reproduce an immutable local release

Use the project's installed environment and existing integrated dataset. From
the repository root, choose a new release ID for every generation:

```bash
python -m src.prepare_prediction_artifact --release-id issue27-2026-11-10
python -m scripts.prepare_serving_bundle --artifact models/issue27/issue27-2026-11-10/selected.pkl --metadata models/issue27/issue27-2026-11-10/metadata.json --output-dir models/issue27/issue27-2026-11-10/bundle --s3-prefix releases/issue27-2026-11-10
python -m scripts.verify_prediction_release --release-dir models/issue27/issue27-2026-11-10/bundle
```

The first command validates the CSV and registry, sorts records consistently,
fits the approved baseline on all validated records for serving, saves the v2
artifact and exercises its exact-version loader. It performs no candidate
selection or holdout evaluation. The second command checks metadata's artifact,
CSV and registry SHA-256 values before copying a matched bundle. Existing release
directories are rejected. Both commands support explicit dataset/registry paths;
artifact generation additionally supports `--output-root`.

Copied target hashes must still match those validated metadata values before
`manifest.json` is published. A source change during copying fails preparation.
The verification command checks bundle hashes and calls Daira's configured
backend with fitting patched to fail and routing disabled. It requires readiness
200, two successful supported recommendations with distinct choices, and exactly
one artifact load across startup and both requests. It prints summary values.

The manual `Prediction validation` GitHub Actions workflow runs the same public
source rebuild, experiments, release commands and full suite on Ubuntu 24.04.
After merge, select it under Actions and choose Run workflow. It is restricted
to public repositories, uses standard runner compute with no cache/artifact
storage, and prints aggregate results and metadata to public Actions logs.
The current workflow, after commit `a1da53f`, removes the encrypted release
export step. Its generated model/data files remain on the ephemeral runner;
use the commands above to retain a release in an allowed local/container
environment. This describes the current workflow, not the earlier verification
run described below.

`metadata.json` records training dates, reading count, survey times, support
policy, artifact format, model identity, exact Python/numpy/pandas/scikit-learn/
scipy/joblib versions, input hashes and reproduction-source hashes. The generated
`requirements-model.txt` pins those five packages; Python's exact patch version
is recorded separately in metadata. API dependencies remain in requirements.txt.
The model's parameters and predictions reproduce from identical data, source and
versions; preparation timestamps and pickle bytes are not a cross-platform
reproducibility guarantee. Keep these files private and gitignored.

The optional source commit is a checkout reference, not a claim of a clean tree.
Source content hashes identify the code actually used, including uncommitted
changes. Preserve the reviewed commit and those hashes with the release.

For Lambda, run generation in the reviewed Linux/Python 3.12 image and install
the generated model pins there. A locally generated Python 3.15 artifact does not
meet the Lambda Python 3.12 compatibility requirement. Do not edit version
metadata to make a loader accept incompatible artifacts. The existing Docker
validation and image-pinning steps are in [infra/README.md](../infra/README.md).

## Release layout

The contents of `bundle/` map directly to one private S3 prefix:

```text
s3://<private-bucket>/releases/<release-id>/
  selected.pkl           # trusted fitted service, never uploaded by clients
  analysis_dataset.csv   # required once to construct current recommendation groups
  locations.json         # exact matched registry
  metadata.json          # input/source hashes, model identity and versions
  requirements-model.txt # model dependency lock; Python version is in metadata
  manifest.json          # publish last; hashes/keys for the three serving files
```

The v1 manifest's `files` contract stays artifact/dataset/registry, so Daira's
merged loader needs no interface change. Optional `release_metadata` binds the
reproduction metadata for human release review; the runtime does not fetch it.
Use a fresh prefix for a new release and retain the previous working prefix for
rollback. A release ID is an application version; it does not enable S3 bucket
versioning or Object Lock.

## S3 concepts and account limits

An S3 bucket is a regional object container. A key such as
`releases/issue27-2026-11-10/selected.pkl` identifies an object; its slash prefix
is a naming convention. The backend reads objects into local storage before
loading the estimator. S3 itself does not run inference. The
[S3 introduction](https://docs.aws.amazon.com/AmazonS3/latest/userguide/GetStartedWithS3.html)
explains creating, uploading, downloading and deleting objects; reading it does
not require creating its example resources.

Checked AWS documentation on 2026-11-10. For new eligible accounts, the current
Free plan provides $100 initial credits and up to $100 additional credits; it
ends after six months or credit exhaustion. Paid plans can incur charges beyond
credits. Joining AWS Organizations can automatically upgrade a Free plan.
The team's account age, plan, remaining credits and applicable allowances are
unverified. Confirm them with the account owner before Week 7 deployment; do
not upgrade plans or enable paid usage. Credits are not a blanket guarantee that
the proposed stack is free. See [AWS plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

Keep bucket/account Block Public Access enabled and use bucket-owner-enforced
ownership with ACLs disabled. Use the existing private bucket in the backend's
region; no public website bucket is needed for these files. See
[S3 security guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).
SSE-S3 encrypts new objects automatically without an extra encryption fee;
storage, requests and transfer still need allowance checks. These instructions
request AES256 explicitly and do not provision KMS keys. See
[SSE-S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingServerSideEncryption.html).

## Later upload procedure — do not run during preparation

After the account owner verifies allowances and Yra approves deployment:

1. Recreate and test the release in the exact backend image, review its hashes
   and pins, and choose an unused prefix matching `--s3-prefix` in its manifest.
2. Use an approved short-lived operator identity with `s3:PutObject` restricted
   to that prefix. Keep this identity separate from the backend reader role.
3. Upload each of `selected.pkl`, `analysis_dataset.csv`, `locations.json`,
   `metadata.json` and `requirements-model.txt` using the command template below.
   Stop on any failure. Publish `manifest.json` only after all five succeed.
4. Download/check the release through the configured backend, verify readiness
   and a supported recommendation, then retain the previous release URI for
   rollback. Do not configure the new manifest while its upload is incomplete.

Template (replace placeholders; not an executed command):

```bash
aws s3api put-object --bucket <private-bucket> --key releases/<release-id>/<filename> --body models/issue27/<release-id>/bundle/<filename> --if-none-match "*" --server-side-encryption AES256 --storage-class STANDARD --region <approved-region>
```

`If-None-Match: *` rejects an existing object instead of overwriting it. After a
partial upload, investigate and use a new release prefix; do not remove the
condition to force an overwrite. The [conditional-write guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
documents this behavior and required `s3:PutObject` access. No cloud command is
needed to prepare or test the local bundle.

## Daira's startup contract and permissions

The existing configured factory loads a compatible trusted artifact once at
FastAPI lifespan startup. Set these nonsecret paths in PowerShell for a local
release (use equivalent environment settings on other systems):

```powershell
$env:PARKSMART_ARTIFACT_PATH = "models/issue27/issue27-2026-11-10/bundle/selected.pkl"
$env:PARKSMART_DATASET_PATH = "models/issue27/issue27-2026-11-10/bundle/analysis_dataset.csv"
$env:PARKSMART_REGISTRY_PATH = "models/issue27/issue27-2026-11-10/bundle/locations.json"
$env:PARKSMART_MODEL_MODE = "saved"
$env:PARKSMART_APPROVED_MODEL = "historical_average"
$env:PARKSMART_ROUTING_PROVIDER = "none"
Remove-Item Env:PARKSMART_BUNDLE_MANIFEST -ErrorAction SilentlyContinue
python -m uvicorn src.api.saved_model:create_configured_app --factory
```

For the later S3 path, set `PARKSMART_BUNDLE_MANIFEST` to the exact
`s3://<private-bucket>/releases/<release-id>/manifest.json` URI and
`PARKSMART_CACHE_DIR=/tmp/parksmart` on Lambda. The bundle overrides individual
local paths. Supply the region using deployment settings and grant the execution
role `s3:GetObject` on `arn:aws:s3:::<private-bucket>/releases/<release-id>/*`.
The reader uses explicit keys and needs no `ListBucket`, write or delete access.
Keep bucket policies compatible with the role. This is the standard
[IAM object-prefix policy pattern](https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-policies-s3.html).
Only trusted team identities may write pickle releases; checksums establish
integrity, not safety of an untrusted pickle. No endpoint accepts model uploads.

`materialize_bundle` verifies hashes before reuse/download and avoids mixing
releases. A cold process fetches the manifest and three required files; warm
requests reuse the loaded estimator and groups. `/health` checks liveness;
`/readiness` is 200 only with working predictions/catalog. Missing, corrupt,
wrong-model or incompatible local artifacts leave readiness/recommendations
503 without fitting a fallback. Bundle download/checksum failures stop factory
initialization and the Lambda wrapper returns 503. Unsupported requests remain
unknown under `PredictionService.support_labels`.

Offline checks use generated data and a stub S3 client, including missing and
incompatible artifacts, bad checksums and repeated requests with fitting disabled:

```bash
python -m pytest tests/test_prepare_prediction_artifact.py tests/test_prepare_serving_bundle.py tests/test_serving_configuration.py tests/test_serving_bundle.py tests/test_lambda_handler.py -q
```

Verified on November 10 in
[Linux run 42784254791](https://github.com/yraclimaco/parksmart/actions/runs/42784254791)
at source commit `c8ac676`: 42 targeted tests and the full **918 tests plus 39
subtests passed**. The real 76,102-reading release passed the backend verifier:
readiness 200, two requests with distinct choices and one startup artifact load,
with fitting forbidden. The private release is
`models/issue27/issue27-2026-11-10/`; its bundled metadata records the hashes.
Its exact model environment is Python 3.12.10, numpy 2.5.4, pandas 3.1.1,
scikit-learn 1.9.1, scipy 1.18.1 and joblib 1.6.0.

On November 10, local Windows Application Control blocked native imports in
both Python 3.15 and Python 3.12 environments; no security settings were changed.
That day's tests and real-data serving ran on the standard Linux runner.
Earlier run `42784254791`
at `c8ac676` printed the recipient-encrypted release into **public Actions
logs**. The ciphertext was publicly logged and checked locally against the
runner's ZIP checksum; it was not privately transmitted. The absence of an
Actions artifact upload does not mean that those logs were private. Yra/the
user will delete the earlier run and logs; deletion is pending and has not
been confirmed. The current workflow after `a1da53f` no longer exports the
encrypted release and prints only aggregate results and metadata. Regenerate
in the exact intended Lambda image before cloud deployment; a Linux runner is
not Lambda validation.

Review revision checks on November 13, 2026 ran locally in Windows/Python 3.12.10:
40 affected prediction tests and the full **921 tests plus 39 subtests passed**
(38 warnings in the full suite). The fixed-boundary real-data rerun reproduced
the existing validation results. No saved artifact was replaced, no new Actions
export was run, and deletion of the earlier public logs is still unconfirmed.

This provides a concrete handoff to Daira's merged backend. It does not claim a
new joint teammate session or cloud verification. Runtime/backend preparation
and cleanup remain documented in [Issue #26 handoff](issue26_handoff.md) and
[infra/README.md](../infra/README.md).
