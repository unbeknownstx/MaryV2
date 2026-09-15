import SwiftUI

@main
struct MaryV2App: App {
    @StateObject private var app = AppState()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(app)
                .preferredColorScheme(.dark)
                .task { await app.start() }
                .onChange(of: scenePhase) { phase in
                    Task {
                        switch phase {
                        case .active:
                            await app.setSurfaceActive(true)
                        case .inactive, .background:
                            await app.setSurfaceActive(false)
                        @unknown default:
                            break
                        }
                    }
                }
        }
    }
}
