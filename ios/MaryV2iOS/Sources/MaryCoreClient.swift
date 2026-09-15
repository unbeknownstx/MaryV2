import Foundation

enum MaryClientError: LocalizedError {
    case invalidResponse, notConfigured, emptyVoiceAudio
    case http(Int, String)
    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Mary Core returned an invalid response."
        case .notConfigured: return "Mary Core is not configured."
        case .emptyVoiceAudio: return "Mary Core returned no voice audio."
        case let .http(code, body): return body.isEmpty ? "Mary Core returned HTTP \(code)." : "Mary Core returned HTTP \(code): \(body)"
        }
    }
}

final class MaryCoreClient {
    let baseURL: URL, token: String, deviceID: String
    init(baseURL: URL, token: String, deviceID: String) { self.baseURL = baseURL; self.token = token; self.deviceID = deviceID }

    private func request(_ path: String, method: String = "GET", json: [String: Any]? = nil, authenticated: Bool = true) throws -> URLRequest {
        var r = URLRequest(url: baseURL.appending(path: path)); r.httpMethod = method; r.timeoutInterval = 45
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        if authenticated && !token.isEmpty { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let json { r.setValue("application/json", forHTTPHeaderField: "Content-Type"); r.httpBody = try JSONSerialization.data(withJSONObject: json) }
        return r
    }
<<<<<<< HEAD
    private func send(_ r: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (d, response) = try await URLSession.shared.data(for: r)
        guard let http = response as? HTTPURLResponse else { throw MaryClientError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw MaryClientError.http(http.statusCode, String(data: d, encoding: .utf8) ?? "") }
        return (d, http)
    }
    private func object(_ d: Data) throws -> [String: Any] { (try JSONSerialization.jsonObject(with: d) as? [String: Any]) ?? [:] }
    func get(_ path: String, authenticated: Bool = true) async throws -> [String: Any] { try object(await send(try request(path, authenticated: authenticated)).0) }
    func post(_ path: String, _ json: [String: Any]) async throws -> [String: Any] { try object(await send(try request(path, method: "POST", json: json)).0) }
=======

    private func request(
        path: String,
        method: String = "GET",
        json: [String: Any]? = nil,
        authenticated: Bool = true
    ) throws -> URLRequest {
        var req = URLRequest(url: baseURL.appending(path: path))
        req.httpMethod = method
        req.timeoutInterval = 45
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        if authenticated, !token.isEmpty {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let json {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: json)
        }
        return req
    }

    private func sendResponse(_ req: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw MaryClientError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw MaryClientError.http(http.statusCode, body)
        }
        return (data, http)
    }

    private func send(_ req: URLRequest) async throws -> Data {
        try await sendResponse(req).0
    }

