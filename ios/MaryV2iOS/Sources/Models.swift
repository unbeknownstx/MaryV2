import Foundation

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

enum ConversationMode: String, CaseIterable, Identifiable {
    case adaptive, engaged, deep
    var id: String { rawValue }
    var label: String { switch self { case .adaptive: return "AUTO"; case .engaged: return "TALK"; case .deep: return "DEEP" } }
}

enum PerformanceMode: String, CaseIterable, Identifiable {
    case `private`, casual, focus, stream, performance
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
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

enum WorkspaceKind: String, Identifiable, CaseIterable, Hashable {
    case memories, growth, personality, presence, study, search, research, studio, gallery, voiceAvatar, nodes, runtime, integrations, training, world, stream
    var id: String { rawValue }
    var title: String {
        switch self {
        case .memories: return "Memories"
        case .growth: return "Growth"
        case .personality: return "Personality"
        case .presence: return "Presence"
        case .study: return "Study"
        case .search: return "Search"
        case .research: return "Research"
        case .studio: return "Studio"
        case .gallery: return "Gallery"
        case .voiceAvatar: return "Voice & Avatar"
        case .nodes: return "Nodes"
        case .runtime: return "Runtime"
        case .integrations: return "Integrations"
        case .training: return "Training"
        case .world: return "World"
        case .stream: return "Stream"
        }
    }
    var subtitle: String {
        switch self {
        case .memories: return "Continuity and recall"
        case .growth: return "Learning and development"
        case .personality: return "Mary's current self"
        case .presence: return "Live situational context"
        case .study: return "Projects and review"
        case .search: return "Search your connected nodes"
        case .research: return "Persistent research threads"
        case .studio: return "Creative productions"
        case .gallery: return "Mary and project art"
        case .voiceAvatar: return "Speech and presentation"
        case .nodes: return "Mac and PC capability hosts"
        case .runtime: return "Core health at a glance"
        case .integrations: return "Connected services"
        case .training: return "Feedback and training signals"
        case .world: return "World context"
        case .stream: return "Public performance state"
        }
    }
    var symbol: String {
        switch self {
        case .memories: return "rectangle.stack.fill"
        case .growth: return "arrow.up.right.circle.fill"
        case .personality: return "sparkles"
        case .presence: return "dot.radiowaves.left.and.right"
        case .study: return "book.closed.fill"
        case .search: return "magnifyingglass"
        case .research: return "doc.text.magnifyingglass"
        case .studio: return "wand.and.stars"
        case .gallery: return "photo.on.rectangle.angled"
        case .voiceAvatar: return "waveform.and.mic"
        case .nodes: return "server.rack"
        case .runtime: return "gauge.with.dots.needle.67percent"
        case .integrations: return "link.circle.fill"
        case .training: return "checkmark.seal.fill"
        case .world: return "globe.americas.fill"
        case .stream: return "dot.radiowaves.left.and.right"
        }
    }
}

struct MaryMessage: Identifiable, Equatable {
    enum Role { case user, mary, system }
    let id: UUID
    let role: Role
    let text: String
    let createdAt: Date
    init(id: UUID = UUID(), role: Role, text: String, createdAt: Date = Date()) {
        self.id = id; self.role = role; self.text = text; self.createdAt = createdAt
    }
}

struct TurnResponse: Codable {
    let response: String
    let conversation_id: String?
    let turn_id: String?
    let effective_mode: String?
}

struct MaryVoiceAudio {
    let data: Data
    let mimeType: String
    let provider: String
    let model: String
    let cached: Bool
}

struct StatusChipModel: Identifiable {
    let id = UUID()
    let label: String
    let value: String
    let symbol: String
    let positive: Bool
}

struct InsightCard: Identifiable {
    let id = UUID()
    let title: String
    let detail: String
    let symbol: String
}

struct GalleryItem: Identifiable, Hashable {
    let id = UUID()
    let title: String
    let baseName: String
    let ext: String
}

enum AppModal: Identifiable {
    case settings, conversations
    var id: String { switch self { case .settings: return "settings"; case .conversations: return "conversations" } }
}
