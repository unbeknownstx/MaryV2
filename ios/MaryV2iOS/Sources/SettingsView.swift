import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var app: AppState
    @State private var coreURL = AppConfiguration.coreURL
    @State private var token = AppConfiguration.token
    @State private var conversationID = AppConfiguration.conversationID
    @State private var speakResponses = AppConfiguration.speakResponses

    var body: some View {
        NavigationStack {
            Form {
                Section("Mary Core") {
                    TextField("https://…", text: $coreURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()

                    SecureField("Core token", text: $token)

                    TextField("Conversation ID", text: $conversationID)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section("This iPhone") {
                    LabeledContent("Surface", value: "ios_native")
                    LabeledContent("Device", value: String(app.deviceID.prefix(22)))
                    LabeledContent("Connection", value: app.statusText)
                    LabeledContent("Social stage", value: app.performanceMode.title)
                }

                Section("Voice") {
                    Toggle("Use Mary's Core voice", isOn: $speakResponses)
                        .onChange(of: speakResponses) { value in
                            AppConfiguration.speakResponses = value
                        }
                    LabeledContent(
                        "Core TTS",
                        value: app.voiceServerAvailable ? app.voiceProvider : "Unavailable"
                    )
                    Text("Push-to-talk records only on this iPhone, then uses Apple's on-device speech recognition. Raw microphone audio is not uploaded to Mary Core. Mary's reply audio is synthesized by Core, so provider keys never live on the phone.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if let voiceError = app.lastVoiceError, !voiceError.isEmpty {
                        Text(voiceError)
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                }

                Section {
                    Button("Save & Connect") {
                        AppConfiguration.speakResponses = speakResponses
                        Task {
                            await app.saveSettings(
                                coreURL: coreURL,
                                token: token,
                                conversationID: conversationID
                            )
                        }
                    }
                }

                Section("Security") {
                    Text("The Mary Core token stays in iOS Keychain. Provider API keys stay on Mary Core and are never stored in this app.")
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Mary Settings")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { app.showSettings = false }
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}
