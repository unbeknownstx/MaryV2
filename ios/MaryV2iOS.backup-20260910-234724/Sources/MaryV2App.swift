import SwiftUI

@main
struct MaryV2App: App {
    @StateObject private var appState = AppState()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .preferredColorScheme(.dark)
                .task { await appState.start() }
                .onChange(of: scenePhase) { phase in
                    Task { await appState.handleScenePhase(phase) }
                }
        }
    }
}
