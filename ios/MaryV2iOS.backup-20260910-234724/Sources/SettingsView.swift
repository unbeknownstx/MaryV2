import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var coreURL = ""
    @State private var token = ""
    @State private var conversationID = "creator-primary"
    @State private var saving = false
    @State private var localError: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Canonical Mary Core") {
                    TextField("https://…", text: $coreURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                    SecureField("Core token", text: $token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("Conversation", text: $conversationID)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section {
                    HStack {
                        Text("Device")
                        Spacer()
                        Text(appState.configuration.deviceID)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    HStack {
                        Text("Surface")
                        Spacer()
                        Text("ios").foregroundStyle(.secondary)
                    }
                } footer: {
                    Text("The phone stores only the Core credential. Provider API keys remain on Railway.")
                }

                if let error = localError ?? appState.lastError {
                    Section { Text(error).foregroundStyle(.red) }
                }

                Section {
                    Button {
                        saving = true
                        localError = nil
                        Task {
                            let success = await appState.saveConfiguration(
                                coreURL: coreURL,
                                token: token,
                                conversationID: conversationID
                            )
                            saving = false
                            if success { dismiss() }
                            else { localError = appState.lastError ?? "Could not connect to Mary Core." }
                        }
                    } label: {
                        HStack {
                            if saving { ProgressView() }
                            Text("Save & Connect")
                        }
                    }
                    .disabled(saving)
                }
            }
            .navigationTitle("Mary Setup")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if appState.configuration.isConfigured {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("Cancel") { dismiss() }
                    }
                }
            }
            .onAppear {
                coreURL = appState.configuration.coreURL
                conversationID = appState.configuration.conversationID
                token = appState.configuration.token
            }
        }
    }
}
