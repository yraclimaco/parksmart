"""Match published UCSD construction geometry to trip points, without routing.

The public ArcGIS service is queried in WGS84; native State Plane coordinates
are never treated as longitude/latitude. Missing relevance information produces
a partial result rather than a claim that no construction affects the trip.
"""

import math
import time
from dataclasses import asdict
from datetime import datetime, time as day_time, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

from .cache import SourceError
from .contracts import ProviderResult
from .http import SOURCE_BUDGET_SECONDS

SOURCE_NAME = "UC San Diego construction alerts"
SOURCE_URL = (
    "https://admin-enterprise-gis.ucsd.edu/server/rest/services/Construction/"
    "Construction_Alert_Approved/MapServer"
)
LAYERS = {0: "esriGeometryPoint", 1: "esriGeometryPolyline", 2: "esriGeometryPolygon"}
QUERY_FIELDS = (
    "objectid,AlertID,AlertType,Comment,Status,Project_Alert_Status,Subject,"
    "Project_Name,Alert_Start_Date,Alert_End_Date,Public_Impact_Date,"
    "Public_Impact_End_Date,Public_URL_Link_To_Map"
)
CACHE_KEY = "ucsd-approved-construction-v1"
CACHE_TTL_SECONDS = 600
MAX_STALE_SECONDS = 86400
PAGE_SIZE = 500  # Below the inspected service's 2,000-record transfer limit.
MAX_PAGES_PER_LAYER = 4
MAX_TOTAL_FEATURES = 2000
MAX_GEOMETRY_VERTICES = 5000
MAX_MESSAGE_CHARACTERS = 600  # Shared TripAlert HTTP schema limit.
MAX_NOTICE_ID_CHARACTERS = 255  # Inspected ArcGIS AlertID field length.
PROXIMITY_METERS = 200.0
BOUNDARY_TOLERANCE_METERS = 0.001  # Numerical boundary tolerance, one millimetre.
EARTH_RADIUS_METERS = 6371008.8
LA = ZoneInfo("America/Los_Angeles")
INACTIVE_STATUSES = {
    "inactive", "cancelled", "canceled", "closed", "complete", "completed",
    "rejected", "withdrawn", "deleted", "not approved", "expired",
}
APPROVED_STATUSES = {"approved", "active"}
MATCH_LIMITATION = (
    "Matches trip points, not the full driving or walking route; no closure "
    "or rerouting is inferred."
)
COVERAGE_LIMITATION = (
    "Only the published construction map was checked; missing notices or "
    "unmapped impacts may exist."
)
UNKNOWN_LIMITATION = (
    "Some published records lacked usable dates, status or geometry; "
    "construction relevance could not be checked completely."
)


def _wgs84(reference):
    if not isinstance(reference, dict):
        return False
    codes = [reference[key] for key in ("wkid", "latestWkid") if key in reference]
    return bool(codes) and all(code == 4326 for code in codes)


def _coordinate(value):
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError("Missing geometry coordinate")
    x, y = value[:2]
    if (isinstance(x, bool) or isinstance(y, bool)
            or not isinstance(x, (int, float)) or not isinstance(y, (int, float))
            or not math.isfinite(x) or not math.isfinite(y)
            or not -180 <= x <= 180 or not -90 <= y <= 90):
        raise ValueError("Invalid WGS84 coordinate")
    return x, y


def _parts(geometry, kind):
    if not isinstance(geometry, dict):
        raise ValueError("Missing geometry")
    if "spatialReference" in geometry and not _wgs84(geometry["spatialReference"]):
        raise ValueError("Geometry is not WGS84")
    if kind == "esriGeometryPoint":
        return [[_coordinate([geometry.get("x"), geometry.get("y")])]]
    key = "paths" if kind == "esriGeometryPolyline" else "rings"
    raw = geometry.get(key)
    if not isinstance(raw, list) or not raw:
        raise ValueError("Missing geometry parts or unsupported true curves")
    if any(not isinstance(part, list) for part in raw):
        raise ValueError("Invalid geometry parts")
    if sum(map(len, raw)) > MAX_GEOMETRY_VERTICES:
        raise ValueError("Geometry is too complex")
    result = [[_coordinate(point) for point in part] for part in raw]
    minimum = 2 if key == "paths" else 4
    if any(len(part) < minimum for part in result):
        raise ValueError("Incomplete geometry")
    if key == "rings" and any(part[0] != part[-1] for part in result):
        raise ValueError("Polygon rings must be closed")
    return result


