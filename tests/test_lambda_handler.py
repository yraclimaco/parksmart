"""Warm-invocation lifecycle tests using an in-memory app, never AWS services."""

import json
from types import SimpleNamespace

from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.api import lambda_handler, saved_model


def event():
    return {
        "version": "2.0", "routeKey": "GET /health", "rawPath": "/health",
        "rawQueryString": "", "headers": {"host": "example.test"},
        "requestContext": {"stage": "$default", "requestId": "test",
                           "http": {"method": "GET", "path": "/health",
                                    "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"}},
        "isBase64Encoded": False,
    }


def test_warm_invocations_enter_lifespan_only_once(monkeypatch):
    calls = []

    @asynccontextmanager
    async def lifespan(app):
        calls.append("startup")
        yield
        calls.append("shutdown")

    app = FastAPI(lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    monkeypatch.setattr(saved_model, "create_configured_app", lambda: app)
    monkeypatch.setattr(lambda_handler, "_runtime", None)
    try:
        for _ in range(2):
            response = lambda_handler.handler(event(), SimpleNamespace())
            assert response["statusCode"] == 200
            assert json.loads(response["body"]) == {"status": "ok"}
        assert calls == ["startup"]
    finally:
        runtime = lambda_handler._runtime
        if runtime:
            runtime.loop.run_until_complete(runtime.lifespan.__aexit__(None, None, None))
            runtime.loop.close()


def test_failed_initialization_is_a_clear_503(monkeypatch):
    def fail():
        raise ValueError("Invalid configuration")
    monkeypatch.setattr(lambda_handler, "_runtime", None)
    monkeypatch.setattr(lambda_handler, "_start_runtime", fail)
    response = lambda_handler.handler(event(), SimpleNamespace())
    assert response["statusCode"] == 503
    assert "parking is full" in json.loads(response["body"])["detail"]
