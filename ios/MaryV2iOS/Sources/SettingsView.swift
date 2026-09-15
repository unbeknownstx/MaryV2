import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var app: AppState
<<<<<<< HEAD
    @State private var url = AppConfiguration.coreURL
=======
    @Environment(\.dismiss) private var dismiss

    @State private var coreURL = AppConfiguration.coreURL
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
    @State private var token = AppConfiguration.token
    @State private var conversation = AppConfiguration.conversationID
    @State private var speak = AppConfiguration.speakResponses
    var body: some View {
        NavigationStack {
<<<<<<< HEAD
            Form {
                Section("Mary Core") {
                    TextField("Core URL", text: $url).textInputAutocapitalization(.never).keyboardType(.URL).autocorrectionDisabled()
                    SecureField("Core credential", text: $token)
                    TextField("Conversation", text: $conversation).textInputAutocapitalization(.never).autocorrectionDisabled()
                }
                Section("Voice") { Toggle("Use Mary's Core voice", isOn: $speak); LabeledContent("Provider", value: app.voiceProvider) }
                Section("This iPhone") { LabeledContent("Connection", value: app.isConnected ? "Online" : "Offline"); LabeledContent("Surface", value: "ios_native") }
                Section { Button("Save & Connect") { Task { await app.saveSettings(url: url, token: token, conversationID: conversation, speak: speak) } } }
                Section("Security") { Text("The Core credential stays in iOS Keychain. Provider API keys remain on Mary Core.").foregroundStyle(.secondary) }
            }
            .navigationTitle("Mary Settings")
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { app.modal = nil } } }
        }.preferredColorScheme(.dark)
    }
}

struct ConversationPickerView: View {
    @EnvironmentObject var app: AppState
    @State private var value = AppConfiguration.conversationID
    var body: some View {
        NavigationStack {
            Form {
                Section("Conversation") { TextField("Conversation ID", text: $value).textInputAutocapitalization(.never).autocorrectionDisabled(); Text("Conversation IDs separate short dialogue history. Mary's identity and canonical memory stay in Core.").font(.caption).foregroundStyle(.secondary) }
                Section { Button("Use Conversation") { AppConfiguration.conversationID = value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "creator-primary" : value; app.modal = nil } }
            }.navigationTitle("Conversation").toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { app.modal = nil } } }
        }.preferredColorScheme(.dark)
=======
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
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
    }
}
