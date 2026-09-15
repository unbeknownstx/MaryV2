import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var app: AppState
    @State private var url = AppConfiguration.coreURL
    @State private var token = AppConfiguration.token
    @State private var conversation = AppConfiguration.conversationID
    @State private var speak = AppConfiguration.speakResponses
    var body: some View {
        NavigationStack {
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
    }
}
