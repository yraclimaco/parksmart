import XCTest
@testable import ParkSmart

final class ContractTests: XCTestCase {
    private func response(_ first: String = "null", _ backup: String = "null",
                          status: String = "not_implemented") throws -> RecommendationResponse {
        let json = """
        {"schema_version":"0.1","status":"\(status)","is_example":true,
         "arrival_time":"2026-10-29T09:00:00-07:00","time_zone":"America/Los_Angeles",
         "first_choice":\(first),"backup_choice":\(backup),
         "explanation":"Test fixture","limitations":[]}
        """
        return try JSONDecoder().decode(RecommendationResponse.self, from: Data(json.utf8))
    }

    private let choice = """
    {"location":{"location_id":"sample-a","name":"Sample A","coordinates":null},
     "estimated_available_fraction":null,"estimated_walking_minutes":null,
     "explanation":"Example only"}
    """

    func testNullMeasurementsStayUnknown() throws {
        let value = try response(choice, status: "ready")
        try value.validate()
        XCTAssertEqual(value.first_choice?.availabilityText, "Unavailable")
        XCTAssertEqual(value.first_choice?.walkingText, "Unavailable")
    }

    func testZeroIsKnownRatherThanUnknown() throws {
        let zero = choice.replacingOccurrences(of: "fraction\":null", with: "fraction\":0")
            .replacingOccurrences(of: "minutes\":null", with: "minutes\":0")
        let value = try response(zero, status: "ready")
        try value.validate()
        XCTAssertEqual(value.first_choice?.availabilityText, "0% estimated open")
        XCTAssertEqual(value.first_choice?.walkingText, "0.0 min")
    }

    func testDuplicateFirstAndBackupRejected() throws {
        XCTAssertThrowsError(try response(choice, choice, status: "ready").validate())
    }

    func testReadyRequiresFirstChoice() throws {
        XCTAssertThrowsError(try response(status: "ready").validate())
    }

    func testUnavailableCannotContainChoices() throws {
        XCTAssertThrowsError(try response(choice).validate())
    }

    func testOutOfRangeFractionRejected() throws {
        let invalid = choice.replacingOccurrences(of: "fraction\":null", with: "fraction\":50")
        XCTAssertThrowsError(try response(invalid, status: "ready").validate())
    }

    func testOnlyVerifiedCatalogCoordinatesBecomeMarkers() throws {
        let location = ParkingLocation(location_id: "test-only", name: "Test fixture",
                                       coordinates: Coordinates(latitude: 0, longitude: 0))
        let sample = LocationsResponse(schema_version: "0.1", data_status: "sample",
                                       locations: [location], limitations: [])
        XCTAssertTrue(sample.mappableLocations.isEmpty)
        let verified = LocationsResponse(schema_version: "0.1", data_status: "verified",
                                         locations: [location], limitations: [])
        XCTAssertEqual(verified.mappableLocations.map(\.id), ["test-only"])
        // Synthetic coordinates above are test-only and never bundled as app fixtures.
    }

    func testRequestUsesContractKeysAndCampusOffset() throws {
        let date = try XCTUnwrap(ISO8601DateFormatter().date(from: "2026-10-29T16:00:00Z"))
        let request = RecommendationRequest(destination: "Geisel", arrival: date, permit: "S")
        XCTAssertEqual(request.arrival_time, "2026-10-29T09:00:00-07:00")
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(request))
                                 as? [String: Any])
        XCTAssertEqual(json["permit_type"] as? String, "S")
        XCTAssertNotNil(json["destination"])
        XCTAssertNil(json["permitType"])
    }

    func testWinterRequestUsesStandardTime() throws {
        let date = try XCTUnwrap(ISO8601DateFormatter().date(from: "2026-12-01T17:00:00Z"))
        XCTAssertEqual(RecommendationRequest(destination: "Geisel", arrival: date, permit: "S")
            .arrival_time, "2026-12-01T09:00:00-08:00")
    }

    func testInvalidURLAndCredentialsRejected() {
        for value in ["", "file:///tmp/api", "https://user:secret@example.com", "http://localhost?q=x"] {
            XCTAssertThrowsError(try APIParkingService(baseURL: value, recommendationsEnabled: false))
        }
    }

    func testDisabledRecommendationsDoNotContactNetwork() async throws {
        let service = try APIParkingService(baseURL: "http://127.0.0.1:1", recommendationsEnabled: false)
        do {
            _ = try await service.recommendations(
                RecommendationRequest(destination: "Test", arrival: Date(), permit: "Test")
            )
            XCTFail("Expected disabled feature error")
        } catch AppError.recommendationsUnavailable {
            // Expected before any URLSession request.
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }
}


