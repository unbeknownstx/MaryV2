import Foundation

enum AppConfiguration {
    private static let defaults = UserDefaults.standard

    static var coreURL: String {
        get { defaults.string(forKey: "mary.core.url") ?? "" }
        set { defaults.set(newValue, forKey: "mary.core.url") }
    }

    static var conversationID: String {
        get { defaults.string(forKey: "mary.conversation.id") ?? "creator-primary" }
        set { defaults.set(newValue, forKey: "mary.conversation.id") }
    }

    static var deviceID: String {
        if let v = defaults.string(forKey: "mary.device.id"), !v.isEmpty { return v }
        let v = "ios-\(UUID().uuidString.lowercased())"
        defaults.set(v, forKey: "mary.device.id")
        return v
    }

    static var token: String {
        get { KeychainStore.read(account: "mary.core.token") }
        set { KeychainStore.save(newValue, account: "mary.core.token") }
    }
}