    private func object(_ data: Data) throws -> [String: Any] {
        (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    func get(_ path: String, authenticated: Bool = true) async throws -> [String: Any] {
        try object(await send(try request(path: path, authenticated: authenticated)))
    }

    func post(_ path: String, json: [String: Any]) async throws -> [String: Any] {
        try object(await send(try request(path: path, method: "POST", json: json)))
    }
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c

    func health() async throws -> [String: Any] { try await get("/v1/health", authenticated: false) }
    func state() async throws -> [String: Any] { try await get("/v1/state") }
    func dashboard() async throws -> [String: Any] { try await get("/v1/dashboard") }
    func workspace() async throws -> [String: Any] { try await get("/v1/workspace") }
    func memory() async throws -> [String: Any] { try await get("/v1/memory/status") }
    func growth() async throws -> [String: Any] { try await get("/v1/growth") }
    func conversation() async throws -> [String: Any] { try await get("/v1/conversation") }
    func nodes() async throws -> [String: Any] { try await get("/v1/nodes") }
    func surfaces() async throws -> [String: Any] { try await get("/v1/creator-surfaces/status") }
    func voiceStatus() async throws -> [String: Any] { try await get("/v1/voice/status") }

<<<<<<< HEAD
    func turn(text: String, conversationID: String, mode: ConversationMode, voiceInput: Bool) async throws -> TurnResponse {
        let payload: [String: Any] = ["text": text, "turn_id": "ios-\(UUID().uuidString.lowercased())", "conversation_id": conversationID, "device_id": deviceID, "surface": "ios_native", "voice_input": voiceInput, "requested_mode": mode.rawValue]
        let data = try await send(try request("/v1/turn", method: "POST", json: payload)).0
=======
    func turn(
        text: String,
        conversationID: String,
        mode: ConversationMode,
        voiceInput: Bool = false
    ) async throws -> TurnResponse {
        let payload: [String: Any] = [
            "text": text,
            "turn_id": "ios-\(UUID().uuidString.lowercased())",
            "conversation_id": conversationID,
            "device_id": deviceID,
            "surface": "ios_native",
            "voice_input": voiceInput,
            "requested_mode": mode.rawValue,
        ]
        let data = try await send(
            try request(path: "/v1/turn", method: "POST", json: payload)
        )
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
        return try JSONDecoder().decode(TurnResponse.self, from: data)
    }
    func runtimeAction(_ action: String, args: [String: Any] = [:]) async throws -> [String: Any] { try await post("/v1/runtime/action", ["action": action, "args": args, "device_id": deviceID]) }
    func workspaceAction(_ action: String, args: [String: Any] = [:]) async throws -> [String: Any] { try await post("/v1/workspace/action", ["action": action, "args": args, "device_id": deviceID]) }
    func capabilityPreview(_ capability: String, intent: String) async throws -> [String: Any] { try await post("/v1/nodes/task/preview", ["capability": capability, "intent": intent, "device_id": deviceID]) }
    func capabilityDispatch(_ capability: String, intent: String, args: [String: Any]) async throws -> [String: Any] { try await post("/v1/nodes/task/dispatch", ["capability": capability, "intent": intent, "args": args, "device_id": deviceID]) }
    func capabilityStatus(_ id: String) async throws -> [String: Any] { try await get("/v1/nodes/task/\(id)") }
    func registerSurface(foreground: Bool = true) async throws { _ = try await post("/v1/creator-surfaces/register", ["surface_id": deviceID, "visible": true, "foreground": foreground, "activity": true, "lease_seconds": 120]) }
    func renewSurface(foreground: Bool = true) async throws { _ = try await post("/v1/creator-surfaces/renew", ["surface_id": deviceID, "visible": true, "foreground": foreground, "activity": true, "lease_seconds": 120]) }

<<<<<<< HEAD
    func synthesizeVoice(text: String, userText: String? = nil) async throws -> MaryVoiceAudio {
        var p: [String: Any] = ["text": text, "delivery_plan": [:]]; if let userText { p["user_text"] = userText }
        let (d, h) = try await send(try request("/v1/voice/synthesize", method: "POST", json: p))
        guard !d.isEmpty else { throw MaryClientError.emptyVoiceAudio }
        return MaryVoiceAudio(data: d, mimeType: h.value(forHTTPHeaderField: "Content-Type") ?? "audio/mpeg", provider: h.value(forHTTPHeaderField: "X-Mary-Voice-Provider") ?? "Core voice", model: h.value(forHTTPHeaderField: "X-Mary-Voice-Model") ?? "", cached: h.value(forHTTPHeaderField: "X-Mary-Voice-Cached") == "1")
=======
    func synthesizeVoice(
        text: String,
        userText: String? = nil,
        deliveryPlan: [String: Any] = [:]
    ) async throws -> MaryVoiceAudio {
        var payload: [String: Any] = [
            "text": text,
            "delivery_plan": deliveryPlan,
        ]
        if let userText, !userText.isEmpty { payload["user_text"] = userText }
        let (data, response) = try await sendResponse(
            try request(path: "/v1/voice/synthesize", method: "POST", json: payload)
        )
        guard !data.isEmpty else { throw MaryClientError.emptyVoiceAudio }
        return MaryVoiceAudio(
            data: data,
            mimeType: response.value(forHTTPHeaderField: "Content-Type") ?? "application/octet-stream",
            provider: response.value(forHTTPHeaderField: "X-Mary-Voice-Provider") ?? "Core voice",
            model: response.value(forHTTPHeaderField: "X-Mary-Voice-Model") ?? "",
            cached: response.value(forHTTPHeaderField: "X-Mary-Voice-Cached") == "1"
        )
    }

    func runtimeAction(_ action: String, args: [String: Any] = [:]) async throws -> [String: Any] {
        try await post("/v1/runtime/action", json: [
            "action": action,
            "args": args,
            "device_id": deviceID,
        ])
    }

    func workspaceAction(_ action: String, args: [String: Any] = [:]) async throws -> [String: Any] {
        try await post("/v1/workspace/action", json: [
            "action": action,
            "args": args,
            "device_id": deviceID,
        ])
    }

    func dispatchCapability(
        _ capability: String,
        intent: String,
        args: [String: Any]
    ) async throws -> [String: Any] {
        try await post("/v1/nodes/task/dispatch", json: [
            "capability": capability,
            "intent": intent,
            "args": args,
            "device_id": deviceID,
        ])
    }

    func capabilityTaskStatus(_ taskID: String) async throws -> [String: Any] {
        try await get("/v1/nodes/task/\(taskID)")
    }

    func performanceContext() async throws -> PerformanceMode {
        let json = try await runtimeAction("performance.context.status")
        return PerformanceMode(rawValue: CoreProjection.string(json["mode"])) ?? .private
    }

    func setPerformanceContext(_ mode: PerformanceMode) async throws -> PerformanceMode {
        let json = try await runtimeAction(
            "performance.context.set",
            args: ["mode": mode.rawValue]
        )
        return PerformanceMode(rawValue: CoreProjection.string(json["mode"])) ?? mode
    }

    private func surfacePayload(
        foreground: Bool,
        visible: Bool,
        activity: Bool,
        leaseSeconds: Int = 120
    ) -> [String: Any] {
        [
            "surface_id": deviceID,
            "visible": visible,
            "foreground": foreground,
            "activity": activity,
            "lease_seconds": leaseSeconds,
        ]
    }

    func registerSurface(foreground: Bool = true) async throws {
        _ = try await post(
            "/v1/creator-surfaces/register",
            json: surfacePayload(
                foreground: foreground,
                visible: foreground,
                activity: true
            )
        )
    }

    func renewSurface(foreground: Bool = true) async throws {
        _ = try await post(
            "/v1/creator-surfaces/renew",
            json: surfacePayload(
                foreground: foreground,
                visible: foreground,
                activity: false
            )
        )
    }

    func setSurfaceVisibility(foreground: Bool, visible: Bool) async throws {
        _ = try await post(
            "/v1/creator-surfaces/visibility",
            json: surfacePayload(
                foreground: foreground,
                visible: visible,
                activity: foreground
            )
        )
    }

    func wakeSurface() async throws {
        _ = try await post(
            "/v1/creator-surfaces/wake",
            json: surfacePayload(
                foreground: true,
                visible: true,
                activity: true
            )
        )
    }

    func disconnectSurface() async throws {
        _ = try await post(
            "/v1/creator-surfaces/disconnect",
            json: ["surface_id": deviceID]
        )
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
    }
}