def _segment_distance(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominator = dx * dx + dy * dy
    fraction = (max(0.0, min(1.0, -(a[0] * dx + a[1] * dy) / denominator))
                if denominator else 0.0)
    return math.hypot(a[0] + fraction * dx, a[1] + fraction * dy)


def _match(parts, kind, target):
    # A local tangent-plane approximation is sufficient for this 200 m campus
    # proximity advisory. It is not a route distance or surveyed access boundary.
    cosine = math.cos(math.radians(target.latitude))
    projected = [[(
        math.radians(x - target.longitude) * EARTH_RADIUS_METERS * cosine,
        math.radians(y - target.latitude) * EARTH_RADIUS_METERS,
    ) for x, y in part] for part in parts]
    if kind == "esriGeometryPoint":
        distance = math.hypot(*projected[0][0])
    else:
        distance = min(_segment_distance(a, b) for part in projected
                       for a, b in zip(part, part[1:]))
    if distance <= BOUNDARY_TOLERANCE_METERS:
        return "intersects_geometry"
    if kind == "esriGeometryPolygon":
        # Even-odd membership includes disjoint shells and excludes holes,
        # independent of Esri ring orientation. A bounding box is insufficient.
        inside = False
        for ring in projected:
            for a, b in zip(ring, ring[1:]):
                if ((a[1] > 0) != (b[1] > 0)
                        and (a[0] + (b[0] - a[0]) * -a[1] / (b[1] - a[1])) > 0):
                    inside = not inside
        if inside:
            return "intersects_geometry"
    return "within_200m" if distance <= PROXIMITY_METERS else None


def _epoch(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError("Missing source date")
    try:
        return datetime.fromtimestamp(value / 1000, timezone.utc)
    except (ValueError, OverflowError, OSError) as error:
        raise ValueError("Invalid source date") from error


def _window(attributes):
    limitations = []
    for start_key, end_key in (
        ("Public_Impact_Date", "Public_Impact_End_Date"),
        ("Alert_Start_Date", "Alert_End_Date"),
    ):
        try:
            start = _epoch(attributes.get(start_key))
            end = _epoch(attributes.get(end_key))
            if end < start:
                raise ValueError("Reversed source dates")
        except ValueError:
            continue
        if start_key == "Alert_Start_Date":
            limitations.append(
                "Public-impact dates unavailable; using the published "
                "alert-date window.")
        if end.astimezone(LA).time() == day_time.min:
            following_date = end.astimezone(LA).date() + timedelta(days=1)
            end = datetime.combine(following_date, day_time.min, LA).astimezone(
                timezone.utc)
            limitations.append(
                "Midnight end dates are included through that Los Angeles calendar "
                "date; exact work hours are unverified.")
        return start, end, limitations
    return None


def _status(attributes):
    values = [str(attributes.get(key) or "").strip().casefold()
              for key in ("Status", "Project_Alert_Status")]
    if any(value in INACTIVE_STATUSES for value in values):
        return "inactive"
    return ("approved" if all(value in APPROVED_STATUSES for value in values)
            else "unknown")


def _source_link(attributes, layer):
    value = attributes.get("Public_URL_Link_To_Map")
    if isinstance(value, str):
        try:
            parsed = urlsplit(value)
            hostname = (parsed.hostname or "").lower()
            if (parsed.scheme == "https" and not parsed.username and not parsed.password
                    and (hostname == "ucsd.edu" or hostname.endswith(".ucsd.edu"))):
                return value
        except ValueError:
            pass
    return f"{SOURCE_URL}/{layer}/query?" + urlencode({
        "f": "pjson", "where": f"objectid={attributes['objectid']}",
        "outFields": QUERY_FIELDS, "returnGeometry": "true", "outSR": 4326,
    })


class _TextExtractor(HTMLParser):
    """Read source excerpts as text and discard script/style content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _text(value):
    parser = _TextExtractor()
    parser.feed(str(value or ""))
    parser.close()
    return " ".join(" ".join(parser.parts).split())


class ConstructionProvider:
    """Cache official approved map features and match them to an arrival/trip.

    Args:
        http: Shared JSONHTTP transport with bounded source deadlines.
        cache: Shared CachedJSON; raw features are reused across trip requests.
        utcnow: Optional aware UTC clock, retained for provider test injection.
    """

    def __init__(self, http, cache, utcnow=None):
        self.http, self.cache = http, cache
        self.utcnow = utcnow or (lambda: datetime.now(timezone.utc))

    def _load(self):
        deadline = time.monotonic() + SOURCE_BUDGET_SECONDS
        records = []
        for layer, kind in LAYERS.items():
            offset, seen = 0, set()
            for _ in range(MAX_PAGES_PER_LAYER):
                if time.monotonic() >= deadline:
                    raise SourceError("Construction source budget expired")
                page = self.http.get_json(f"{SOURCE_URL}/{layer}/query", params={
                    "f": "json", "where": "1=1", "outFields": QUERY_FIELDS,
                    "returnGeometry": "true", "returnTrueCurves": "false",
                    "outSR": 4326, "orderByFields": "objectid ASC",
                    "resultOffset": offset, "resultRecordCount": PAGE_SIZE,
                }, deadline=deadline)
                if (not isinstance(page, dict) or "error" in page
                        or not isinstance(page.get("features"), list)
                        or page.get("geometryType") != kind
                        or not _wgs84(page.get("spatialReference"))):
                    raise SourceError("Construction response incomplete or unprojected")
                features = page["features"]
                exceeded = page.get("exceededTransferLimit", False)
                if not isinstance(exceeded, bool) or (exceeded and not features):
                    raise SourceError("Construction pagination is incomplete")
                for feature in features:
                    attributes = (feature.get("attributes")
                                  if isinstance(feature, dict) else None)
                    identity = (attributes.get("objectid")
                                if isinstance(attributes, dict) else None)
                    if (isinstance(identity, bool)
                            or not isinstance(identity, (str, int))
                            or identity == "" or identity in seen):
                        raise SourceError(
                            "Construction feature IDs missing or repeated")
                    seen.add(identity)
                    records.append((layer, feature))
                    if len(records) > MAX_TOTAL_FEATURES:
                        raise SourceError("Construction feature bound exceeded")
                if not exceeded:
                    break
                offset += len(features)
            else:
                raise SourceError("Construction page bound exceeded")
        if time.monotonic() >= deadline:
            raise SourceError("Construction source budget expired")
        return records

    def get(self, arrival, targets):
        """Return source-attributed notices relevant to an aware arrival and points.

        Args:
            arrival: Aware datetime; date-only windows use Los Angeles dates.
            targets: AlertTarget parking/destination coordinates; labels are not
                matched or geocoded. No targets returns missing_location.
        Returns:
            ProviderResult with deduplicated alerts, retrieval times and honest
            partial/stale/unavailable states. The model/ranking is never changed.
        """
        if arrival.tzinfo is None or arrival.utcoffset() is None:
            raise ValueError("Construction arrival must include a timezone")
        if not targets:
            return ProviderResult("missing_location", SOURCE_NAME, SOURCE_URL,
                                  limitations=["Trip coordinates are required."])
        snapshot = self.cache.get(CACHE_KEY, self._load, CACHE_TTL_SECONDS,
                                  MAX_STALE_SECONDS)
        result = ProviderResult(
            "unavailable", SOURCE_NAME, SOURCE_URL,
            snapshot.last_checked_at, snapshot.last_attempt_at,
            limitations=[MATCH_LIMITATION, COVERAGE_LIMITATION],
        )
        if snapshot.data is None:
            result.limitations.append(
                "Published construction data could not be retrieved.")
            return result
        notices, unknown = {}, False
        instant = arrival.astimezone(timezone.utc)
        for layer, feature in snapshot.data:
            attributes = feature["attributes"]
            if _text(attributes.get("AlertType")).casefold() == "text":
                continue  # Map label positions are not impact geometry.
            status, window = _status(attributes), _window(attributes)
            if (status == "inactive"
                    or (window and not window[0] <= instant < window[1])):
                continue
            try:
                parts = _parts(feature.get("geometry"), LAYERS[layer])
                matches = [(target, basis) for target in targets
                           if (basis := _match(parts, LAYERS[layer], target))]
            except (ValueError, TypeError):
                unknown = True
                continue
            if not matches:
                continue
            if status != "approved" or window is None:
                unknown = True
                continue
            start, end, limitations = window
            if any("Public-impact dates unavailable" in note for note in limitations):
                unknown = True
            identity = (str(attributes.get("AlertID") or "").strip()
                        or f"{layer}:{attributes['objectid']}")
            if len(identity) > MAX_NOTICE_ID_CHARACTERS:
                unknown = True
                continue
            notice = notices.setdefault(identity, {
                "alert_id": f"construction:{identity}", "alert_type": "construction",
                "message": "", "locations": [], "relevant_from": start,
                "relevant_until": end, "source_name": SOURCE_NAME,
                "source_url": _source_link(attributes, layer),
                "last_checked_at": snapshot.last_checked_at,
                "match_basis": "within_200m", "limitations": [MATCH_LIMITATION],
                "_subject": _text(attributes.get("Subject")
                                  or attributes.get("Project_Name")) or "UCSD project",
                "_types": [],
            })
            notice["relevant_from"] = max(notice["relevant_from"], start)
            notice["relevant_until"] = min(notice["relevant_until"], end)
            for target, basis in matches:
                location = asdict(target)
                if location not in notice["locations"]:
                    notice["locations"].append(location)
                if basis == "intersects_geometry":
                    notice["match_basis"] = basis
            feature_type = _text(attributes.get("AlertType")) or "construction feature"
            if feature_type not in notice["_types"]:
                notice["_types"].append(feature_type)
            for note in limitations:
                if note not in notice["limitations"]:
                    notice["limitations"].append(note)
        for notice in notices.values():
            notice["message"] = (
                f"Published construction notice: {notice.pop('_subject')}. "
                f"Source map marks: {', '.join(notice.pop('_types'))}. "
                "Check the notice for exact access conditions.")
            if len(notice["message"]) > MAX_MESSAGE_CHARACTERS:
                notice["message"] = (
                    notice["message"][:MAX_MESSAGE_CHARACTERS - 1].rstrip() + "…")
                notice["limitations"].append(
                    "Source text was shortened; read the linked official notice.")
            if notice["match_basis"] == "within_200m":
                notice["limitations"].append(
                    "Within 200 m of published geometry; impact at this exact "
                    "point is unverified.")
            else:
                notice["limitations"].append(
                    "At least one listed trip point intersects the mapped feature; "
                    "other listed points may only be nearby.")
        result.alerts = sorted(notices.values(), key=lambda item: item["alert_id"])
        if unknown:
            result.limitations.append(UNKNOWN_LIMITATION)
        if snapshot.state == "stale":
            result.status = "stale"
            result.limitations.append(
                "Cached construction data could not be refreshed.")
        else:
            result.status = ("partial" if unknown else
                             ("available" if notices else "no_relevant"))
        return result
