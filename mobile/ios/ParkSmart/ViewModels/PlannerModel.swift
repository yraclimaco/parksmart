import Combine
import Foundation
import MapKit

@MainActor
final class PlannerModel: ObservableObject {
    @Published var destination = "" {
        didSet {
            if destination != oldValue {
                destinationCoordinates = nil
                destinationResults = []
                destinationSearch?.cancel()
                destinationSearch = nil
                searchingDestination = false
                destinationSearchError = nil
                invalidate()
            }
        }
    }
    @Published private(set) var destinationCoordinates: Coordinates?
    @Published private(set) var destinationResults: [MKMapItem] = []
    @Published private(set) var searchingDestination = false
    @Published private(set) var destinationSearchError: String?
    private var destinationSearch: MKLocalSearch?
    @Published var permit = ""
    @Published var arrival = Date()
    @Published var useAPI = false
    @Published var scenario: SampleScenario = .cards
    @Published var baseURL = UserDefaults.standard.string(forKey: "apiBaseURL")
        ?? "http://127.0.0.1:8000"
    @Published var recommendationsEnabled = false
    @Published private(set) var catalog: LocationsResponse?
    @Published private(set) var result: RecommendationResponse?
    @Published private(set) var error: String?
    @Published private(set) var busy = false
    @Published private(set) var requestJSON = ""
    @Published var selectedID: String?
    private var work: Task<Void, Never>?

    var validInput: Bool {
        (!useAPI || destinationCoordinates?.isValid == true)
            && [destination, permit].allSatisfy {
            let text = $0.trimmingCharacters(in: .whitespacesAndNewlines)
            return !text.isEmpty && text.count <= 200
        }
    }

    private let serviceOverride: (any ParkingService)?

    init(serviceOverride: (any ParkingService)? = nil) {
        self.serviceOverride = serviceOverride
    }

    // Allows tests to await completion without timing-based sleeps.
    func waitForCurrentWork() async {
        await work?.value
    }

    private func service() throws -> any ParkingService {
        if let serviceOverride { return serviceOverride }
        if useAPI {
            return try APIParkingService(baseURL: baseURL,
                                         recommendationsEnabled: recommendationsEnabled)
        }
        return SampleParkingService(scenario: scenario)
    }

    /// Discard stale responses when inputs or connection settings change.
    func invalidate(clearCatalog: Bool = false) {
        work?.cancel()
        busy = false
        result = nil
        error = nil
        selectedID = nil
        requestJSON = ""
        if clearCatalog { catalog = nil }
    }

    func loadLocations() {
        invalidate(clearCatalog: true)
        busy = true
        work = Task {
            do {
                let value = try await service().locations()
                try Task.checkCancellation()
                catalog = value
                busy = false
            } catch {
                guard !Task.isCancelled else { return }
                self.error = error.localizedDescription
                busy = false
            }
        }
    }

    func plan() {
        guard validInput else { return }
        invalidate()
        let request = RecommendationRequest(
            destination: destination.trimmingCharacters(in: .whitespacesAndNewlines),
            arrival: arrival, permit: permit.trimmingCharacters(in: .whitespacesAndNewlines),
            coordinates: useAPI ? destinationCoordinates : nil
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        requestJSON = (try? String(data: encoder.encode(request), encoding: .utf8)) ?? ""
        busy = true
        work = Task {
            do {
                let value = try await service().recommendations(request)
                try Task.checkCancellation()
                result = value
                selectedID = value.first_choice?.location.id
                busy = false
            } catch {
                guard !Task.isCancelled else { return }
                self.error = error.localizedDescription
                busy = false
            }
        }
    }

    /// Search for destinations; parking IDs still come only from the backend.
    func searchDestination() {
        let query = destination.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return }
        destinationSearch?.cancel()
        destinationCoordinates = nil
        destinationResults = []
        destinationSearchError = nil
        invalidate()

        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = query + ", UC San Diego"
        let search = MKLocalSearch(request: request)
        destinationSearch = search
        searchingDestination = true

        Task {
            do {
                let response = try await search.start()
                guard destinationSearch === search else { return }
                destinationResults = response.mapItems.filter {
                    let point = $0.placemark.coordinate
                    return Coordinates(latitude: point.latitude,
                                       longitude: point.longitude).isValid
                }
                if destinationResults.isEmpty {
                    destinationSearchError = "No places found. Try a more specific name."
                }
                searchingDestination = false
                destinationSearch = nil
            } catch {
                guard destinationSearch === search else { return }
                destinationSearchError = "Destination search failed. Check your connection and try again."
                searchingDestination = false
                destinationSearch = nil
            }
        }
    }

    func selectDestination(_ item: MKMapItem) {
        let point = item.placemark.coordinate
        let coordinates = Coordinates(latitude: point.latitude, longitude: point.longitude)
        guard coordinates.isValid else { return }
        destinationSearch?.cancel()
        destinationSearch = nil
        destination = item.name ?? destination
        destinationCoordinates = coordinates
        destinationResults = []
        searchingDestination = false
        destinationSearchError = nil
        invalidate()
    }

    func saveConnection() {
        UserDefaults.standard.set(baseURL, forKey: "apiBaseURL")
        loadLocations()
    }
}
