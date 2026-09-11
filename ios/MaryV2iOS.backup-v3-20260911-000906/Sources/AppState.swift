import SwiftUI
import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var messages: [MaryMessage] = []
    @Published var draft = ""
    @Published var isConnected = false
    @Published var isSending = false
    @Published var statusText = "Offline"
    @Published var coreLabel = "mary-core"
    @Published var coreVersion = "13.3"
    @Published var selectedTab: MainTab = .chat
    @Published var conversationMode: ConversationMode = .adaptive
    @Published var performanceMode: PerformanceMode = .private
    @Published var showSettings = false
    @Published var showWorkspace = false
    @Published var lastError: String?

    private var client: MaryCoreClient?

    var conversationID: String { AppConfiguration.conversationID }
    var deviceID: String { AppConfiguration.deviceID }

    func start() async {
        await connect()
        if messages.isEmpty {
            messages = [MaryMessage(role: .mary, text: "I'm here.")]
        }
    }

    func connect() async {
        let raw = AppConfiguration.coreURL.trimmingCharacters(in: .whitespacesAndNewlines)
        let token = AppConfiguration.token

        guard let url = URL(string: raw), !raw.isEmpty, !token.isEmpty else {
            isConnected = false
            statusText = "Setup"
            return
        }

        let c = MaryCoreClient(baseURL: url, token: token, deviceID: deviceID)
        client = c

        do {
            let h = try await c.health()
            coreLabel = (h["name"] as? String) ?? "mary-core"
            coreVersion = (h["version"] as? String) ?? "13.3"
            try await c.registerSurface()
            performanceMode = try await c.performanceContext()
            isConnected = true
            statusText = "Online"
            lastError = nil
        } catch {
            isConnected = false
            statusText = "Offline"
            lastError = error.localizedDescription
        }
    }

    func saveSettings(coreURL: String, token: String, conversationID: String) async {
        AppConfiguration.coreURL = coreURL.trimmingCharacters(in: .whitespacesAndNewlines)
        AppConfiguration.token = token
        let id = conversationID.trimmingCharacters(in: .whitespacesAndNewlines)
        AppConfiguration.conversationID = id.isEmpty ? "creator-primary" : id
        showSettings = false
        await connect()
    }

    func send() async {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }

        guard let client else {
            lastError = "Connect Mary Core in Settings first."
            showSettings = true
            return
        }

        draft = ""
        messages.append(MaryMessage(role: .user, text: text))
        isSending = true

        do {
            let result = try await client.turn(
                text: text,
                conversationID: AppConfiguration.conversationID,
                mode: conversationMode
            )
            messages.append(MaryMessage(role: .mary, text: result.response))
            isConnected = true
            statusText = "Online"
            lastError = nil
        } catch {
            messages.append(MaryMessage(role: .system, text: error.localizedDescription))
            isConnected = false
            statusText = "Offline"
            lastError = error.localizedDescription
        }

        isSending = false
    }

    func changePerformanceMode(_ mode: PerformanceMode) async {
        guard let client else { return }
        do {
            performanceMode = try await client.setPerformanceContext(mode)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }
}
