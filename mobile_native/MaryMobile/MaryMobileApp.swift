import SwiftUI

@main
struct MaryMobileApp: App {
    var body: some Scene {
        WindowGroup {
            MaryWebContainer()
                .ignoresSafeArea()
        }
    }
}

struct MaryWebContainer: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> MaryViewController {
        MaryViewController()
    }

    func updateUIViewController(_ uiViewController: MaryViewController, context: Context) {}
}
