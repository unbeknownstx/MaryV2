import Foundation

enum AppConfiguration {
    private static let d = UserDefaults.standard

    static var coreURL: String {
        get { d.string(forKey: "mary.core.url") ?? "" }
        set { d.set(newValue, forKey: "mary.core.url") }
    }

    static var conversationID: String {
        get { d.string(forKey: "mary.conversation.id") ?? "creator-primary" }
        set { d.set(newValue, forKey: "mary.conversation.id") }
    }

    static var deviceID: String {
        if let existing = d.string(forKey: "mary.device.id"), !existing.isEmpty { return existing }
        let value = "ios-\(UUID().uuidString.lowercased())"
        d.set(value, forKey: "mary.device.id")
        return value
    }

    static var token: String {
        get { KeychainStore.read(account: "mary.core.token") }
        set { KeychainStore.save(newValue, account: "mary.core.token") }
    }

    static var speakResponses: Bool {
        get { d.object(forKey: "mary.speak.responses") as? Bool ?? true }
        set { d.set(newValue, forKey: "mary.speak.responses") }
    }
}
