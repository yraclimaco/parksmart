"""Check the local Lambda runtime emulator; never contact an AWS endpoint.

Uses only Python's standard library and prints readiness and location IDs,
not datasets, artifacts, credentials or raw prediction responses.
"""

import json
from urllib.request import Request, build_opener, ProxyHandler

INVOCATION_URL = "http://127.0.0.1:9000/2015-03-31/functions/function/invocations"
SMOKE_REQUEST = {
    "destination": {"name": "Geisel Library", "coordinates": {
        "latitude": 32.8811, "longitude": -117.2376}},
    "arrival_time": "2026-11-03T10:00:00-08:00",
    "permit_type": "S", "starting_location": None,
}


def invoke(method, path, payload=None):
    """Invoke an HTTP API v2 fixture locally; return the successful API body."""
    event = {
        "version": "2.0", "routeKey": f"{method} {path}", "rawPath": path,
        "rawQueryString": "", "headers": {
            "host": "localhost", "content-type": "application/json"},
        "requestContext": {"stage": "$default", "requestId": "local-check",
                           "http": {"method": method, "path": path,
                                    "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"}},
        "isBase64Encoded": False,
    }
    if payload is not None:
        event["body"] = json.dumps(payload)
    request = Request(INVOCATION_URL, data=json.dumps(event).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
    # Bypass any system HTTP proxy: this check must stay on loopback.
    with build_opener(ProxyHandler({})).open(request, timeout=120) as response:
        envelope = json.load(response)
    if envelope.get("statusCode") != 200:
        raise RuntimeError(f"{path} failed; inspect local container logs. "
                           f"API status: {envelope.get('statusCode', 'missing')}")
    return json.loads(envelope["body"])


def main():
    """Check saved readiness and two recommendations through the real adapter."""
    ready = invoke("GET", "/readiness")
    if ready.get("status") != "ready" or ready.get("prediction_mode") != "saved":
        raise RuntimeError("Local runtime must report ready in saved mode")
    choices = []
    for _ in range(2):
        result = invoke("POST", "/recommendations", SMOKE_REQUEST)
        if result.get("status") != "ready" or result.get("is_example") is not False:
            raise RuntimeError("Local runtime did not return a real ready result")
        first, backup = result.get("first_choice"), result.get("backup_choice")
        if not first or not backup:
            raise RuntimeError("This release smoke check needs two suitable choices")
        ids = [choice["location"]["location_id"] for choice in (first, backup)]
        if ids[0] == ids[1]:
            raise RuntimeError("First choice and backup must be distinct")
        choices.append(ids)
    print(json.dumps({"readiness": ready, "recommendation_requests": len(choices),
                      "choices": choices, "target": "local Lambda emulator"}, indent=2))


if __name__ == "__main__":
    main()
