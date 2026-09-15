import SwiftUI

@main
struct MaryV2App: App {
    @StateObject private var app = AppState()
<<<<<<< HEAD
    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(app).preferredColorScheme(.dark).task { await app.start() }
=======
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
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
        }
    }
}
