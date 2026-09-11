import Foundation

@MainActor
final class AppConfiguration: ObservableObject {
    private enum Keys {
        static let coreURL = "mary.coreURL"
        static let conversationID = "mary.conversationID"
        static let deviceID = "mary.deviceID"
        static let coreToken = "mary.coreToken"
    }

    @Published var coreURL: String
    @Published var conversationID: String
    let deviceID: String

    init() {
        let defaults = UserDefaults.standard
        coreURL = defaults.string(forKey: Keys.coreURL) ?? ""
        conversationID = defaults.string(forKey: Keys.conversationID) ?? "creator-primary"
        if let existing = defaults.string(forKey: Keys.deviceID), !existing.isEmpty {
            deviceID = existing
        } else {
            let generated = "ios-\(UUID().uuidString.lowercased())"
            defaults.set(generated, forKey: Keys.deviceID)
            deviceID = generated
        }
    }

    var token: String { KeychainStore.get(Keys.coreToken) ?? "" }

    var normalizedURL: URL? {
        let trimmed = coreURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed),
              url.scheme?.lowercased() == "https",
              url.host != nil
        else { return nil }
        return url
    }

    var isConfigured: Bool { normalizedURL != nil && !token.isEmpty }

    func save(coreURL: String, token: String, conversationID: String) throws {
        let cleanURL = coreURL.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanToken = token.trimmingCharacters(in: .whitespacesAndNewlines)
        let cleanConversation = conversationID.trimmingCharacters(in: .whitespacesAndNewlines)

        guard let url = URL(string: cleanURL),
              url.scheme?.lowercased() == "https",
              url.host != nil else { throw ConfigurationError.invalidCoreURL }
        guard !cleanToken.isEmpty else { throw ConfigurationError.missingToken }

        let finalConversation = cleanConversation.isEmpty ? "creator-primary" : cleanConversation
        UserDefaults.standard.set(cleanURL, forKey: Keys.coreURL)
        UserDefaults.standard.set(finalConversation, forKey: Keys.conversationID)
        try KeychainStore.set(cleanToken, for: Keys.coreToken)
        self.coreURL = cleanURL
        self.conversationID = finalConversation
    }

    enum ConfigurationError: LocalizedError {
        case invalidCoreURL, missingToken
        var errorDescription: String? {
            switch self {
            case .invalidCoreURL: return "Core URL must be a valid HTTPS address."
            case .missingToken: return "Core token is required."
            }
        }
    }
}
