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
}

enum PerformanceMode: String, CaseIterable, Identifiable {
    case `private`, casual, focus, stream, performance
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
    var subtitle: String {
        switch self {
        case .private: return "Creator only"
        case .casual: return "Relaxed creator chat"
        case .focus: return "Low interruption"
        case .stream: return "Public audience guard"
        case .performance: return "Public performance guard"
        }
    }
    var isPublic: Bool { self == .stream || self == .performance }
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
