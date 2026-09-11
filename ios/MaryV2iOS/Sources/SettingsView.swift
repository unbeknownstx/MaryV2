import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var coreURL = AppConfiguration.coreURL
    @State private var token = AppConfiguration.token
    @State private var conversationID = AppConfiguration.conversationID
    @State private var speakResponses = AppConfiguration.speakResponses

    var body: some View {
        NavigationStack {
            ZStack {
                MaryBackground()
                Form {
                    Section("Mary Core") {
                        TextField("https://…", text: $coreURL)
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                            .autocorrectionDisabled()

                        SecureField("Core credential", text: $token)

                        TextField("Conversation ID", text: $conversationID)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                    }

                    Section("Voice") {
                        Toggle("Speak Mary's responses", isOn: $speakResponses)
                        LabeledContent(
                            "Core TTS",
                            value: app.voiceServerAvailable
                                ? app.voiceProvider
                                : "Unavailable"
                        )
                        Text(
                            "Microphone capture and speech recognition stay on this iPhone. "
                            + "Only the transcript is sent to Mary Core; provider API keys remain server-side."
                        )
                        .font(.caption)
                        .foregroundStyle(.secondary)

                        if let voiceError = app.lastVoiceError,
                           !voiceError.isEmpty {
                            Text(voiceError)
                                .font(.caption)
                                .foregroundStyle(.orange)
                        }
                    }

                    Section("This surface") {
                        LabeledContent("Surface", value: "Native iPhone")
                        LabeledContent("Device", value: String(app.deviceID.prefix(22)))
                        LabeledContent("Connection", value: app.statusText)
                        LabeledContent("Presence", value: app.performanceMode.title)
                        LabeledContent(
                            "Architecture",
                            value: app.coreVersion.isEmpty ? "Unknown" : app.coreVersion
                        )
                    }

                    Section("Advanced") {
                        NavigationLink("Core diagnostics") {
                            WorkspaceDetailView(kind: .advanced)
                                .environmentObject(app)
                        }
                    }

                    Section("Security") {
                        Text(
                            "The Mary Core credential is stored in iOS Keychain. "
                            + "Provider credentials are never stored in the app."
                        )
                        .foregroundStyle(.secondary)
                    }
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Mary Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        AppConfiguration.speakResponses = speakResponses
                        Task {
                            await app.saveSettings(
                                coreURL: coreURL,
                                token: token,
                                conversationID: conversationID
                            )
                            dismiss()
                        }
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}
