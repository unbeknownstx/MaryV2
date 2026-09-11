import SwiftUI

enum MaryTheme {
    static let bg = Color(red: 0.02, green: 0.024, blue: 0.067)
    static let panel = Color(red: 0.055, green: 0.05, blue: 0.14)
    static let pink = Color(red: 1.0, green: 0.31, blue: 0.65)
    static let pink2 = Color(red: 1.0, green: 0.62, blue: 0.80)
    static let violet = Color(red: 0.55, green: 0.41, blue: 1.0)
    static let cyan = Color(red: 0.29, green: 0.87, blue: 1.0)
    static let green = Color(red: 0.29, green: 0.91, blue: 0.65)
    static let muted = Color(red: 0.66, green: 0.62, blue: 0.69)
    static let line = Color(red: 1.0, green: 0.30, blue: 0.64).opacity(0.23)

    static let accentGradient = LinearGradient(
        colors: [pink, violet, cyan],
        startPoint: .leading,
        endPoint: .trailing
    )
}

struct MaryPanel<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .padding(14)
            .background(
                LinearGradient(
                    colors: [MaryTheme.panel.opacity(0.95), MaryTheme.bg.opacity(0.96)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: RoundedRectangle(cornerRadius: 18, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(MaryTheme.line, lineWidth: 1)
            )
    }
}
