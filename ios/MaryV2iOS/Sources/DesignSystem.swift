import SwiftUI

enum MaryTheme {
    static let bg = Color(red: 0.025, green: 0.025, blue: 0.07)
    static let surface = Color(red: 0.055, green: 0.045, blue: 0.115)
    static let surface2 = Color(red: 0.085, green: 0.055, blue: 0.15)
    static let pink = Color(red: 1.0, green: 0.28, blue: 0.65)
    static let pinkSoft = Color(red: 1.0, green: 0.56, blue: 0.78)
    static let cyan = Color(red: 0.28, green: 0.86, blue: 1.0)
    static let violet = Color(red: 0.48, green: 0.28, blue: 1.0)
    static let green = Color(red: 0.25, green: 0.92, blue: 0.67)
    static let muted = Color.white.opacity(0.62)
    static let faint = Color.white.opacity(0.08)
    static let hairline = Color.white.opacity(0.09)
}

struct MaryBackground: View {
    var body: some View {
        ZStack {
            MaryTheme.bg
            RadialGradient(colors: [MaryTheme.violet.opacity(0.20), .clear], center: .topTrailing, startRadius: 10, endRadius: 520)
            RadialGradient(colors: [MaryTheme.pink.opacity(0.12), .clear], center: .bottomLeading, startRadius: 40, endRadius: 640)
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
            .background(.ultraThinMaterial.opacity(0.32), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .background(MaryTheme.surface.opacity(0.88), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(MaryTheme.pink.opacity(0.24), lineWidth: 1))
    }
}

struct SectionLabel: View {
    let text: String
    var body: some View {
        Text(text.uppercased())
            .font(.caption2.weight(.black))
            .tracking(2.2)
            .foregroundStyle(MaryTheme.pinkSoft)
    }
}

struct MaryWordmark: View {
    var compact = false
    var body: some View {
        VStack(spacing: compact ? -2 : 0) {
            HStack(spacing: 2) {
                Text("Mary").font(.system(size: compact ? 31 : 40, weight: .semibold, design: .serif)).italic()
                Image(systemName: "heart").font(.system(size: compact ? 15 : 18, weight: .bold)).foregroundStyle(MaryTheme.pink)
            }
            Text("M O B I L E").font(.system(size: 8, weight: .black)).tracking(4).foregroundStyle(MaryTheme.muted)
        }
    }
}

struct StatusPill: View {
    let online: Bool
    var body: some View {
        HStack(spacing: 7) {
            Circle().fill(online ? MaryTheme.green : .red).frame(width: 8, height: 8)
            Text(online ? "Online" : "Offline").font(.caption.weight(.semibold))
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(.white.opacity(0.04), in: Capsule()).overlay(Capsule().stroke(MaryTheme.hairline))
    }
}

struct MetricTile: View {
    let title: String
    let value: String
    let symbol: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: symbol).foregroundStyle(MaryTheme.cyan)
            Text(value).font(.title3.bold()).lineLimit(1).minimumScaleFactor(0.75)
            Text(title).font(.caption).foregroundStyle(MaryTheme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(MaryTheme.surface.opacity(0.9), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(MaryTheme.hairline))
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.bold)).foregroundStyle(.white)
            .padding(.horizontal, 18).frame(minHeight: 46)
            .background(LinearGradient(colors: [MaryTheme.pink, MaryTheme.violet], startPoint: .leading, endPoint: .trailing), in: Capsule())
            .opacity(configuration.isPressed ? 0.78 : 1)
    }
}

extension View {
    func maryScreen() -> some View { self.background(MaryBackground()) }
}
