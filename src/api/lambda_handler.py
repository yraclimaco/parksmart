"""API Gateway HTTP API adapter; resource startup happens once per cold process.

Mangum normally enters/exits lifespan on every invocation. This adapter enters
it once and disables Mangum's repeated lifespan cycle, retaining only in-memory
model/catalog/routing state for this execution environment. No AWS resources
are created or accessed merely by importing this module.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass
class _Runtime:
    adapter: Any
    loop: Any
    lifespan: Any  # Keep the entered context alive across warm invocations.


_runtime = None


def _start_runtime():
    """Return an initialized adapter and live lifespan without per-invoke fitting."""
    from mangum import Mangum
    from .saved_model import create_configured_app

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        app = create_configured_app()
        lifespan = app.router.lifespan_context(app)
        loop.run_until_complete(lifespan.__aenter__())
        return _Runtime(Mangum(app, lifespan="off"), loop, lifespan)
    except Exception:
        loop.close()
        raise


def handler(event, context):
    """Return an API Gateway proxy response for one event/context pair.

    AWS invokes one request at a time per execution environment. The first
    invocation initializes resources; warm invocations reuse them. Model failures
    handled by FastAPI return explicit 503s, never an automatic baseline fallback.
    """
    global _runtime
    if _runtime is None:
        try:
            _runtime = _start_runtime()
        except Exception:
            LOGGER.exception("Backend cold-start initialization failed")
            return {"statusCode": 503, "headers": {"content-type": "application/json"},
                    "body": json.dumps({"detail": "Backend initialization unavailable; "
                                        "check server logs. This does not mean "
                                        "parking is full."})}
    asyncio.set_event_loop(_runtime.loop)
    return _runtime.adapter(event, context)
