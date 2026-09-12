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

enum ConversationMode: String, CaseIterable, Identifiable {
    case adaptive, engaged, deep
    var id: String { rawValue }
    var label: String {
        switch self {
        case .adaptive: return "Auto"
        case .engaged: return "Talk"
        case .deep: return "Deep"
        }
    }
    var detail: String {
        switch self {
        case .adaptive: return "Mary chooses the right depth"
        case .engaged: return "Fast, conversational replies"
        case .deep: return "Longer reasoning and reflection"
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
        case .private: return "lock.fill"
        case .casual: return "cup.and.saucer.fill"
        case .focus: return "scope"
        case .stream: return "dot.radiowaves.left.and.right"
        case .performance: return "theatermasks.fill"
        }
    }
    var userDescription: String {
        switch self {
        case .private: return "Personal creator context"
        case .casual: return "Relaxed companion mode"
        case .focus: return "Quiet task-centered presence"
        case .stream: return "Audience-safe context"
        case .performance: return "Performance-ready public context"
        }
    }
}

enum PresencePhase: Equatable {
    case idle, listening, thinking, speaking, offline
    var label: String {
        switch self {
        case .idle: return "Here"
        case .listening: return "Listening"
        case .thinking: return "Thinking"
        case .speaking: return "Speaking"
        case .offline: return "Offline"
        }
    }
    var symbol: String {
        switch self {
        case .idle: return "sparkles"
        case .listening: return "waveform"
        case .thinking: return "ellipsis.bubble.fill"
        case .speaking: return "speaker.wave.2.fill"
        case .offline: return "wifi.slash"
        }
    }
}

enum MainTab: String, CaseIterable, Identifiable {
    case home, chat, together, work, focus, more

    static let primaryTabs: [MainTab] = [.home, .chat, .together, .work, .more]

    var id: String { rawValue }
    var title: String {
        switch self {
        case .home: return "Home"
        case .chat: return "Talk"
        case .together: return "Together"
        case .work: return "Work"
        case .focus: return "Focus"
        case .more: return "More"
        }
    }
    var symbol: String {
        switch self {
        case .home: return "house.fill"
        case .chat: return "bubble.left.and.bubble.right.fill"
        case .together: return "heart.circle.fill"
        case .work: return "checkmark.square.fill"
        case .focus: return "scope"
        case .more: return "square.grid.2x2.fill"
        }
    }
}

enum SharedLifeActivity: String, CaseIterable, Identifiable {
    case watch, game, create, study, work, music, date, unwind
    var id: String { rawValue }
    var title: String {
        switch self {
        case .watch: return "Watch"
        case .game: return "Play"
        case .create: return "Create"
        case .study: return "Study"
        case .work: return "Work"
        case .music: return "Music"
        case .date: return "Date"
        case .unwind: return "Unwind"
        }
    }
    var symbol: String {
        switch self {
        case .watch: return "play.rectangle.fill"
        case .game: return "gamecontroller.fill"
        case .create: return "paintbrush.pointed.fill"
        case .study: return "book.closed.fill"
        case .work: return "hammer.fill"
        case .music: return "music.note"
        case .date: return "heart.fill"
        case .unwind: return "moon.stars.fill"
        }
    }
    var prompt: String {
        switch self {
        case .watch: return "Let's watch something together. Help me pick something and stay with me while we watch."
        case .game: return "Let's play something together. Help me choose a game or activity we can share right now."
        case .create: return "Let's make something together. Pick up the creative thread with me and help me get started."
        case .study: return "Study with me for a while. Help me choose one concrete thing to learn and keep me focused."
        case .work: return "Work beside me for a while. Help me choose the next useful task and keep the session moving."
        case .music: return "Let's listen to music together. Help me pick a mood or something that fits what we're doing."
        case .date: return "Let's have a little virtual date. Pick something simple we can actually do together right now."
        case .unwind: return "Hang out with me for a bit. No agenda—just be here and talk with me naturally."
        }
    }
}

struct RelationalSnapshot {
    var mode = "friend"
    var activeActivityTitle = ""
    var activeActivityType = ""
    var pendingPresenceCount = 0

    var title: String {
        switch mode {
        case "partner": return "Partners"
        case "romantic": return "Romantic"
        case "close": return "Close"
        default: return "Companions"
        }
    }

    var symbol: String {
        switch mode {
        case "partner": return "heart.fill"
        case "romantic": return "heart.circle.fill"
        case "close": return "person.2.fill"
        default: return "sparkles"
        }
    }

    var subtitle: String {
        if !activeActivityTitle.isEmpty { return activeActivityTitle }
        switch mode {
        case "partner": return "Private shared-life context"
        case "romantic": return "Affectionate private context"
        case "close": return "Familiar shared context"
        default: return "Growing shared history"
        }
    }
}

enum WorkspaceKind: String, Identifiable, CaseIterable, Hashable {
    case memories, growth, personality, presence, study, search, research
    case studio, gallery, media, voiceAvatar, devices, integrations
    case world, training, advanced

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
        case .media: return "Media"
        case .voiceAvatar: return "Voice & Avatar"
        case .devices: return "Devices"
        case .integrations: return "Integrations"
        case .world: return "World"
        case .training: return "Training"
        case .advanced: return "Advanced"
        }
    }
    var subtitle: String {
        switch self {
        case .memories: return "Continuity and recall"
        case .growth: return "How Mary is developing"
        case .personality: return "Character and preferences"
        case .presence: return "What Mary is aware of now"
        case .study: return "Learning projects and review"
        case .search: return "Search approved connected devices"
        case .research: return "Persistent research threads"
        case .studio: return "Creative projects"
        case .gallery: return "Mary and project artwork"
        case .media: return "Media connections"
        case .voiceAvatar: return "Voice and presentation"
        case .devices: return "Mac and PC capabilities"
        case .integrations: return "Connected services"
        case .world: return "Current world context"
        case .training: return "Feedback and adaptation"
        case .advanced: return "Core diagnostics"
        }
    }
    var symbol: String {
        switch self {
        case .memories: return "brain.head.profile"
        case .growth: return "arrow.up.right.circle.fill"
        case .personality: return "heart.text.square.fill"
        case .presence: return "dot.radiowaves.left.and.right"
        case .study: return "book.closed.fill"
        case .search: return "magnifyingglass"
        case .research: return "doc.text.magnifyingglass"
        case .studio: return "paintbrush.fill"
        case .gallery: return "photo.on.rectangle.angled"
        case .media: return "play.rectangle.fill"
        case .voiceAvatar: return "waveform.and.mic"
        case .devices: return "desktopcomputer"
        case .integrations: return "link.circle.fill"
        case .world: return "globe.americas.fill"
        case .training: return "checkmark.seal.fill"
        case .advanced: return "gearshape.2.fill"
        }
    }
}

struct CompanionSnapshot {
    var currentProject = ""
    var currentSummary = ""
    var activeTaskCount = 0
    var connectedNodeCount = 0
    var memoryCount = 0
    var voiceReady = false
}

enum AppModal: String, Identifiable {
    case settings, voiceCall
    var id: String { rawValue }
}
