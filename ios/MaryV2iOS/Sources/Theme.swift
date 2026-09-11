import SwiftUI

enum MaryTheme {
    static let bg = Color(red: 0.014, green: 0.016, blue: 0.052)
    static let bg2 = Color(red: 0.026, green: 0.026, blue: 0.095)
    static let panel = Color(red: 0.055, green: 0.050, blue: 0.140)
    static let pink = Color(red: 1.00, green: 0.31, blue: 0.65)
    static let pink2 = Color(red: 1.00, green: 0.62, blue: 0.80)
    static let violet = Color(red: 0.55, green: 0.41, blue: 1.00)
    static let cyan = Color(red: 0.29, green: 0.87, blue: 1.00)
    static let green = Color(red: 0.29, green: 0.91, blue: 0.65)
    static let orange = Color(red: 1.00, green: 0.70, blue: 0.36)
    static let muted = Color(red: 0.66, green: 0.62, blue: 0.70)
    static let line = Color(red: 1.00, green: 0.30, blue: 0.64).opacity(0.22)

    static let accent = LinearGradient(
        colors: [pink, violet, cyan],
        startPoint: .leading,
        endPoint: .trailing
    )
}

struct MaryPanel<Content: View>: View {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }

    var body: some View {
        content
            .padding(14)
            .background(
                LinearGradient(
                    colors: [MaryTheme.panel.opacity(0.96), MaryTheme.bg.opacity(0.98)],
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

struct TinyCaps: View {
    let text: String
    var body: some View {
        Text(text)
            .font(.system(size: 9, weight: .black))
            .tracking(1.6)
            .foregroundStyle(MaryTheme.pink2)
    }
}
