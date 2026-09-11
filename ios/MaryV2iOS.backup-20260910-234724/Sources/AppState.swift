import Foundation
import SwiftUI

@MainActor
final class AppState: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var isSending = false
    @Published var isOnline = false
    @Published var coreStatus = "Not connected"
    @Published var lastError: String?
    @Published var showingSettings = false

    let configuration = AppConfiguration()
    private var started = false

    func start() async {
        guard !started else { return }
        started = true
        if configuration.isConfigured { await connect() }
        else { showingSettings = true }
    }

    func connect() async {
        guard let client = makeClient() else {
            isOnline = false
            coreStatus = "Needs setup"
            return
        }
        do {
            let health = try await client.health()
            try await client.registerSurface()
            isOnline = health.ok ?? true
            coreStatus = "\(health.service ?? "mary-core")\(health.architecture.map { " · \($0)" } ?? "")"
            lastError = nil
        } catch {
            isOnline = false
            coreStatus = "Offline"
            lastError = error.localizedDescription
        }
    }

    func send(_ rawText: String) async {
        let text = rawText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }
        guard let client = makeClient() else {
            showingSettings = true
            return
        }

        messages.append(ChatMessage(role: .user, text: text))
        isSending = true
        lastError = nil

        do {
            let result = try await client.turn(text)
            messages.append(ChatMessage(role: .mary, text: result.response))
            isOnline = true
            try? await client.renewSurface(foreground: true, activity: true)
        } catch {
            messages.append(ChatMessage(role: .system, text: "Could not reach Mary: \(error.localizedDescription)"))
            isOnline = false
            lastError = error.localizedDescription
        }

        isSending = false
    }

    func saveConfiguration(coreURL: String, token: String, conversationID: String) async -> Bool {
        do {
            try configuration.save(coreURL: coreURL, token: token, conversationID: conversationID)
            showingSettings = false
            await connect()
            return isOnline
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }

    func handleScenePhase(_ phase: ScenePhase) async {
        guard let client = makeClient() else { return }
        switch phase {
        case .active:
            try? await client.registerSurface()
            await connect()
        case .inactive:
            try? await client.renewSurface(foreground: false, activity: false)
        case .background:
            try? await client.disconnectSurface()
        @unknown default:
            break
        }
    }

    private func makeClient() -> MaryCoreClient? {
        guard configuration.isConfigured, let baseURL = configuration.normalizedURL else { return nil }
        return MaryCoreClient(
            baseURL: baseURL,
            token: configuration.token,
            deviceID: configuration.deviceID,
            conversationID: configuration.conversationID
        )
    }
}
