# Preparation only: no image is built/pushed by adding this file.
# Pin the reviewed base image digest before deployment. Artifact Python patch
# version must match this image exactly; /readiness rejects incompatible models.
ARG LAMBDA_BASE_IMAGE=public.ecr.aws/lambda/python:3.12
FROM ${LAMBDA_BASE_IMAGE}
COPY infra/requirements-lambda.txt /tmp/requirements-lambda.txt
COPY .serving-bundle/requirements-model.txt /tmp/requirements-model.txt
RUN python -m pip install --no-cache-dir \
    -r /tmp/requirements-lambda.txt -r /tmp/requirements-model.txt \
    --target ${LAMBDA_TASK_ROOT}
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY config/locations.json ${LAMBDA_TASK_ROOT}/config/locations.json
CMD ["src.api.lambda_handler.handler"]
