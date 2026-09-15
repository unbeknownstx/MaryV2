import SwiftUI
import Combine
import UIKit

@MainActor
final class AppState: ObservableObject {
    @Published var selectedTab: MainTab = .home
    @Published var modal: AppModal?
    @Published var messages: [MaryMessage] = [MaryMessage(role: .mary, text: "I'm here.")]
    @Published var draft = ""
    @Published var isConnected = false
    @Published var isSending = false
    @Published var coreLabel = "mary-core"
<<<<<<< HEAD
    @Published var coreVersion = "—"
    @Published var conversationMode: ConversationMode = .adaptive
    @Published var performanceMode: PerformanceMode = .private
    @Published var voiceProvider = "Core voice"
    @Published var voiceAvailable = false
    @Published var lastError: String?
    @Published var homeSnapshot: [String: Any] = [:]
    @Published var workspaceSnapshot: [String: Any] = [:]
    @Published var memorySnapshot: [String: Any] = [:]
    @Published var growthSnapshot: [String: Any] = [:]
    @Published var nodeSnapshot: [String: Any] = [:]
    @Published var presenceSnapshot: [String: Any] = [:]
    @Published var runtimeSnapshot: [String: Any] = [:]
    @Published var integrationSnapshot: [String: Any] = [:]
    @Published var activeCapabilityTask: [String: Any] = [:]
=======
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
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c

    let voice = VoiceCapture()
    let playback = VoicePlayback()

    private var client: MaryCoreClient?
    private var renewTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()
    private var surfaceForeground = true

    init() {
        voice.objectWillChange.sink { [weak self] _ in self?.objectWillChange.send() }.store(in: &cancellables)
        playback.objectWillChange.sink { [weak self] _ in self?.objectWillChange.send() }.store(in: &cancellables)
    }

    deinit {
        renewTask?.cancel()
    }

