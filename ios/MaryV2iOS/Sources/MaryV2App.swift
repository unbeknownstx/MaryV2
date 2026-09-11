import SwiftUI

@main
struct MaryV2App: App {
    @StateObject private var app = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(app)
                .preferredColorScheme(.dark)
                .task { await app.start() }
        }
    }
}
