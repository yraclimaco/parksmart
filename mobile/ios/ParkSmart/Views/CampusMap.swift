import MapKit
import SwiftUI

struct CampusMap: View {
    let locations: [ParkingLocation]
    @Binding var selectedID: String?
    @State private var camera: MapCameraPosition = .automatic
    @State private var centerMessage = "Loading campus basemap…"

    var body: some View {
        Map(position: $camera, selection: $selectedID) {
            ForEach(locations) { location in
                if let point = location.coordinates {
                    Marker(location.name, systemImage: "parkingsign",
                           coordinate: CLLocationCoordinate2D(
                            latitude: point.latitude, longitude: point.longitude
                           ))
                    .tint(selectedID == location.id ? .orange : .blue)
                    .tag(location.id)
                }
            }
        }
        .mapControls { MapCompass(); MapScaleView() }
        .frame(height: 265)
        .overlay(alignment: .bottom) {
            if locations.isEmpty {
                Text("\(centerMessage)\nParking markers await verified coordinates.")
                    .font(.caption).multilineTextAlignment(.center)
                    .padding(10).background(.regularMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 10)).padding(10)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .task {
            // MapKit searches only for campus basemap framing, never parking IDs.
            let request = MKLocalSearch.Request()
            request.naturalLanguageQuery = "University of California San Diego, La Jolla, California"
            do {
                let response = try await MKLocalSearch(request: request).start()
                guard !Task.isCancelled else { return }
                if !response.mapItems.isEmpty {
                    camera = .region(response.boundingRegion)
                    centerMessage = "Campus basemap from Apple Maps."
                } else {
                    centerMessage = "Campus basemap could not be located."
                }
            } catch {
                centerMessage = "Campus basemap unavailable; check your connection."
            }
        }
        .onChange(of: selectedID) { _, value in
            guard let point = locations.first(where: { $0.id == value })?.coordinates else { return }
            withAnimation {
                camera = .region(MKCoordinateRegion(
                    center: CLLocationCoordinate2D(latitude: point.latitude, longitude: point.longitude),
                    latitudinalMeters: 900, longitudinalMeters: 900
                ))
            }
        }
        .onChange(of: locations) { _, value in
            if !value.isEmpty { camera = .automatic }
        }
    }
}
