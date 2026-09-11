import Foundation

struct MaryCoreClient {
    let baseURL: URL
    let token: String
    let deviceID: String
    let conversationID: String

    func health() async throws -> HealthResponse {
        try await get("/v1/health", authenticated: false, as: HealthResponse.self)
    }

    func turn(_ text: String, voiceInput: Bool = false) async throws -> TurnResponse {
        let body = TurnRequest(
            text: text,
            turnID: "turn_\(UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased())",
            conversationID: conversationID,
            deviceID: deviceID,
            surface: "ios",
            voiceInput: voiceInput,
            requestedMode: nil
        )
        return try await post("/v1/turn", body: body, as: TurnResponse.self)
    }

    func registerSurface() async throws {
        let body = CreatorSurfaceRequest(
            surfaceID: deviceID, visible: true, foreground: true,
            activity: true, leaseSeconds: 90
        )
        try await postIgnoringResponse("/v1/creator-surfaces/register", body: body)
    }

    func renewSurface(foreground: Bool, activity: Bool) async throws {
        let body = CreatorSurfaceRequest(
            surfaceID: deviceID, visible: true, foreground: foreground,
            activity: activity, leaseSeconds: 90
        )
        try await postIgnoringResponse("/v1/creator-surfaces/renew", body: body)
    }

    func disconnectSurface() async throws {
        let body = CreatorSurfaceRequest(
            surfaceID: deviceID, visible: false, foreground: false,
            activity: false, leaseSeconds: nil
        )
        try await postIgnoringResponse("/v1/creator-surfaces/disconnect", body: body)
    }

    private func endpoint(_ path: String) -> URL {
        baseURL.appendingPathComponent(path.hasPrefix("/") ? String(path.dropFirst()) : path)
    }

    private func get<T: Decodable>(_ path: String, authenticated: Bool, as type: T.Type) async throws -> T {
        var request = URLRequest(url: endpoint(path))
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if authenticated {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let data = try await perform(request)
        return try JSONDecoder().decode(type, from: data)
    }

    private func post<B: Encodable, R: Decodable>(_ path: String, body: B, as type: R.Type) async throws -> R {
        var request = URLRequest(url: endpoint(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(body)
        let data = try await perform(request)
        return try JSONDecoder().decode(type, from: data)
    }

    private func postIgnoringResponse<B: Encodable>(_ path: String, body: B) async throws {
        var request = URLRequest(url: endpoint(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(body)
        _ = try await perform(request)
    }

    private func perform(_ request: URLRequest) async throws -> Data {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw CoreError.invalidResponse }
        guard 200..<300 ~= http.statusCode else { throw CoreError.http(http.statusCode) }
        return data
    }

    enum CoreError: LocalizedError {
        case invalidResponse, http(Int)
        var errorDescription: String? {
            switch self {
            case .invalidResponse: return "Mary Core returned an invalid response."
            case .http(let status):
                return status == 401
                    ? "Mary Core rejected the credential (HTTP 401)."
                    : "Mary Core returned HTTP \(status)."
            }
        }
    }
}
