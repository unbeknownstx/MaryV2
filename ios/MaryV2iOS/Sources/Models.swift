import Foundation

struct MaryMessage: Identifiable, Equatable {
    enum Role { case user, mary, system }
    let id = UUID()
    let role: Role
    let text: String
}

struct TurnResponse: Codable {
    let response: String
    let conversation_id: String?
    let turn_id: String?
    let effective_mode: String?
    let display_hints: [String: JSONValue]?
}

enum JSONValue: Codable, Hashable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([String: JSONValue].self) { self = .object(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .null }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
}

enum PerformanceMode: String, CaseIterable, Identifiable {
    case `private`, casual, focus, stream, performance
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
    var isPublic: Bool { self == .stream || self == .performance }
    var symbol: String {
        switch self {
        case .private: return "person.fill"
        case .casual: return "cup.and.saucer.fill"
        case .focus: return "scope"
        case .stream: return "dot.radiowaves.left.and.right"
        case .performance: return "theatermasks.fill"
        }
    }
}

enum ConversationMode: String, CaseIterable, Identifiable {
    case adaptive, engaged, deep
    var id: String { rawValue }
    var label: String {
        switch self {
        case .adaptive: return "AUTO"
        case .engaged: return "TALK"
        case .deep: return "DEEP"
        }
    }
}

enum MainTab: String, CaseIterable, Identifiable {
    case home, chat, command, focus, more
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
    var symbol: String {
        switch self {
        case .home: return "house.fill"
        case .chat: return "bubble.left.and.bubble.right.fill"
        case .command: return "checkmark.square.fill"
        case .focus: return "scope"
        case .more: return "square.grid.2x2.fill"
        }
    }
}

enum WorkspaceKind: String, Identifiable, CaseIterable {
    case memories, growth, personality, mind, presence, study, search, research, arcade
    case studio, gallery, media, voiceAvatar, runtime, nodes, stream, world, integrations, training

    var id: String { rawValue }
    var title: String {
        switch self {
        case .memories: return "Memories"
        case .growth: return "Growth"
        case .personality: return "Personality"
        case .mind: return "Mind"
        case .presence: return "Presence"
        case .study: return "Study"
        case .search: return "Search"
        case .research: return "Research"
        case .arcade: return "Arcade"
        case .studio: return "Studio"
        case .gallery: return "Gallery"
        case .media: return "Media"
        case .voiceAvatar: return "Voice & Avatar"
        case .runtime: return "Runtime"
        case .nodes: return "Nodes"
        case .stream: return "Stream"
        case .world: return "World"
        case .integrations: return "Integrations"
        case .training: return "Training"
        }
    }
}
