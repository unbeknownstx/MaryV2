import SwiftUI
import Foundation
import Combine

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
    @Published var activeWorkspace: WorkspaceKind?
    @Published var lastError: String?
    @Published var lastVoiceError: String?
    @Published var voiceProvider = "Core voice"
    @Published var voiceServerAvailable = false
    @Published var dashboardData: [String: Any] = [:]
    @Published var workspaceData: [String: Any] = [:]
    @Published var liveData: [String: Any] = [:]

    let voice = VoiceCapture()
    let playback = VoicePlayback()
    private var client: MaryCoreClient?
    private var renewTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    init() {
        voice.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
        playback.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
    }

    var conversationID: String { AppConfiguration.conversationID }
    var deviceID: String { AppConfiguration.deviceID }

    func start() async {
        if messages.isEmpty {
            messages = [MaryMessage(role: .mary, text: "I'm here.")]
        }
        await connect()
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
            coreLabel = (h["service"] as? String) ?? (h["name"] as? String) ?? "mary-core"
            coreVersion = (h["architecture"] as? String) ?? (h["version"] as? String) ?? "13.3"
            try await c.registerSurface()
            performanceMode = try await c.performanceContext()
            isConnected = true
            statusText = "Online"
            lastError = nil
            await refreshVoiceStatus()
            await refreshHome()
            startRenewLoop()
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

    func send(text explicitText: String? = nil, voiceInput: Bool = false) async {
        let source = explicitText ?? draft
        let text = source.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }

        guard let client else {
            lastError = "Connect Mary Core in Settings first."
            showSettings = true
            return
        }

        if explicitText == nil { draft = "" }
        messages.append(MaryMessage(role: .user, text: text))
        isSending = true
        playback.stop()

        do {
            let result = try await client.turn(
                text: text,
                conversationID: AppConfiguration.conversationID,
                mode: conversationMode,
                voiceInput: voiceInput
            )
            messages.append(MaryMessage(role: .mary, text: result.response))
            isConnected = true
            statusText = "Online"
            lastError = nil
            isSending = false

            if AppConfiguration.speakResponses, voiceServerAvailable {
                await speakMaryResponse(result.response, userText: text)
            }
        } catch {
            messages.append(MaryMessage(role: .system, text: error.localizedDescription))
            isConnected = false
            statusText = "Offline"
            lastError = error.localizedDescription
            isSending = false
        }
    }

    func toggleVoiceCapture() async {
        if voice.isListening {
            let text = await voice.stopAndTranscribe()
            if let error = voice.errorText, text == nil {
                lastVoiceError = error
                return
            }
            guard let text, !text.isEmpty else { return }
            voice.transcript = text
            await send(text: text, voiceInput: true)
            voice.transcript = ""
        } else {
            playback.stop()
            await voice.start()
            if let error = voice.errorText {
                lastVoiceError = error
            } else {
                lastVoiceError = nil
            }
        }
    }

    func sendVoiceTranscript() async {
        let text = voice.transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        voice.transcript = ""
        await send(text: text, voiceInput: true)
    }

    func speakMaryResponse(_ text: String, userText: String? = nil) async {
        guard let client, AppConfiguration.speakResponses else { return }
        do {
            let audio = try await client.synthesizeVoice(text: text, userText: userText)
            voiceProvider = audio.provider
            voiceServerAvailable = true
            try playback.play(audio)
            lastVoiceError = nil
        } catch {
            // Voice is optional presentation. A TTS outage must never make the
            // canonical Core/chat surface appear offline.
            lastVoiceError = error.localizedDescription
        }
    }

    func refreshVoiceStatus() async {
        guard let client else { return }
        do {
            let status = try await client.voiceStatus()
            let tts = status["tts"] as? [String: Any] ?? [:]
            voiceServerAvailable = (tts["enabled"] as? Bool) ?? false
            voiceProvider = (tts["provider"] as? String) ?? "Core voice"
            lastVoiceError = nil
        } catch {
            voiceServerAvailable = false
            voiceProvider = "Core voice unavailable"
            lastVoiceError = error.localizedDescription
        }
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

    func refreshHome() async {
        guard let client else { return }
        do {
            async let dashboard = client.dashboard()
            async let workspace = client.workspace()
            dashboardData = try await dashboard
            workspaceData = try await workspace
        } catch {
            lastError = error.localizedDescription
        }
    }

    func loadWorkspace(_ kind: WorkspaceKind) async {
        guard let client else { return }
        activeWorkspace = kind

        do {
            switch kind {
            case .memories:
                liveData = try await client.memoryStatus()
            case .growth:
                liveData = try await client.growthStatus()
            case .personality:
                liveData = try await client.state()
            case .mind:
                liveData = try await client.runtimeAction("model.adapter.status")
            case .presence:
                liveData = try await client.runtimeAction("presence.scene.status")
            case .study, .research, .arcade, .studio:
                liveData = try await client.workspace()
            case .search:
                liveData = try await client.state()
            case .gallery:
                liveData = try await client.workspace()
            case .media:
                liveData = try await client.integrationStatus()
            case .voiceAvatar:
                liveData = try await client.voiceStatus()
            case .runtime:
                liveData = try await client.dashboard()
            case .nodes:
                liveData = try await client.nodes()
            case .stream:
                liveData = try await client.runtimeAction("stream.status")
            case .world:
                liveData = try await client.runtimeAction("world.status")
            case .integrations:
                liveData = try await client.runtimeAction("integration.status")
            case .training:
                liveData = try await client.runtimeAction("training.feedback.status")
            }
        } catch {
            liveData = [:]
            lastError = error.localizedDescription
        }
    }

    func runWorkspaceAction(_ action: String, args: [String: Any]) async -> Bool {
        guard let client else { return false }
        do {
            _ = try await client.workspaceAction(action, args: args)
            workspaceData = try await client.workspace()
            liveData = workspaceData
            return true
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }

    private func startRenewLoop() {
        renewTask?.cancel()
        renewTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 60_000_000_000)
                guard let self, let client = self.client else { continue }
                try? await client.renewSurface()
            }
        }
    }
}

private extension MaryCoreClient {
    func integrationStatus() async throws -> [String: Any] {
        try await runtimeAction("integration.status")
    }
}
