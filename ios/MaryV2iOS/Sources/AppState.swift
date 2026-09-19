import SwiftUI
import Foundation
import Combine
import CryptoKit
import UIKit

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
    @Published var socialStatusData: [String: Any] = [:]
    @Published var socialProposalData: [String: Any] = [:]
    @Published var lastDeliveryPlan: [String: Any] = [:]
    @Published var lastPerformancePacket: [String: Any] = [:]
    @Published var surfacePerformanceData: [String: Any] = [:]

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

    var relationship: RelationalSnapshot {
        CoreProjection.relationalSnapshot(dashboardData)
    }

    var presentationExpression: String {
        let reaction = CoreProjection.dict(lastPerformancePacket["pre_reaction"])
        let delivery = CoreProjection.dict(lastPerformancePacket["delivery"])
        let value = CoreProjection.string(
            reaction["expression"]
            ?? delivery["avatar_expression"]
            ?? lastDeliveryPlan["avatar_expression"]
        )
        return value.isEmpty ? "neutral" : value.lowercased()
    }

    var presentationGaze: String {
        let reaction = CoreProjection.dict(lastPerformancePacket["pre_reaction"])
        let delivery = CoreProjection.dict(lastPerformancePacket["delivery"])
        let value = CoreProjection.string(
            reaction["gaze_style"]
            ?? delivery["gaze_style"]
            ?? lastDeliveryPlan["gaze_style"]
        )
        return value.isEmpty ? "engaged" : value.lowercased()
    }

    var presentationHeadStyle: String {
        let reaction = CoreProjection.dict(lastPerformancePacket["pre_reaction"])
        let delivery = CoreProjection.dict(lastPerformancePacket["delivery"])
        let value = CoreProjection.string(
            reaction["head_style"]
            ?? delivery["head_style"]
            ?? lastDeliveryPlan["head_style"]
        )
        return value.isEmpty ? "natural" : value.lowercased()
    }

    var presentationEnergy: Double {
        let delivery = CoreProjection.dict(lastPerformancePacket["delivery"])
        let raw = delivery["energy"] ?? lastDeliveryPlan["energy"]
        if let value = raw as? Double { return min(1, max(0, value)) }
        if let value = raw as? NSNumber { return min(1, max(0, value.doubleValue)) }
        return 0.4
    }

    private func applyTurnPresentation(_ result: TurnResponse) {
        lastDeliveryPlan = result.deliveryPlan
        lastPerformancePacket = result.performancePacket
        surfacePerformanceData = result.surfacePerformance
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

    func prepareSharedActivity(_ activity: SharedLifeActivity) {
        Task { await beginSharedActivity(activity) }
    }

    func beginSharedActivity(_ activity: SharedLifeActivity) async {
        guard let client else {
            lastError = "Connect Mary Core first."
            return
        }
        do {
            _ = try await client.runtimeAction(
                "shared_activity.start",
                args: [
                    "activity_type": activity.rawValue,
                    "title": activity.title,
                    "context": activity.prompt,
                ]
            )
            draft = activity.prompt
            selectedTab = .chat
            lastError = nil
            UIImpactFeedbackGenerator(style: .soft).impactOccurred()
            await refreshHome()
        } catch {
            lastError = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    func completeSharedActivity() async {
        guard let client else { return }
        let current = relationship.activeActivityTitle
        do {
            _ = try await client.runtimeAction(
                "shared_activity.complete",
                args: [
                    "summary": current.isEmpty
                        ? "Mary and her creator completed shared time together."
                        : "Mary and her creator completed: \(current)",
                    "importance": 0.8,
                ]
            )
            lastError = nil
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            await refreshHome()
        } catch {
            lastError = error.localizedDescription
        }
    }

    func cancelSharedActivity() async {
        guard let client else { return }
        do {
            _ = try await client.runtimeAction("shared_activity.cancel")
            lastError = nil
            await refreshHome()
        } catch {
            lastError = error.localizedDescription
        }
    }

    func setRelationshipMode(_ mode: String) async {
        guard let client else { return }
        do {
            _ = try await client.runtimeAction(
                "relationship.set_mode",
                args: ["mode": mode]
            )
            lastError = nil
            UISelectionFeedbackGenerator().selectionChanged()
            await refreshHome()
        } catch {
            lastError = error.localizedDescription
        }
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
            applyTurnPresentation(result)
            isConnected = true
            statusText = "Online"
            lastError = nil
            isSending = false
            UINotificationFeedbackGenerator().notificationOccurred(.success)

            if AppConfiguration.speakResponses {
                await speakMaryResponse(
                    result.response,
                    userText: text,
                    deliveryPlan: result.deliveryPlan
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
        userText: String? = nil,
        deliveryPlan: [String: Any] = [:]
    ) async {
        guard AppConfiguration.speakResponses else { return }

        if let client, voiceServerAvailable {
            do {
                let audio = try await client.synthesizeVoice(
                    text: text,
                    userText: userText,
                    deliveryPlan: deliveryPlan
                )
                voiceProvider = audio.provider
                voiceServerAvailable = true
                try playback.play(audio)
                lastVoiceError = nil
                return
            } catch {
                voiceServerAvailable = false
                lastVoiceError = error.localizedDescription
            }
        }

        do {
            try playback.speakDevice(text)
            voiceProvider = "iPhone voice"
            if let existing = lastVoiceError, !existing.isEmpty {
                lastVoiceError = existing + " Using iPhone voice fallback."
            } else {
                lastVoiceError = nil
            }
        } catch {
            lastVoiceError = error.localizedDescription
        }
    }

    func refreshVoiceStatus() async {
        guard let client else { return }
        do {
            let status = try await client.voiceStatus()
            let tts = CoreProjection.dict(status["tts"])
            voiceServerAvailable = CoreProjection.bool(
                tts["server_available"] ?? tts["enabled"]
            )
            voiceProvider = CoreProjection.string(tts["provider"])
            if voiceProvider.isEmpty { voiceProvider = "Core voice" }
            lastVoiceError = nil
        } catch {
            voiceServerAvailable = false
            voiceProvider = "iPhone voice"
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
            case .social:
                socialStatusData = try await client.runtimeAction("social.status")
                liveData = socialStatusData
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
            case .knowledge:
                let dashboard = try await client.dashboard()
                dashboardData = dashboard
                liveData = CoreProjection.dict(CoreProjection.dict(dashboard["system_fabric"])["knowledge"])
            case .procedures:
                let dashboard = try await client.dashboard()
                dashboardData = dashboard
                var continuity = CoreProjection.dict(
                    CoreProjection.dict(dashboard["system_fabric"])["continuity"]
                )
                continuity["review"] = try await client.runtimeAction(
                    "continuity.skill.status"
                )
                liveData = continuity
            case .modelLab:
                let dashboard = try await client.dashboard()
                dashboardData = dashboard
                let fabric = CoreProjection.dict(dashboard["system_fabric"])
                var models = CoreProjection.dict(fabric["models"])
                models["node_intelligence"] = CoreProjection.dict(
                    CoreProjection.dict(fabric["compute"])["node_intelligence"]
                )
                liveData = models
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

    func refreshSocialStatus() async {
        guard let client else { return }
        do {
            socialStatusData = try await client.runtimeAction("social.status")
            liveData = socialStatusData
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func proposeSocial(
        kind: String,
        brief: String,
        mediaSummary: String,
        tone: String = "",
        audienceText: String = ""
    ) async -> Bool {
        guard let client else { return false }
        let cleanBrief = brief.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanBrief.isEmpty else { return false }

        do {
            try? await client.renewSurface(foreground: true)
            let result = try await client.runtimeAction(
                "social.propose",
                args: [
                    "platform": "instagram",
                    "kind": kind,
                    "brief": cleanBrief,
                    "media_summary": mediaSummary,
                    "tone": tone,
                    "audience_text": audienceText,
                ]
            )
            socialProposalData = CoreProjection.dict(result["proposal"])
            liveData = result
            lastError = nil
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            await refreshSocialStatus()
            return true
        } catch {
            lastError = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            return false
        }
    }

    func approveSocial(
        proposalID: String,
        editedContent: String
    ) async -> Bool {
        guard let client, !proposalID.isEmpty else { return false }
        do {
            let result = try await client.runtimeAction(
                "social.approve",
                args: [
                    "proposal_id": proposalID,
                    "edited_content": editedContent,
                ]
            )
            socialProposalData = CoreProjection.dict(result["proposal"])
            lastError = nil
            await refreshSocialStatus()
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            return true
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }

    func rejectSocial(proposalID: String, reason: String = "") async -> Bool {
        guard let client, !proposalID.isEmpty else { return false }
        do {
            let result = try await client.runtimeAction(
                "social.reject",
                args: ["proposal_id": proposalID, "reason": reason]
            )
            socialProposalData = CoreProjection.dict(result["proposal"])
            lastError = nil
            await refreshSocialStatus()
            return true
        } catch {
            lastError = error.localizedDescription
            return false
        }
    }

    func speakSocialProposal() async {
        guard
            let client,
            !socialProposalData.isEmpty
        else { return }

        let text = CoreProjection.string(socialProposalData["content"])
        guard !text.isEmpty else { return }
        let deliveryPlan = CoreProjection.dict(socialProposalData["delivery_plan"])

        do {
            let audio = try await client.synthesizeVoice(
                text: text,
                deliveryPlan: deliveryPlan
            )
            voiceProvider = audio.provider
            voiceServerAvailable = true
            try playback.play(audio)
            lastVoiceError = nil
        } catch {
            voiceServerAvailable = false
            lastVoiceError = error.localizedDescription
            do {
                try playback.speakDevice(text)
                voiceProvider = "iPhone voice"
                lastVoiceError = (lastVoiceError ?? "Core voice unavailable.") + " Using iPhone voice fallback."
            } catch {
                lastVoiceError = error.localizedDescription
            }
        }
    }

    private func boundedCreatorImage(_ source: Data) -> Data? {
        guard var image = UIImage(data: source) else { return nil }

        func resized(_ image: UIImage, maxDimension: CGFloat) -> UIImage {
            let width = image.size.width
            let height = image.size.height
            let longest = max(width, height)
            guard longest > maxDimension, longest > 0 else { return image }
            let scale = maxDimension / longest
            let size = CGSize(width: max(1, width * scale), height: max(1, height * scale))
            let renderer = UIGraphicsImageRenderer(size: size)
            return renderer.image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        }

        image = resized(image, maxDimension: 1600)
        var quality: CGFloat = 0.78
        var encoded = image.jpegData(compressionQuality: quality)
        while let data = encoded, data.count > 1_350_000, quality > 0.42 {
            quality -= 0.08
            encoded = image.jpegData(compressionQuality: quality)
        }
        if let data = encoded, data.count <= 1_350_000 { return data }

        image = resized(image, maxDimension: 1200)
        quality = 0.66
        encoded = image.jpegData(compressionQuality: quality)
        while let data = encoded, data.count > 1_350_000, quality > 0.38 {
            quality -= 0.07
            encoded = image.jpegData(compressionQuality: quality)
        }
        guard let data = encoded, data.count <= 1_350_000 else { return nil }
        return data
    }

    func describeCreatorImage(_ source: Data) async -> String? {
        guard let client else {
            lastError = "Connect Mary Core in Settings first."
            return nil
        }
        guard let image = boundedCreatorImage(source) else {
            lastError = "That image could not be prepared within Mary's bounded vision limit."
            return nil
        }

        let digest = SHA256.hash(data: image)
            .map { String(format: "%02x", $0) }
            .joined()

        do {
            try? await client.renewSurface(foreground: true)
            let registered = try await client.runtimeAction(
                "perception.asset.register",
                args: [
                    "kind": "image",
                    "mime_type": "image/jpeg",
                    "content_sha256": digest,
                    "byte_count": image.count,
                ]
            )
            let asset = CoreProjection.dict(registered["asset"])
            let assetID = CoreProjection.string(asset["asset_id"])
            guard !assetID.isEmpty else {
                throw MaryClientError.invalidResponse
            }

            let dispatched = try await client.dispatchCapability(
                "sensor.image_describe",
                intent: "Describe one creator-selected image as factual creative evidence for Mary.",
                args: [
                    "image_base64": image.base64EncodedString(),
                    "mime_type": "image/jpeg",
                    "mode": "creative",
                    "asset_id": assetID,
                ]
            )
            let initialTask = CoreProjection.dict(dispatched["task"])
            let taskID = CoreProjection.string(initialTask["task_id"])
            guard !taskID.isEmpty else {
                throw MaryClientError.invalidResponse
            }

            for _ in 0..<90 {
                let statusPayload = try await client.capabilityTaskStatus(taskID)
                let task = CoreProjection.dict(statusPayload["task"])
                let status = CoreProjection.string(task["status"]).lowercased()
                if status == "completed" {
                    let result = CoreProjection.dict(task["result"])
                    let description = CoreProjection.string(result["description"])
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !description.isEmpty else {
                        lastError = "The vision node completed without a usable description."
                        return nil
                    }
                    lastError = nil
                    return description
                }
                if ["failed", "rejected", "expired"].contains(status) {
                    let detail = CoreProjection.string(task["error"])
                    lastError = detail.isEmpty
                        ? "Mary's configured vision node could not describe this image."
                        : detail
                    return nil
                }
                try await Task.sleep(nanoseconds: 500_000_000)
            }

            lastError = "Mary's vision task did not finish within the bounded wait."
            return nil
        } catch {
            lastError = error.localizedDescription
            return nil
        }
    }

    func reconcileWorldBelief(_ beliefID: String) async -> Bool {
        guard let client else { return false }
        let clean = beliefID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return false }
        do {
            _ = try await client.runtimeAction(
                "world.reconcile",
                args: ["belief_id": clean]
            )
            lastError = nil
            await loadWorkspace(.world)
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            return true
        } catch {
            lastError = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            return false
        }
    }

    func approveSkillCandidate(_ skillID: String) async -> Bool {
        await mutateSkillCandidate(
            action: "continuity.skill.approve",
            skillID: skillID
        )
    }

    func rejectSkillCandidate(_ skillID: String) async -> Bool {
        await mutateSkillCandidate(
            action: "continuity.skill.reject",
            skillID: skillID
        )
    }

    func reviseApprovedSkill(
        _ skillID: String,
        reason: String,
        steps: [String]
    ) async -> Bool {
        guard let client else { return false }
        let cleanID = skillID.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanReason = reason.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanSteps = Array(
            steps
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
                .prefix(32)
        )
        guard !cleanID.isEmpty, !cleanReason.isEmpty else { return false }

        do {
            var args: [String: Any] = [
                "skill_id": cleanID,
                "reason": String(cleanReason.prefix(600)),
            ]
            if !cleanSteps.isEmpty {
                args["steps"] = cleanSteps.map { String($0.prefix(240)) }
            }
            _ = try await client.runtimeAction(
                "continuity.skill.revise",
                args: args
            )
            lastError = nil
            await loadWorkspace(.procedures)
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            return true
        } catch {
            lastError = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            return false
        }
    }

    private func mutateSkillCandidate(
        action: String,
        skillID: String
    ) async -> Bool {
        guard let client else { return false }
        let clean = skillID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return false }
        do {
            _ = try await client.runtimeAction(
                action,
                args: ["skill_id": clean]
            )
            lastError = nil
            await loadWorkspace(.procedures)
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            return true
        } catch {
            lastError = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            return false
        }
    }

    func runModelExperiment(
        experimentID: String,
        prompt: String
    ) async -> [String: Any]? {
        guard let client else {
            lastError = "Connect Mary Core in Settings first."
            return nil
        }
        let experiment = experimentID.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanPrompt = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !experiment.isEmpty, !cleanPrompt.isEmpty else {
            lastError = "Choose a trial-ready experiment and enter a prompt."
            return nil
        }

        do {
            let dispatched = try await client.runtimeAction(
                "model.experiment.dispatch",
                args: [
                    "experiment_id": experiment,
                    "prompt": String(cleanPrompt.prefix(12_000)),
                    "max_tokens": 512,
                    "temperature": 0.7,
                ]
            )
            let initialTask = CoreProjection.dict(dispatched["task"])
            let taskID = CoreProjection.string(initialTask["task_id"])
            guard !taskID.isEmpty else {
                throw MaryClientError.invalidResponse
            }

            for _ in 0..<120 {
                let statusPayload = try await client.capabilityTaskStatus(taskID)
                let task = CoreProjection.dict(statusPayload["task"])
                let status = CoreProjection.string(task["status"]).lowercased()

                if status == "completed" {
                    let result = CoreProjection.dict(task["result"])
                    let content = CoreProjection.string(result["content"])
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !content.isEmpty else {
                        lastError = "The model experiment completed without usable output."
                        return nil
                    }
                    lastError = nil
                    return result
                }

                if ["failed", "rejected", "expired"].contains(status) {
                    let detail = CoreProjection.string(task["error"])
                    lastError = detail.isEmpty
                        ? "The model experiment ended as \(status)."
                        : detail
                    return nil
                }

                try await Task.sleep(nanoseconds: 500_000_000)
            }

            lastError = "The model experiment is still running on the selected node."
            return nil
        } catch {
            lastError = error.localizedDescription
            return nil
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
