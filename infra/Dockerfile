# Preparation only: no image is built/pushed by adding this file.
# Pinned to the locally verified linux/amd64 Python 3.12.16 base.
# Artifacts must match the exact runtime/dependencies; readiness enforces this.
ARG LAMBDA_BASE_IMAGE=public.ecr.aws/lambda/python@sha256:696fcc2a052fc8f335f9b34c6ec4e50ad54dbe5dd35134ec997c4f97bd150b22
FROM ${LAMBDA_BASE_IMAGE}
COPY infra/requirements-lambda.txt /tmp/requirements-lambda.txt
ARG MODEL_REQUIREMENTS_FILE=.serving-bundle/requirements-model.txt
COPY ${MODEL_REQUIREMENTS_FILE} /tmp/requirements-model.txt
RUN python -m pip install --no-cache-dir \
    -r /tmp/requirements-lambda.txt -r /tmp/requirements-model.txt \
    --target ${LAMBDA_TASK_ROOT}
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY config/locations.json ${LAMBDA_TASK_ROOT}/config/locations.json
CMD ["src.api.lambda_handler.handler"]
