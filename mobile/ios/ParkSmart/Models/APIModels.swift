import Foundation

// Property names intentionally match the proposed Python/JSON contract.
struct Coordinates: Codable, Equatable {
    let latitude: Double
    let longitude: Double

    var isValid: Bool {
        latitude.isFinite && longitude.isFinite
            && (-90...90).contains(latitude) && (-180...180).contains(longitude)
    }
}

struct ParkingLocation: Codable, Identifiable, Equatable {
    let location_id: String
    let name: String
    let coordinates: Coordinates?
    var id: String { location_id }
}

struct LocationsResponse: Codable {
    let schema_version: String
    let data_status: String
    let locations: [ParkingLocation]
    let limitations: [String]

    func validate() throws {
        guard schema_version == "0.1",
              ["sample", "verified"].contains(data_status),
              Set(locations.map(\.id)).count == locations.count,
              locations.allSatisfy({
                  !$0.id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                      && !$0.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                      && ($0.coordinates?.isValid ?? true)
              }) else { throw AppError.invalidResponse }
    }

    // The API's verified status is the trust boundary. Never geocode fictional IDs.
    var mappableLocations: [ParkingLocation] {
        guard data_status == "verified" else { return [] }
        return locations.filter { $0.coordinates?.isValid == true }
    }
}

struct PlaceInput: Codable {
    let name: String
    let coordinates: Coordinates?
}

struct RecommendationRequest: Codable {
    let destination: PlaceInput
    let arrival_time: String
    let permit_type: String
    let starting_location: PlaceInput?

    static let campusTimeZone = TimeZone(identifier: "America/Los_Angeles")!

    /// Encode the selected instant with UCSD's offset, including DST.
    init(destination: String, arrival: Date, permit: String,
         coordinates: Coordinates? = nil) {
        self.destination = PlaceInput(name: destination, coordinates: coordinates)
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = Self.campusTimeZone
        arrival_time = formatter.string(from: arrival)
        permit_type = permit
        starting_location = nil
    }
}

struct ParkingChoice: Codable {
    let location: ParkingLocation
    let estimated_available_fraction: Double?
    let estimated_walking_minutes: Double?
    let explanation: String

    var availabilityText: String {
        guard let fraction = estimated_available_fraction else { return "Unavailable" }
        return String(format: "%.0f%% estimated open", fraction * 100)
    }

    var walkingText: String {
        guard let minutes = estimated_walking_minutes else { return "Unavailable" }
        return String(format: "%.1f min", minutes)
    }

    var isValid: Bool {
        let fractionOK = estimated_available_fraction.map {
            $0.isFinite && (0...1).contains($0)
        } ?? true
        let walkingOK = estimated_walking_minutes.map { $0.isFinite && $0 >= 0 } ?? true
        return fractionOK && walkingOK && (location.coordinates?.isValid ?? true)
            && !location.id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !location.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}

struct RecommendationResponse: Codable {
    let schema_version: String
    let status: String
    let is_example: Bool
    let arrival_time: String
    let time_zone: String
    let first_choice: ParkingChoice?
    let backup_choice: ParkingChoice?
    let explanation: String
    let limitations: [String]

    func validate() throws {
        guard schema_version == "0.1", time_zone == "America/Los_Angeles",
              ["ready", "no_suitable_location", "not_implemented", "predictions_unavailable"].contains(status),
              Self.parseDate(arrival_time) != nil,
              first_choice?.isValid ?? true, backup_choice?.isValid ?? true
        else { throw AppError.invalidResponse }
        if status == "ready" {
            guard first_choice != nil,
                  backup_choice == nil || backup_choice?.location.id != first_choice?.location.id
            else { throw AppError.invalidResponse }
        } else if first_choice != nil || backup_choice != nil {
            throw AppError.invalidResponse
        }
    }

    private static func parseDate(_ value: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: value) { return date }
        formatter.formatOptions.insert(.withFractionalSeconds)
        return formatter.date(from: value)
    }
}
