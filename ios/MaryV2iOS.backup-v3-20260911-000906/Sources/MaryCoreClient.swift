import Foundation

enum MaryClientError: LocalizedError {
    case invalidResponse
    case http(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Mary Core returned an invalid response."
        case let .http(code, body):
            return "Mary Core returned HTTP \(code): \(body)"
        }
    }
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

    private func makeRequest(path: String, method: String = "GET", body: Data? = nil, authenticated: Bool = true) -> URLRequest {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        request.timeoutInterval = 35
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if body != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if authenticated, !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = body
        return request
    }

    private func send(_ request: URLRequest) async throws -> Data {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw MaryClientError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw MaryClientError.http(http.statusCode, body)
        }
        return data
    }

    func health() async throws -> [String: Any] {
        let data = try await send(makeRequest(path: "/v1/health", authenticated: false))
        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    func turn(text: String, conversationID: String, mode: ConversationMode) async throws -> TurnResponse {
        let payload: [String: Any] = [
            "text": text,
            "turn_id": "ios-\(UUID().uuidString.lowercased())",
            "conversation_id": conversationID,
            "device_id": deviceID,
            "surface": "ios_native",
            "voice_input": false,
            "requested_mode": mode.rawValue
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        let data = try await send(makeRequest(path: "/v1/turn", method: "POST", body: body))
        return try JSONDecoder().decode(TurnResponse.self, from: data)
    }

    func runtimeAction(_ action: String, args: [String: Any] = [:]) async throws -> [String: Any] {
        let payload: [String: Any] = [
            "action": action,
            "args": args,
            "device_id": deviceID
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        let data = try await send(makeRequest(path: "/v1/runtime/action", method: "POST", body: body))
        return (try JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    func performanceContext() async throws -> PerformanceMode {
        let json = try await runtimeAction("performance.context.status")
        let raw = (json["mode"] as? String) ?? "private"
        return PerformanceMode(rawValue: raw) ?? .private
    }

    func setPerformanceContext(_ mode: PerformanceMode) async throws -> PerformanceMode {
        let json = try await runtimeAction("performance.context.set", args: ["mode": mode.rawValue])
        let raw = (json["mode"] as? String) ?? mode.rawValue
        return PerformanceMode(rawValue: raw) ?? mode
    }

    func registerSurface() async throws {
        let payload: [String: Any] = [
            "surface_id": deviceID,
            "visible": true,
            "foreground": true,
            "activity": "ios_native",
            "lease_seconds": 120
        ]
        let body = try JSONSerialization.data(withJSONObject: payload)
        _ = try await send(makeRequest(path: "/v1/creator-surfaces/register", method: "POST", body: body))
    }
}