extension ContractTests {
    func testTransportSendsCoordinatesAndDecodesResponse() async throws {
        let expected = try response(choice, status: "ready")
        let data = try JSONEncoder().encode(expected)
        let service = try APIParkingService(
            baseURL: "https://parksmart.invalid",
            recommendationsEnabled: true
        ) { request in
            XCTAssertEqual(request.url?.path, "/recommendations")
            XCTAssertEqual(request.httpMethod, "POST")
            XCTAssertEqual(request.value(forHTTPHeaderField: "Content-Type"),
                           "application/json")
            let body = try XCTUnwrap(request.httpBody)
            let sent = try JSONDecoder().decode(RecommendationRequest.self, from: body)
            XCTAssertEqual(sent.destination.coordinates?.latitude, 32.88)
            XCTAssertEqual(sent.destination.coordinates?.longitude, -117.24)
            return (data, HTTPURLResponse(url: request.url!, statusCode: 200,
                                         httpVersion: nil, headerFields: nil)!)
        }
        let value = try await service.recommendations(
            RecommendationRequest(
                destination: "Test destination", arrival: Date(), permit: "S",
                coordinates: Coordinates(latitude: 32.88, longitude: -117.24)
            )
        )
        XCTAssertEqual(value.status, "ready")
        XCTAssertEqual(value.first_choice?.location.id, "sample-a")
        XCTAssertEqual(value.first_choice?.availabilityText, "Unavailable")
    }

    func testTransportPreservesBackendErrorDetail() async throws {
        let service = try APIParkingService(
            baseURL: "https://parksmart.invalid",
            recommendationsEnabled: true
        ) { request in
            let data = Data(#"{"detail":"Historical estimates are unavailable."}"#.utf8)
            return (data, HTTPURLResponse(url: request.url!, statusCode: 503,
                                         httpVersion: nil, headerFields: nil)!)
        }
        do {
            _ = try await service.recommendations(
                RecommendationRequest(destination: "Test", arrival: Date(), permit: "S")
            )
            XCTFail("Expected backend error")
        } catch AppError.backend(let status, let message) {
            XCTAssertEqual(status, 503)
            XCTAssertEqual(message, "Historical estimates are unavailable.")
        }
    }

    func testValidationArrayUsesHelpfulFallback() async throws {
        let service = try APIParkingService(
            baseURL: "https://parksmart.invalid",
            recommendationsEnabled: true
        ) { request in
            let data = Data(#"{"detail":[{"msg":"Invalid permit"}]}"#.utf8)
            return (data, HTTPURLResponse(url: request.url!, statusCode: 422,
                                         httpVersion: nil, headerFields: nil)!)
        }
        do {
            _ = try await service.recommendations(
                RecommendationRequest(destination: "Test", arrival: Date(), permit: "XYZ")
            )
            XCTFail("Expected validation error")
        } catch AppError.backend(let status, let message) {
            XCTAssertEqual(status, 422)
            XCTAssertTrue(message.contains("permit code"))
        }
    }

    @MainActor
    func testCancelledOldResponseCannotReplaceNewResult() async throws {
        let old = try response(choice, status: "ready")
        let newerChoice = choice.replacingOccurrences(of: "sample-a", with: "sample-b")
        let newer = try response(newerChoice, status: "ready")
        let started = expectation(description: "Old request started")
        let service = DelayedTestService(old: old, newer: newer, started: started)
        let model = PlannerModel(serviceOverride: service)
        model.destination = "Test destination"
        model.permit = "old"
        model.plan()

        await fulfillment(of: [started], timeout: 3)
        // Capture the old task before starting the replacement.
        let oldFinished = Task { await model.waitForCurrentWork() }
        await Task.yield()

        model.permit = "new"
        model.plan()
        await model.waitForCurrentWork()
        XCTAssertEqual(model.result?.first_choice?.location.id, "sample-b")

        await service.releaseOldResponse()
        await oldFinished.value
        XCTAssertEqual(model.result?.first_choice?.location.id, "sample-b")
        XCTAssertFalse(model.busy)
        XCTAssertNil(model.error)
    }
}

// Intentionally ignores cancellation to simulate a late server response.
private actor DelayedTestService: ParkingService {
    let old: RecommendationResponse
    let newer: RecommendationResponse
    let started: XCTestExpectation
    private var continuation: CheckedContinuation<RecommendationResponse, Never>?

    init(old: RecommendationResponse, newer: RecommendationResponse,
         started: XCTestExpectation) {
        self.old = old
        self.newer = newer
        self.started = started
    }

    func locations() async throws -> LocationsResponse {
        throw AppError.exampleFailure
    }

    func recommendations(_ request: RecommendationRequest) async throws
        -> RecommendationResponse {
        if request.permit_type == "new" { return newer }
        return await withCheckedContinuation {
            continuation = $0
            started.fulfill()
        }
    }

    func releaseOldResponse() {
        continuation?.resume(returning: old)
        continuation = nil
    }
}
