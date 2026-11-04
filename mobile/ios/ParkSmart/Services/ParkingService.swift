import Foundation

enum AppError: LocalizedError {
    case invalidURL, invalidResponse, recommendationsUnavailable, http(Int), exampleFailure

    case backend(status: Int, message: String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Enter an HTTP or HTTPS backend URL without credentials, query, or fragment."
        case .invalidResponse:
            return "The response does not match the proposed 0.1 API contract."
        case .recommendationsUnavailable:
            return "Recommendations are disabled or unavailable. Check Connection settings and the backend."
        case .backend(_, let message):
            return message
        case .http(let status):
            return "The backend returned HTTP \(status). Check the server and API contract."
        case .exampleFailure:
            return "Sample error state. No network request was made. Try another sample state."
        }
    }
}

protocol ParkingService {
    func locations() async throws -> LocationsResponse
    func recommendations(_ request: RecommendationRequest) async throws -> RecommendationResponse
}

/// All transport stays here; views do not know URLSession or endpoint details.
struct APIParkingService: ParkingService {
    let baseURL: URL
    let recommendationsEnabled: Bool
    private let transport: (URLRequest) async throws -> (Data, URLResponse)

    init(
        baseURL: String,
        recommendationsEnabled: Bool,
        transport: @escaping (URLRequest) async throws -> (Data, URLResponse) = {
            try await URLSession.shared.data(for: $0)
        }
    ) throws {
        guard let parts = URLComponents(string: baseURL),
              ["http", "https"].contains(parts.scheme?.lowercased() ?? ""),
              parts.host != nil, parts.user == nil, parts.password == nil,
              parts.query == nil, parts.fragment == nil, let url = parts.url
        else { throw AppError.invalidURL }
        self.baseURL = url
        self.recommendationsEnabled = recommendationsEnabled
        self.transport = transport
    }

    func locations() async throws -> LocationsResponse {
        let value: LocationsResponse = try await send(path: "locations")
        try value.validate()
        return value
    }

    func recommendations(_ request: RecommendationRequest) async throws -> RecommendationResponse {
        guard recommendationsEnabled else { throw AppError.recommendationsUnavailable }
        let value: RecommendationResponse = try await send(
            path: "recommendations", body: JSONEncoder().encode(request)
        )
        try value.validate()
        return value
    }

    private func send<T: Decodable>(path: String, body: Data? = nil) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.timeoutInterval = 15
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpMethod = "POST"
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await transport(request)
        guard let http = response as? HTTPURLResponse else { throw AppError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            if path == "recommendations" && [404, 405, 501].contains(http.statusCode) {
                throw AppError.recommendationsUnavailable
            }
            let payload = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            let detail = (payload?["detail"] as? String)?
                .trimmingCharacters(in: .whitespacesAndNewlines)

            if let detail, !detail.isEmpty {
                throw AppError.backend(status: http.statusCode, message: detail)
            }

            switch http.statusCode {
            case 400, 422:
                throw AppError.backend(
                    status: http.statusCode,
                    message: "The server rejected these inputs. Check the destination, arrival time, and permit code (A, B, S, SR, D, or V)."
                )
            case 503:
                throw AppError.backend(
                    status: http.statusCode,
                    message: "Historical parking estimates are temporarily unavailable. Try again later. This does not mean parking is full."
                )
            default:
                throw AppError.http(http.statusCode)
            }
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}

enum SampleScenario: String, CaseIterable, Identifiable {
    case cards = "Two example cards"
    case empty = "Empty result"
    case unavailable = "Not implemented"
    case error = "Error"
    var id: String { rawValue }
    var resource: String {
        switch self {
        case .cards: return "recommendation_example"
        case .empty: return "recommendation_no_suitable"
        case .unavailable: return "recommendation_not_implemented"
        case .error: return ""
        }
    }
}

/// Exact team fixtures, kept in JSON resources. Inputs never determine a sample ranking.
struct SampleParkingService: ParkingService {
    let scenario: SampleScenario

    func locations() async throws -> LocationsResponse {
        let value: LocationsResponse = try load("locations_sample")
        try value.validate()
        return value
    }

    func recommendations(_ request: RecommendationRequest) async throws -> RecommendationResponse {
        // A visible short delay makes the prototype's loading state demonstrable.
        try await Task.sleep(nanoseconds: 350_000_000)
        if scenario == .error { throw AppError.exampleFailure }
        let value: RecommendationResponse = try load(scenario.resource)
        try value.validate()
        return value
    }

    private func load<T: Decodable>(_ name: String) throws -> T {
        guard let url = Bundle.main.url(forResource: name, withExtension: "json")
        else { throw AppError.invalidResponse }
        return try JSONDecoder().decode(T.self, from: Data(contentsOf: url))
    }
}
