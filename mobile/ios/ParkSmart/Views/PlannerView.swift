import SwiftUI
import MapKit

struct PlannerView: View {
    @StateObject private var model = PlannerModel()
    @State private var showConnection = false
    @FocusState private var inputFocused: Bool
    
    private enum InputField: Hashable {
        case destination
        case permit
    }

    @FocusState private var focusedField: InputField?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Arrive with a plan.").font(.largeTitle.bold())
                        Text("UC San Diego · Parking planner").foregroundStyle(.secondary)
                    }
                    notice(model.useAPI ? "API mode · Catalog may still contain samples"
                           : "SAMPLE MODE · Fictional locations and fixed example plans",
                           icon: "info.circle")
                    inputs
                    if !model.useAPI {
                        Picker("Sample state", selection: $model.scenario) {
                            ForEach(SampleScenario.allCases) { Text($0.rawValue).tag($0) }
                        }
                        .pickerStyle(.menu)
                    }
                    Button {
                        inputFocused = false
                        model.plan()
                    } label: {
                        HStack {
                            Spacer()
                            Image(systemName: "parkingsign.circle")
                            Text(model.useAPI ? "Request parking plan" : "Show sample plan")
                            Spacer()
                        }.padding(.vertical, 7)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!model.validInput || model.busy)

                    if model.busy {
                        ProgressView("Loading…").frame(maxWidth: .infinity)
                    }
                    if let error = model.error {
                        notice(error, icon: "exclamationmark.triangle")
                    }
                    CampusMap(locations: model.catalog?.mappableLocations ?? [],
                              selectedID: $model.selectedID)
                    if let result = model.result { resultView(result) }
                    if let catalog = model.catalog {
                        DisclosureGroup("Location catalog · \(catalog.data_status)") {
                            VStack(alignment: .leading, spacing: 10) {
                                ForEach(catalog.locations) { location in
                                    Button {
                                        model.selectedID = location.id
                                    } label: {
                                        HStack {
                                            Text(location.name)
                                            Spacer()
                                            if model.selectedID == location.id {
                                                Image(systemName: "checkmark.circle.fill")
                                            }
                                        }
                                    }.buttonStyle(.plain)
                                    Text(location.id).font(.caption.monospaced()).foregroundStyle(.secondary)
                                }
                                if catalog.locations.isEmpty { Text("No catalog locations returned.") }
                                ForEach(catalog.limitations, id: \.self) {
                                    Text($0).font(.caption).foregroundStyle(.secondary)
                                }
                            }.padding(.top, 8)
                        }
                    }
                    if !model.requestJSON.isEmpty {
                        DisclosureGroup("Prepared API request") {
                            Text(model.requestJSON).font(.caption.monospaced())
                                .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                            Text(model.useAPI ? "Sent only if recommendations are enabled."
                                 : "Preview only. Sample plans do not evaluate these inputs.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    Text("Availability is an estimate, never a guarantee. Permit eligibility and walking information require backend evidence.")
                        .font(.footnote).foregroundStyle(.secondary)
                }.padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("ParkSmart").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Connection", systemImage: "network") {
                        showConnection = true
                    }
                    .disabled(model.busy)
                }

                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") {
                        inputFocused = false
                    }
                }
            }
            .sheet(isPresented: $showConnection, onDismiss: model.saveConnection) {
                connectionView
            }
            .task { model.loadLocations() }
                        .onChange(of: model.permit) { _, _ in model.invalidate() }
            .onChange(of: model.arrival) { _, _ in model.invalidate() }
            .onChange(of: model.scenario) { _, _ in model.invalidate() }
        }
        .tint(.blue)
    }

    private var inputs: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("PLAN YOUR VISIT").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 8) {
                Label("Destination", systemImage: "mappin.and.ellipse")
                    .font(.subheadline.weight(.semibold))

                TextField("e.g. Geisel Library", text: $model.destination)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityLabel("Destination")
                    .focused($inputFocused)

                if model.useAPI {
                    Button("Find destination") {
                        inputFocused = false
                        model.searchDestination()
                    }
                    .disabled(model.destination.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                              || model.searchingDestination)

                    if model.searchingDestination {
                        ProgressView("Finding places…")
                    }

                    ForEach(model.destinationResults.indices, id: \.self) { index in
                        let item = model.destinationResults[index]
                        Button {
                            inputFocused = false
                            model.selectDestination(item)
                        } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(item.name ?? "Place").font(.subheadline.bold())
                                Text(item.placemark.title ?? "")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 6)
                        }
                    }

                    if model.destinationCoordinates != nil {
                        Label("Destination selected from Apple Maps", systemImage: "checkmark.circle")
                            .font(.caption).foregroundStyle(.green)
                    } else {
                        Text("Find and select a place before requesting parking.")
                            .font(.caption).foregroundStyle(.secondary)
                    }

                    if let message = model.destinationSearchError {
                        Text(message).font(.caption).foregroundStyle(.red)
                    }
                }
            }
            DatePicker("Arrival · UCSD time", selection: $model.arrival,
                       displayedComponents: [.date, .hourAndMinute])
                .environment(\.timeZone, RecommendationRequest.campusTimeZone)
            VStack(alignment: .leading, spacing: 8) {
                Label("Permit", systemImage: "parkingsign")
                    .font(.subheadline.weight(.semibold))

                TextField("Enter your permit type or code", text: $model.permit)
                    .textFieldStyle(.roundedBorder)
                    .accessibilityLabel("Permit type")
                    .focused($inputFocused)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.characters)
            }
            Text("Supported codes: A, B, S, SR, D, V. Eligibility is checked by the backend; follow posted parking signs.")
                .font(.caption).foregroundStyle(.secondary)
            if !model.validInput {
                Text("Enter a destination and permit (1–200 characters each).")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding().background(.background).clipShape(RoundedRectangle(cornerRadius: 20))
    }

    private func resultView(_ result: RecommendationResponse) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            if result.is_example {
                notice("EXAMPLE ONLY · Fixed fixture; your inputs were not evaluated.", icon: "testtube.2")
            }
            Text(result.status == "ready" ? "Your parking options"
                : result.status == "predictions_unavailable" ? "Availability estimates unavailable"
                : result.status == "not_implemented" ? "Recommendations unavailable"
                : "No suitable recommendation")
                .font(.title2.bold())
            Text(result.explanation).font(.subheadline)
            Text("Response arrival: \(result.arrival_time) · \(result.time_zone)")
                .font(.caption).foregroundStyle(.secondary)
            if let choice = result.first_choice { choiceCard(choice, title: "FIRST CHOICE", backup: false) }
            if let choice = result.backup_choice {
                choiceCard(choice, title: "BACKUP", backup: true)
            } else if result.status == "ready" {
                Text("Backup unavailable").foregroundStyle(.secondary)
            }
            if result.status == "no_suitable_location" {
                Text("This does not mean every parking location is full.").font(.footnote)
            }
            ForEach(result.limitations, id: \.self) {
                Text($0).font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func choiceCard(_ choice: ParkingChoice, title: String, backup: Bool) -> some View {
        let selected = model.selectedID == choice.location.id
        return Button {
            model.selectedID = choice.location.id
        } label: {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Label(title, systemImage: backup ? "arrow.triangle.branch" : "star.fill")
                        .font(.caption.bold()).foregroundStyle(backup ? Color.orange : Color.blue)
                    Spacer()
                    if selected { Label("Selected", systemImage: "checkmark.circle.fill").font(.caption) }
                }
                Text(choice.location.name).font(.title3.bold())
                HStack(alignment: .top) {
                    metric("Availability", value: choice.availabilityText)
                    Spacer()
                    metric("Walk", value: choice.walkingText)
                }
                Text(choice.explanation).font(.subheadline).foregroundStyle(.secondary)
                if !(model.catalog?.mappableLocations.contains(where: { $0.id == choice.location.id }) ?? false) {
                    Text("Map position unavailable").font(.caption).foregroundStyle(.secondary)
                }
            }
            .padding().frame(maxWidth: .infinity, alignment: .leading)
            .background(.background).clipShape(RoundedRectangle(cornerRadius: 18))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(selected ? Color.blue : Color.clear, lineWidth: 2))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(title), \(choice.location.name), \(selected ? "selected" : "not selected")")
    }

    private func metric(_ title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.subheadline.weight(.semibold))
        }
    }

    private func notice(_ text: String, icon: String) -> some View {
        Label(text, systemImage: icon).font(.footnote)
            .padding(12).frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.blue.opacity(0.09)).clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var connectionView: some View {
        NavigationStack {
            Form {
                Toggle("Use shared API", isOn: $model.useAPI)
                Section("Backend URL") {
                    TextField("http://127.0.0.1:8000", text: $model.baseURL)
                        .keyboardType(.URL).textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("Simulator: use the Mac's localhost. Physical iPhone: use the Mac's LAN address on the same network.")
                        .font(.caption)
                }
                Section("Recommendations") {
                    Toggle("Enable POST /recommendations", isOn: $model.recommendationsEnabled)
                    Text("Enable to request parking options from the shared backend. Historical estimates require the backend dataset.")
                        .font(.caption)
                }
            }
            .navigationTitle("Connection")
            .toolbar { Button("Done") { showConnection = false } }
        }
    }
}
