import Foundation

struct ChatMessage: Identifiable, Equatable {
    enum Role { case user, mary, system }
    let id: UUID
    let role: Role
    let text: String
    let timestamp: Date

    init(id: UUID = UUID(), role: Role, text: String, timestamp: Date = Date()) {
        self.id = id
        self.role = role
        self.text = text
        self.timestamp = timestamp
    }
}

struct HealthResponse: Decodable {
    let ok: Bool?
    let service: String?
    let protocolVersion: String?
    let architecture: String?
    let instanceID: String?

    enum CodingKeys: String, CodingKey {
        case ok, service, architecture
        case protocolVersion = "protocol_version"
        case instanceID = "instance_id"
    }
}

struct TurnRequest: Encodable {
    let text: String
    let turnID: String
    let conversationID: String
    let deviceID: String
    let surface: String
    let voiceInput: Bool
    let requestedMode: String?

    enum CodingKeys: String, CodingKey {
        case text
        case turnID = "turn_id"
        case conversationID = "conversation_id"
        case deviceID = "device_id"
        case surface
        case voiceInput = "voice_input"
        case requestedMode = "requested_mode"
    }
}

struct TurnResponse: Decodable {
    let response: String
    let conversationID: String
    let turnID: String
    let effectiveMode: String

    enum CodingKeys: String, CodingKey {
        case response
        case conversationID = "conversation_id"
        case turnID = "turn_id"
        case effectiveMode = "effective_mode"
    }
}

struct CreatorSurfaceRequest: Encodable {
    let surfaceID: String
    let visible: Bool?
    let foreground: Bool?
    let activity: Bool
    let leaseSeconds: Double?

    enum CodingKeys: String, CodingKey {
        case surfaceID = "surface_id"
        case visible, foreground, activity
        case leaseSeconds = "lease_seconds"
    }
}
