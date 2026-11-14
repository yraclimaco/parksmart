"""Offline UCSD construction parsing, spatial matching and freshness checks."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import pytest

from src.trip_alerts.cache import CachedJSON, SourceError
from src.trip_alerts.construction import ConstructionProvider, LAYERS, SOURCE_URL
from src.trip_alerts.contracts import AlertTarget
from src.api.alert_schemas import AlertSourceResult

ARRIVAL = datetime(2026, 11, 13, 18, tzinfo=timezone.utc)
TARGET = AlertTarget("parking", "Gilman", 32.88, -117.24, "gilman")


def milliseconds(value):
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def feature(identity=1, alert_id="project-1", **updates):
    """Build a synthetic approved point in the inspected ArcGIS field schema."""
    attributes = {
        "objectid": identity, "AlertID": alert_id, "AlertType": "Parking Closed",
        "Subject": "Synthetic construction project", "Status": "Approved",
        "Project_Alert_Status": "APPROVED",
        "Public_Impact_Date": milliseconds("2026-11-10T00:00:00-08:00"),
        "Public_Impact_End_Date": milliseconds("2026-11-13T00:00:00-08:00"),
        "Alert_Start_Date": milliseconds("2026-11-01T00:00:00-07:00"),
        "Alert_End_Date": milliseconds("2026-11-20T00:00:00-08:00"),
        "Public_URL_Link_To_Map": "https://admin-enterprise-gis.ucsd.edu/notice",
    }
    attributes.update(updates)
    return {"attributes": attributes, "geometry": {"x": -117.24, "y": 32.88}}


def page(layer, features=(), exceeded=False):
    return {"geometryType": LAYERS[layer], "spatialReference": {"wkid": 4326},
            "features": deepcopy(list(features)), "exceededTransferLimit": exceeded}


class HTTPFixture:
    """Supply per-layer pages or SourceError without making network requests."""

    def __init__(self, pages=None):
        self.pages = pages or {}
        self.calls = []
        self.fail = False

    def get_json(self, url, params=None, deadline=None):
        layer = int(urlsplit(url).path.split("/")[-2])
        self.calls.append((layer, dict(params), deadline))
        if self.fail:
            raise SourceError("Synthetic source outage")
        values = self.pages.get(layer)
        return deepcopy(values.pop(0) if values else page(layer))


@pytest.fixture
def clocks():
    elapsed = [0.0]
    return elapsed, CachedJSON(monotonic=lambda: elapsed[0],
                               utcnow=lambda: ARRIVAL + timedelta(seconds=elapsed[0]))


def provider(http, clocks):
    return ConstructionProvider(http, clocks[1], utcnow=lambda: ARRIVAL)


def test_deduplicates_notice_and_preserves_targets_dates_source_and_no_closure(clocks):
    first, second = feature(), feature(identity=2)
    second["geometry"] = {"paths": [[[-117.241, 32.88], [-117.239, 32.88]]]}
    second["attributes"]["AlertType"] = "Pedestrian"
    http = HTTPFixture({0: [page(0, [first])], 1: [page(1, [second])]})
    destination = AlertTarget("destination", "Lecture", 32.88, -117.24)
    result = provider(http, clocks).get(ARRIVAL, [TARGET, destination])
    assert result.status == "available"
    assert len(result.alerts) == 1
    alert = result.alerts[0]
    assert len(alert["locations"]) == 2
    assert alert["relevant_until"] == datetime(2026, 11, 14, 8, tzinfo=timezone.utc)
    assert alert["match_basis"] == "intersects_geometry"
    assert alert["source_url"] == first["attributes"]["Public_URL_Link_To_Map"]
    assert "Published construction notice" in alert["message"]
    assert "Parking Closed" in alert["message"] and "Pedestrian" in alert["message"]
    assert "no closure or rerouting is inferred" in alert["limitations"][0]
    assert result.last_checked_at == ARRIVAL
    assert len(http.calls) == 3
    assert {item[2] for item in http.calls} == {http.calls[0][2]}
    assert all(item[1]["outSR"] == 4326 for item in http.calls)


def test_same_raw_cache_is_refiltered_by_arrival_and_locations(clocks):
    http = HTTPFixture({0: [page(0, [feature()])]})
    source = provider(http, clocks)
    assert source.get(ARRIVAL, [TARGET]).status == "available"
    assert source.get(ARRIVAL + timedelta(days=2), [TARGET]).status == "no_relevant"
    far = AlertTarget("destination", TARGET.name, 32.9, -117.2)
    assert source.get(ARRIVAL, [far]).status == "no_relevant"
    assert len(http.calls) == 3


@pytest.mark.parametrize("changes", [
    {"Status": "Cancelled"}, {"Project_Alert_Status": "INACTIVE"},
    {"Public_Impact_End_Date": milliseconds("2026-11-12T00:00:00-08:00")},
    {"Public_Impact_Date": milliseconds("2026-11-14T00:00:00-08:00"),
     "Public_Impact_End_Date": milliseconds("2026-11-20T00:00:00-08:00")},
])
def test_inactive_expired_or_future_notices_are_excluded(clocks, changes):
    http = HTTPFixture({0: [page(0, [feature(**changes)])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "no_relevant" and result.alerts == []


@pytest.mark.parametrize("changes", [
    {"Status": None}, {"Project_Alert_Status": "UNKNOWN"},
    {"Public_Impact_Date": None, "Alert_Start_Date": None},
])
def test_unknown_relevance_is_partial_not_false_empty(clocks, changes):
    http = HTTPFixture({0: [page(0, [feature(**changes)])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "partial" and result.alerts == []
    assert any("could not be checked completely" in note for note in result.limitations)


def test_fallback_uses_one_complete_pair_and_labels_broader_timing(clocks):
    item = feature(Public_Impact_Date=None)
    http = HTTPFixture({0: [page(0, [item])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "partial"
    alert = result.alerts[0]
    assert alert["relevant_from"] == datetime(2026, 11, 1, 7, tzinfo=timezone.utc)
    assert alert["relevant_until"] == datetime(2026, 11, 21, 8, tzinfo=timezone.utc)
    assert any("alert-date window" in note for note in alert["limitations"])


def test_date_only_end_uses_next_local_midnight_across_dst(clocks):
    item = feature(
        Public_Impact_Date=milliseconds("2026-10-31T00:00:00-07:00"),
        Public_Impact_End_Date=milliseconds("2026-11-01T00:00:00-07:00"))
    http = HTTPFixture({0: [page(0, [item])]})
    result = provider(http, clocks).get(
        datetime(2026, 11, 2, 7, tzinfo=timezone.utc), [TARGET])
    assert result.alerts[0]["relevant_until"] == datetime(
        2026, 11, 2, 8, tzinfo=timezone.utc)


@pytest.mark.parametrize("geometry", [None, {"x": 6257000, "y": 1898000},
    {"x": -117.24, "y": 32.88, "spatialReference": {"wkid": 2230}},
    {"x": float("nan"), "y": 32.88}])
def test_missing_invalid_or_native_geometry_is_partial(clocks, geometry):
    item = feature()
    item["geometry"] = geometry
    source = provider(HTTPFixture({0: [page(0, [item])]}), clocks)
    result = source.get(ARRIVAL, [TARGET])
    assert result.status == "partial" and result.alerts == []


def square(half_size):
    x, y = TARGET.longitude, TARGET.latitude
    return [[x-half_size, y-half_size], [x+half_size, y-half_size],
            [x+half_size, y+half_size], [x-half_size, y+half_size],
            [x-half_size, y-half_size]]


def test_polygon_hole_is_not_filled_by_outer_shell_or_bounding_box(clocks):
    item = feature()
    item["geometry"] = {"rings": [square(0.01), square(0.004)]}
    source = provider(HTTPFixture({2: [page(2, [item])]}), clocks)
    result = source.get(ARRIVAL, [TARGET])
    assert result.status == "no_relevant" and not result.alerts


def test_polygon_shell_and_nearby_line_or_point_match_conservatively(clocks):
    polygon, line, point = feature(), feature(2, "project-2"), feature(3, "project-3")
    polygon["geometry"] = {"rings": [square(0.001)]}
    line["geometry"] = {"paths": [[[-117.241, 32.881], [-117.239, 32.881]]]}
    point["geometry"] = {"x": -117.24, "y": 32.881}
    http = HTTPFixture({0: [page(0, [point])], 1: [page(1, [line])],
                        2: [page(2, [polygon])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "available"
    assert [item["match_basis"] for item in result.alerts] == [
        "intersects_geometry", "within_200m", "within_200m"]


def test_pagination_collects_every_page_and_checks_offsets(clocks):
    http = HTTPFixture({0: [page(0, [feature()], True), page(0, [feature(2)])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "available"
    assert [item[1]["resultOffset"] for item in http.calls if item[0] == 0] == [0, 1]
    assert all(item[1]["orderByFields"] == "objectid ASC" for item in http.calls)


@pytest.mark.parametrize("failure", [
    "error", "native", "missing", "empty_page", "repeated"])
def test_bad_or_incomplete_source_never_reports_empty_success(clocks, failure):
    first = page(0, [feature()], True)
    second = page(0, [feature(2)])
    if failure == "error":
        first = {"error": {"code": 500}}
    elif failure == "native":
        first["spatialReference"] = {"wkid": 102646, "latestWkid": 2230}
    elif failure == "missing":
        del first["features"]
    elif failure == "empty_page":
        second = page(0, [], True)
    else:
        second = page(0, [feature()])
    http = HTTPFixture({0: [first, second]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "unavailable" and not result.alerts


@pytest.mark.parametrize("bound", ["pages", "features"])
def test_pagination_and_feature_bounds_fail_honestly(clocks, monkeypatch, bound):
    from src.trip_alerts import construction
    if bound == "pages":
        monkeypatch.setattr(construction, "MAX_PAGES_PER_LAYER", 1)
        response = page(0, [feature()], True)
    else:
        monkeypatch.setattr(construction, "MAX_TOTAL_FEATURES", 1)
        response = page(0, [feature(), feature(2)])
    result = provider(HTTPFixture({0: [response]}), clocks).get(ARRIVAL, [TARGET])
    assert result.status == "unavailable" and not result.alerts


def test_shared_deadline_prevents_starting_another_layer_request(clocks, monkeypatch):
    from src.trip_alerts import construction
    elapsed = [0]
    monkeypatch.setattr(construction.time, "monotonic", lambda: elapsed[0])

    class SlowHTTP(HTTPFixture):
        def get_json(self, url, params=None, deadline=None):
            response = super().get_json(url, params, deadline)
            elapsed[0] = deadline + 1
            return response

    http = SlowHTTP()
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "unavailable"
    assert len(http.calls) == 1


def test_failed_refresh_serves_stale_then_expires_without_new_timestamp(clocks):
    http = HTTPFixture({0: [page(0, [feature()])]})
    source = provider(http, clocks)
    source.get(ARRIVAL, [TARGET])
    clocks[0][0] = 601
    http.fail = True
    stale = source.get(ARRIVAL, [TARGET])
    assert stale.status == "stale" and stale.alerts
    assert stale.last_checked_at == ARRIVAL
    assert stale.last_attempt_at == ARRIVAL + timedelta(seconds=601)
    attempts = len(http.calls)
    clocks[0][0] = 602
    assert source.get(ARRIVAL, [TARGET]).status == "stale"
    assert len(http.calls) == attempts  # Failure cooldown prevents request storms.
    clocks[0][0] = 86401
    assert source.get(ARRIVAL, [TARGET]).status == "unavailable"


def test_untrusted_notice_url_uses_official_feature_link(clocks):
    item = feature(Public_URL_Link_To_Map="javascript:evil")
    http = HTTPFixture({0: [page(0, [item])]})
    alert = provider(http, clocks).get(ARRIVAL, [TARGET]).alerts[0]
    assert alert["source_url"].startswith(f"{SOURCE_URL}/0/query?")


def test_map_text_marker_does_not_create_an_access_warning(clocks):
    http = HTTPFixture({0: [page(0, [feature(AlertType="Text")])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "no_relevant" and not result.alerts


def test_long_source_text_stays_plain_and_within_shared_api_message_limit(clocks):
    subject = "<b>Campus work</b><script>bad_script()</script> " + "long " * 150
    item = feature(Subject=subject, AlertType="<i>Pedestrian access</i>" * 30)
    http = HTTPFixture({0: [page(0, [item])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    alert = result.alerts[0]
    assert len(alert["message"]) <= 600
    assert "Campus work" in alert["message"]
    assert "<b>" not in alert["message"] and "<script>" not in alert["message"]
    assert "bad_script" not in alert["message"] and "<i>" not in alert["message"]
    assert any("text was shortened" in note for note in alert["limitations"])
    assert AlertSourceResult.model_validate(asdict(result)).status == "available"


def test_oversized_notice_identifier_is_partial_instead_of_invalid_api_output(clocks):
    http = HTTPFixture({0: [page(0, [feature(alert_id="a" * 400)])]})
    result = provider(http, clocks).get(ARRIVAL, [TARGET])
    assert result.status == "partial" and result.alerts == []


def test_missing_location_does_not_fetch_and_naive_arrival_is_rejected(clocks):
    http = HTTPFixture()
    source = provider(http, clocks)
    assert source.get(ARRIVAL, []).status == "missing_location"
    assert http.calls == []
    with pytest.raises(ValueError, match="timezone"):
        source.get(ARRIVAL.replace(tzinfo=None), [TARGET])
