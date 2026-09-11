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
    @Published var coreVersion = ""
    @Published var selectedTab: MainTab = .home
    @Published var conversationMode: ConversationMode = .adaptive
    @Published var performanceMode: PerformanceMode = .private
    @Published var modalRoute: AppModal?
    @Published var activeWorkspace: WorkspaceKind?
    @Published var lastError: String?
    @Published var lastVoiceError: String?
    @Published var voiceProvider = "Core voice"
    @Published var voiceServerAvailable = false
    @Published var dashboardData: [String: Any] = [:]
    @Published var workspaceData: [String: Any] = [:]
    @Published var liveData: [String: Any] = [:]
    @Published var searchResult: [String: Any] = [:]

    let voice = VoiceCapture()
    let playback = VoicePlayback()

    private var client: MaryCoreClient?
    private var renewTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()
    private var surfaceForeground = true

    init() {
        voice.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
        playback.objectWillChange
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)
    }

    deinit {
        renewTask?.cancel()
    }

    var conversationID: String { AppConfiguration.conversationID }
    var deviceID: String { AppConfiguration.deviceID }

    var phase: PresencePhase {
        if !isConnected { return .offline }
        if voice.isListening || voice.isTranscribing { return .listening }
        if isSending { return .thinking }
        if playback.isPlaying { return .speaking }
        return .idle
    }

    var snapshot: CompanionSnapshot {
        CoreProjection.companionSnapshot(
            dashboard: dashboardData,
            workspace: workspaceData,
            voiceReady: voiceServerAvailable
        )
    }

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

        let nextClient = MaryCoreClient(
            baseURL: url,
            token: token,
            deviceID: deviceID
        )
        client = nextClient

        do {
            let health = try await nextClient.health()
            coreLabel = CoreProjection.string(health["service"] ?? health["name"])
            if coreLabel.isEmpty { coreLabel = "mary-core" }
            coreVersion = CoreProjection.string(health["architecture"] ?? health["version"])

            try await nextClient.registerSurface(foreground: surfaceForeground)
            if surfaceForeground {
                try? await nextClient.wakeSurface()
            }
            performanceMode = try await nextClient.performanceContext()

            isConnected = true
            statusText = "Online"
            lastError = nil

            async let voiceRefresh: Void = refreshVoiceStatus()
            async let homeRefresh: Void = refreshHome()
            _ = await (voiceRefresh, homeRefresh)

            if surfaceForeground {
                startRenewLoop()
            }
        } catch {
            isConnected = false
            statusText = "Offline"
            lastError = error.localizedDescription
            stopRenewLoop()
        }
    }

    func setSurfaceActive(_ active: Bool) async {
        surfaceForeground = active
        guard let client else {
            if active { await connect() }
            return
        }

        if active {
            do {
                try await client.registerSurface(foreground: true)
                try? await client.wakeSurface()
                isConnected = true
                statusText = "Online"
                startRenewLoop()
                await refreshHome()
            } catch {
                isConnected = false
                statusText = "Offline"
                lastError = error.localizedDescription
            }
        } else {
            stopRenewLoop()
            playback.stop()
            voice.cancel()
            do {
                try await client.setSurfaceVisibility(
                    foreground: false,
                    visible: false
                )
            } catch {
                // Background lifecycle is best effort; the short Core lease
                // still expires safely if the app was suspended mid-request.
            }
        }
    }

    func disconnectSurface() async {
        stopRenewLoop()
        guard let client else { return }
        try? await client.disconnectSurface()
    }

    func saveSettings(
        coreURL: String,
        token: String,
        conversationID: String
    ) async {
        AppConfiguration.coreURL =
            coreURL.trimmingCharacters(in: .whitespacesAndNewlines)
        AppConfiguration.token = token
        let id = conversationID.trimmingCharacters(in: .whitespacesAndNewlines)
        AppConfiguration.conversationID =
            id.isEmpty ? "creator-primary" : id
        modalRoute = nil
        await connect()
    }

    func send(
        text explicitText: String? = nil,
        voiceInput: Bool = false
    ) async {
        let source = explicitText ?? draft
        let text = source.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }

        guard let client else {
            lastError = "Connect Mary Core in Settings first."
            modalRoute = .settings
            return
        }

        if explicitText == nil { draft = "" }
        messages.append(MaryMessage(role: .user, text: text))
        isSending = true
        playback.stop()

        do {
            // A meaningful turn also refreshes this exact creator surface.
            try? await client.renewSurface(foreground: true)

            let result = try await client.turn(
                text: text,
                conversationID: AppConfiguration.conversationID,
                mode: conversationMode,
                voiceInput: voiceInput
            )
            messages.append(
                MaryMessage(role: .mary, text: result.response)
            )
            isConnected = true
            statusText = "Online"
            lastError = nil
            isSending = false

            if AppConfiguration.speakResponses, voiceServerAvailable {
                await speakMaryResponse(
                    result.response,
                    userText: text
                )
            }

            await refreshHome()
        } catch {
            messages.append(
                MaryMessage(
                    role: .system,
                    text: error.localizedDescription
                )
            )
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
        let text = voice.transcript
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        voice.transcript = ""
        await send(text: text, voiceInput: true)
    }

    func speakMaryResponse(
        _ text: String,
        userText: String? = nil
    ) async {
        guard let client, AppConfiguration.speakResponses else { return }
        do {
            let audio = try await client.synthesizeVoice(
                text: text,
                userText: userText
            )
            voiceProvider = audio.provider
            voiceServerAvailable = true
            try playback.play(audio)
            lastVoiceError = nil
        } catch {
            // TTS is presentation only. A voice outage must never make the
            // canonical chat/Core appear offline.
            lastVoiceError = error.localizedDescription
        }
    }

    func refreshVoiceStatus() async {
        guard let client else { return }
        do {
            let status = try await client.voiceStatus()
            let tts = CoreProjection.dict(status["tts"])
            voiceServerAvailable = CoreProjection.bool(tts["enabled"])
            voiceProvider = CoreProjection.string(tts["provider"])
            if voiceProvider.isEmpty { voiceProvider = "Core voice" }
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
            lastError = nil
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
            case .presence:
                liveData = try await client.runtimeAction("presence.scene.status")
            case .study, .research, .studio, .gallery:
                liveData = try await client.workspace()
            case .search:
                liveData = try await client.nodes()
            case .media:
                liveData = try await client.runtimeAction("integration.status")
            case .voiceAvatar:
                liveData = try await client.voiceStatus()
            case .devices:
                liveData = try await client.nodes()
            case .integrations:
                liveData = try await client.runtimeAction("integration.status")
            case .world:
                liveData = try await client.runtimeAction("world.status")
            case .training:
                liveData = try await client.runtimeAction("training.feedback.status")
            case .advanced:
                liveData = try await client.dashboard()
            }
            lastError = nil
        } catch {
            liveData = [:]
            lastError = error.localizedDescription
        }
    }

    func personalSearch(_ query: String) async {
        guard let client else { return }
        let clean = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return }

        do {
            searchResult = try await client.dispatchCapability(
                "personal_search",
                intent: "Search creator-approved personal files for: \(clean)",
                args: ["query": clean, "limit": 8]
            )
            liveData = searchResult
            lastError = nil
        } catch {
            searchResult = [:]
            lastError = error.localizedDescription
        }
    }

    func runWorkspaceAction(
        _ action: String,
        args: [String: Any]
    ) async -> Bool {
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
        guard surfaceForeground else { return }
        renewTask?.cancel()
        renewTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 60_000_000_000)
                guard !Task.isCancelled,
                      let self,
                      self.surfaceForeground,
                      let client = self.client
                else { continue }

                do {
                    try await client.renewSurface(foreground: true)
                } catch {
                    self.isConnected = false
                    self.statusText = "Offline"
                }
            }
        }
    }

    private func stopRenewLoop() {
        renewTask?.cancel()
        renewTask = nil
    }
}