    var conversationID: String { AppConfiguration.conversationID }
    var deviceID: String { AppConfiguration.deviceID }
<<<<<<< HEAD
    var connectedNodeCount: Int {
        if let nodes = nodeSnapshot["nodes"] as? [[String: Any]] { return nodes.filter { ($0["connected"] as? Bool) == true }.count }
        return (nodeSnapshot["connected"] as? NSNumber)?.intValue ?? 0
=======

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

    var relationship: RelationalSnapshot {
        CoreProjection.relationalSnapshot(dashboardData)
    }

    func start() async {
        if messages.isEmpty {
            messages = [MaryMessage(role: .mary, text: "I'm here.")]
        }
        await connect()
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
    }

    func start() async { await connect(); await refreshAll() }

    func connect() async {
        let raw = AppConfiguration.coreURL.trimmingCharacters(in: .whitespacesAndNewlines)
        let token = AppConfiguration.token
<<<<<<< HEAD
        guard let url = URL(string: raw), !token.isEmpty else { isConnected = false; modal = .settings; return }
        let c = MaryCoreClient(baseURL: url, token: token, deviceID: deviceID); client = c
        do {
            let h = try await c.health(); coreLabel = (h["service"] as? String) ?? (h["name"] as? String) ?? "mary-core"; coreVersion = (h["architecture"] as? String) ?? (h["version"] as? String) ?? "—"
            try await c.registerSurface(); isConnected = true; lastError = nil
            if let mode = try? await c.runtimeAction("performance.context.status"), let rawMode = mode["mode"] as? String { performanceMode = PerformanceMode(rawValue: rawMode) ?? .private }
            await refreshVoice(); startRenewLoop()
        } catch { isConnected = false; lastError = error.localizedDescription }
    }

    func saveSettings(url: String, token: String, conversationID: String, speak: Bool) async {
        AppConfiguration.coreURL = url.trimmingCharacters(in: .whitespacesAndNewlines)
        AppConfiguration.token = token
        AppConfiguration.conversationID = conversationID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "creator-primary" : conversationID.trimmingCharacters(in: .whitespacesAndNewlines)
        AppConfiguration.speakResponses = speak
        modal = nil; await connect(); await refreshAll()
    }

    func refreshAll() async {
        guard let client else { return }
        async let dashboard = try? client.dashboard(); async let workspace = try? client.workspace(); async let memory = try? client.memory(); async let growth = try? client.growth(); async let nodes = try? client.nodes(); async let presence = try? client.runtimeAction("presence.scene.status"); async let integrations = try? client.runtimeAction("integration.status")
        homeSnapshot = await dashboard ?? [:]; runtimeSnapshot = homeSnapshot; workspaceSnapshot = await workspace ?? [:]; memorySnapshot = await memory ?? [:]; growthSnapshot = await growth ?? [:]; nodeSnapshot = await nodes ?? [:]; presenceSnapshot = await presence ?? [:]; integrationSnapshot = await integrations ?? [:]
        await refreshVoice()
    }

    func send(text explicit: String? = nil, voiceInput: Bool = false) async {
        let text = (explicit ?? draft).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }
        guard let client else { modal = .settings; return }
        if explicit == nil { draft = "" }
        messages.append(MaryMessage(role: .user, text: text)); isSending = true; playback.stop()
        do {
            let result = try await client.turn(text: text, conversationID: conversationID, mode: conversationMode, voiceInput: voiceInput)
            let reply = MaryMessage(role: .mary, text: result.response); messages.append(reply); isSending = false; isConnected = true
            if AppConfiguration.speakResponses && voiceAvailable { await speak(result.response, userText: text) }
        } catch { messages.append(MaryMessage(role: .system, text: "I couldn't reach Mary Core. \(error.localizedDescription)")); lastError = error.localizedDescription; isSending = false; isConnected = false }
=======

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

    func prepareSharedActivity(_ activity: SharedLifeActivity) {
        draft = activity.prompt
        selectedTab = .chat
        UIImpactFeedbackGenerator(style: .soft).impactOccurred()
    }

    func openChat(with prompt: String = "") {
        if !prompt.isEmpty { draft = prompt }
        selectedTab = .chat
        UISelectionFeedbackGenerator().selectionChanged()
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
        UIImpactFeedbackGenerator(style: .light).impactOccurred()

        do {
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
            UINotificationFeedbackGenerator().notificationOccurred(.success)

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
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
    }

    func toggleVoice() async {
        if voice.isListening {
            _ = try? await client?.runtimeAction("realtime.listening", args: ["active": false])
            if let text = await voice.stopAndTranscribe(), !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { await send(text: text, voiceInput: true) }
        } else {
<<<<<<< HEAD
            playback.stop(); _ = try? await client?.runtimeAction("realtime.listening", args: ["active": true]); await voice.start()
        }
    }

    func speak(_ text: String, userText: String? = nil) async {
        guard let client else { return }
        do { _ = try? await client.runtimeAction("realtime.speech_started"); let audio = try await client.synthesizeVoice(text: text, userText: userText); voiceProvider = audio.provider; voiceAvailable = true; try playback.play(audio) } catch { lastError = error.localizedDescription }
    }

    func setConversationMode(_ mode: ConversationMode) async { conversationMode = mode; _ = try? await client?.runtimeAction("conversation.set_mode", args: ["mode": mode.rawValue]) }
    func setPerformanceMode(_ mode: PerformanceMode) async { if let result = try? await client?.runtimeAction("performance.context.set", args: ["mode": mode.rawValue]), let raw = result["mode"] as? String { performanceMode = PerformanceMode(rawValue: raw) ?? mode } else { performanceMode = mode } }

    func runWorkspace(_ action: String, args: [String: Any]) async -> Bool {
=======
            playback.stop()
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
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
            UISelectionFeedbackGenerator().selectionChanged()
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
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
        guard let client else { return false }
        do { _ = try await client.workspaceAction(action, args: args); workspaceSnapshot = try await client.workspace(); return true } catch { lastError = error.localizedDescription; return false }
    }

    func searchPersonalFiles(_ query: String) async -> [String: Any] {
        guard let client else { return [:] }
        do {
            let preview = try await client.capabilityPreview("personal_search", intent: "Search connected personal files for \(query)")
            let dispatch = try await client.capabilityDispatch("personal_search", intent: "Search connected personal files for \(query)", args: ["query": query, "limit": 8])
            activeCapabilityTask = dispatch
            var result = dispatch; result["preview"] = preview; return result
        } catch { lastError = error.localizedDescription; return [:] }
    }

    func data(for kind: WorkspaceKind) -> [String: Any] {
        switch kind {
        case .memories: return memorySnapshot
        case .growth: return growthSnapshot
        case .presence: return presenceSnapshot
        case .nodes: return nodeSnapshot
        case .runtime: return runtimeSnapshot
        case .integrations: return integrationSnapshot
        case .voiceAvatar: return ["provider": voiceProvider, "available": voiceAvailable]
        default: return workspaceSnapshot
        }
    }

    func refresh(_ kind: WorkspaceKind) async { await refreshAll() }

    private func refreshVoice() async {
        guard let client else { return }
        if let status = try? await client.voiceStatus(), let tts = status["tts"] as? [String: Any] { voiceAvailable = (tts["enabled"] as? Bool) ?? false; voiceProvider = (tts["provider"] as? String) ?? "Core voice" }
    }

    private func startRenewLoop() {
<<<<<<< HEAD
        renewTask?.cancel(); renewTask = Task { [weak self] in while !Task.isCancelled { try? await Task.sleep(nanoseconds: 60_000_000_000); guard let self, let client = self.client else { continue }; try? await client.renewSurface() } }
=======
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
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
    }
}
