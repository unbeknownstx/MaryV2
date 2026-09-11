import Foundation

enum MaryClientError: LocalizedError {
    case invalidResponse
    case http(Int, String)
    case notConfigured
    case emptyVoiceAudio

    var errorDescription: String? {
        switch self {
        case .invalidResponse: return "Mary Core returned an invalid response."
        case let .http(code, body): return "Mary Core returned HTTP \(code): \(body)"
        case .notConfigured: return "Mary Core is not configured."
        case .emptyVoiceAudio: return "Mary Core returned no voice audio."
        }
    }
}

struct MaryVoiceAudio {
    let data: Data
    let mimeType: String
    let provider: String
    let model: String
    let cached: Bool
}

final class MaryCoreClient {
    let baseURL: URL
    let token: String
    let deviceID: String

    init(baseURL: URL, token: String, deviceID: String) {
        self.baseURL = baseURL
        self.token = token
        self.deviceID = deviceID
    }

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

    func health() async throws -> [String: Any] {
        try await get("/v1/health", authenticated: false)
    }

    func state() async throws -> [String: Any] { try await get("/v1/state") }
    func dashboard() async throws -> [String: Any] { try await get("/v1/dashboard") }
    func workspace() async throws -> [String: Any] { try await get("/v1/workspace") }
    func memoryStatus() async throws -> [String: Any] { try await get("/v1/memory/status") }
    func conversationStatus() async throws -> [String: Any] { try await get("/v1/conversation") }
    func growthStatus() async throws -> [String: Any] { try await get("/v1/growth") }
    func nodes() async throws -> [String: Any] { try await get("/v1/nodes") }
    func surfaces() async throws -> [String: Any] { try await get("/v1/creator-surfaces/status") }
    func voiceStatus() async throws -> [String: Any] { try await get("/v1/voice/status") }

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
            "requested_mode": mode.rawValue
        ]
        let data = try await send(
            try request(path: "/v1/turn", method: "POST", json: payload)
        )
        return try JSONDecoder().decode(TurnResponse.self, from: data)
    }

    func synthesizeVoice(
        text: String,
        userText: String? = nil,
        deliveryPlan: [String: Any] = [:]
    ) async throws -> MaryVoiceAudio {
        var payload: [String: Any] = [
            "text": text,
            "delivery_plan": deliveryPlan
        ]
        if let userText, !userText.isEmpty {
            payload["user_text"] = userText
        }
        let req = try request(
            path: "/v1/voice/synthesize",
            method: "POST",
            json: payload
        )
        let (data, response) = try await sendResponse(req)
        guard !data.isEmpty else { throw MaryClientError.emptyVoiceAudio }
        return MaryVoiceAudio(
            data: data,
            mimeType: response.value(forHTTPHeaderField: "Content-Type") ?? "application/octet-stream",
            provider: response.value(forHTTPHeaderField: "X-Mary-Voice-Provider") ?? "unknown",
            model: response.value(forHTTPHeaderField: "X-Mary-Voice-Model") ?? "unknown",
            cached: response.value(forHTTPHeaderField: "X-Mary-Voice-Cached") == "1"
        )
    }

    func runtimeAction(_ action: String, args: [String: Any] = [:]) async throws -> [String: Any] {
        try await post("/v1/runtime/action", json: [
            "action": action,
            "args": args,
            "device_id": deviceID
        ])
    }

    func workspaceAction(_ action: String, args: [String: Any] = [:]) async throws -> [String: Any] {
        try await post("/v1/workspace/action", json: [
            "action": action,
            "args": args,
            "device_id": deviceID
        ])
    }

    func performanceContext() async throws -> PerformanceMode {
        let json = try await runtimeAction("performance.context.status")
        let raw = (json["mode"] as? String) ?? "private"
        return PerformanceMode(rawValue: raw) ?? .private
    }

    func setPerformanceContext(_ mode: PerformanceMode) async throws -> PerformanceMode {
        let json = try await runtimeAction(
            "performance.context.set",
            args: ["mode": mode.rawValue]
        )
        let raw = (json["mode"] as? String) ?? mode.rawValue
        return PerformanceMode(rawValue: raw) ?? mode
    }

    func registerSurface(foreground: Bool = true) async throws {
        _ = try await post("/v1/creator-surfaces/register", json: [
            "surface_id": deviceID,
            "visible": true,
            "foreground": foreground,
            "activity": true,
            "lease_seconds": 120
        ])
    }

    func renewSurface(foreground: Bool = true) async throws {
        _ = try await post("/v1/creator-surfaces/renew", json: [
            "surface_id": deviceID,
            "visible": true,
            "foreground": foreground,
            "activity": true,
            "lease_seconds": 120
        ])
    }
}
