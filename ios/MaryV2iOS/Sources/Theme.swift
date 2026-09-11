import SwiftUI

extension Color {
    init(hex: UInt, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xff) / 255,
            green: Double((hex >> 8) & 0xff) / 255,
            blue: Double(hex & 0xff) / 255,
            opacity: alpha
        )
    }
}

enum MaryTheme {
    static let bg = Color(hex: 0x080715)
    static let bg2 = Color(hex: 0x0D0B24)
    static let panel = Color(hex: 0x111025)
    static let panel2 = Color(hex: 0x17132E)
    static let text = Color.white
    static let muted = Color(hex: 0xABA5BD)
    static let pink = Color(hex: 0xFF72B9)
    static let pink2 = Color(hex: 0xFF9DD1)
    static let violet = Color(hex: 0x8F5CFF)
    static let cyan = Color(hex: 0x57D8FF)
    static let green = Color(hex: 0x55E7B0)
    static let orange = Color(hex: 0xFFB55E)
    static let hairline = Color.white.opacity(0.08)
    static let line = hairline
    static let gradient = LinearGradient(colors: [pink, violet, cyan], startPoint: .leading, endPoint: .trailing)
    static let accent = gradient
}

struct MaryBackground: View {
    var body: some View {
        ZStack {
            MaryTheme.bg
            RadialGradient(
                colors: [MaryTheme.violet.opacity(0.15), .clear],
                center: .topTrailing,
                startRadius: 10,
                endRadius: 430
            )
            RadialGradient(
                colors: [MaryTheme.pink.opacity(0.09), .clear],
                center: .bottomLeading,
                startRadius: 30,
                endRadius: 360
            )
        }
        .ignoresSafeArea()
    }
}

struct GlassCard<Content: View>: View {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View {
        content
            .padding(16)
            .background(MaryTheme.panel.opacity(0.94), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(MaryTheme.hairline))
    }
}

struct MaryPanel<Content: View>: View {
    let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    var body: some View { GlassCard { content } }
}

struct Eyebrow: View {
    let text: String
    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 11, weight: .black, design: .rounded))
            .tracking(2)
            .foregroundStyle(MaryTheme.pink)
    }
}

struct TinyCaps: View {
    let text: String
    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 9, weight: .black))
            .tracking(1.6)
            .foregroundStyle(MaryTheme.pink2)
    }
}

struct StatusPill: View {
    let text: String
    let online: Bool
    var body: some View {
        HStack(spacing: 7) {
            Circle().fill(online ? MaryTheme.green : MaryTheme.orange).frame(width: 8, height: 8)
            Text(text).font(.caption.weight(.semibold))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial, in: Capsule())
        .overlay(Capsule().stroke(MaryTheme.hairline))
    }
}

struct MetricChip: View {
    let symbol: String
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Image(systemName: symbol).foregroundStyle(MaryTheme.cyan)
            Text(value).font(.title3.bold())
            Text(label).font(.caption).foregroundStyle(MaryTheme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 18))
    }
}

struct DataRow: View {
    let label: String
    let value: String
    var body: some View {
        HStack(alignment: .top) {
            Text(label).font(.caption).foregroundStyle(MaryTheme.muted)
            Spacer()
            Text(value).font(.caption.weight(.semibold)).multilineTextAlignment(.trailing)
        }
        .padding(.vertical, 3)
    }
}

struct MaryPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.bold())
            .foregroundStyle(.white)
            .padding(.vertical, 13)
            .padding(.horizontal, 16)
            .background(MaryTheme.gradient.opacity(configuration.isPressed ? 0.7 : 1), in: RoundedRectangle(cornerRadius: 16))
    }
}

struct MarySecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.bold())
            .foregroundStyle(.white)
            .padding(.vertical, 13)
            .padding(.horizontal, 16)
            .background(MaryTheme.panel2.opacity(configuration.isPressed ? 0.7 : 1), in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(MaryTheme.hairline))
    }
}
