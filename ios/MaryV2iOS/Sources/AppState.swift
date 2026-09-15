import SwiftUI
import Combine

@MainActor
final class AppState: ObservableObject {
    @Published var selectedTab: MainTab = .home
    @Published var modal: AppModal?
    @Published var messages: [MaryMessage] = [MaryMessage(role: .mary, text: "I'm here.")]
    @Published var draft = ""
    @Published var isConnected = false
    @Published var isSending = false
    @Published var coreLabel = "mary-core"
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

    let voice = VoiceCapture()
    let playback = VoicePlayback()
    private var client: MaryCoreClient?
    private var renewTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()

    init() {
        voice.objectWillChange.sink { [weak self] _ in self?.objectWillChange.send() }.store(in: &cancellables)
        playback.objectWillChange.sink { [weak self] _ in self?.objectWillChange.send() }.store(in: &cancellables)
    }

    var conversationID: String { AppConfiguration.conversationID }
    var deviceID: String { AppConfiguration.deviceID }
    var connectedNodeCount: Int {
        if let nodes = nodeSnapshot["nodes"] as? [[String: Any]] { return nodes.filter { ($0["connected"] as? Bool) == true }.count }
        return (nodeSnapshot["connected"] as? NSNumber)?.intValue ?? 0
    }

    func start() async { await connect(); await refreshAll() }

    func connect() async {
        let raw = AppConfiguration.coreURL.trimmingCharacters(in: .whitespacesAndNewlines)
        let token = AppConfiguration.token
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
    }

    func toggleVoice() async {
        if voice.isListening {
            _ = try? await client?.runtimeAction("realtime.listening", args: ["active": false])
            if let text = await voice.stopAndTranscribe(), !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { await send(text: text, voiceInput: true) }
        } else {
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
        renewTask?.cancel(); renewTask = Task { [weak self] in while !Task.isCancelled { try? await Task.sleep(nanoseconds: 60_000_000_000); guard let self, let client = self.client else { continue }; try? await client.renewSurface() } }
    }
}
