import SwiftUI

struct MaryStageView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var breath = false

    var compact = false

    private var energy: Double {
        min(1, max(0, app.presentationEnergy))
    }

    private var stageAccent: Color {
        switch app.presentationExpression {
        case "happy", "excited", "loving", "affectionate", "warmth":
            return MaryTheme.pink2
        case "surprised", "curious":
            return MaryTheme.cyan
        case "angry", "frustrated", "firm":
            return MaryTheme.orange
        case "sad", "concerned", "soft":
            return MaryTheme.violet
        default:
            return MaryTheme.pink
        }
    }

    private var gazeOffset: CGFloat {
        switch app.presentationGaze {
        case "glance_away": return -7
        case "soft": return -2
        case "direct": return 2
        default: return 0
        }
    }

    private var headTilt: Double {
        switch app.presentationHeadStyle {
        case "tilt": return 0.9
        case "flustered": return -0.75
        case "amused": return 0.55
        case "thoughtful": return -0.25
        case "still": return 0
        default: return 0.15
        }
    }

    private var phaseLift: CGFloat {
        switch app.phase {
        case .speaking: return -3
        case .listening: return -1
        case .thinking: return 1
        default: return 0
        }
    }

    private var directedPerformance: Bool {
        !app.lastPerformancePacket.isEmpty
    }

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            MaryArtwork(asset: .portrait, contentMode: .fill)
                .frame(maxWidth: .infinity)
                .frame(height: compact ? 230 : 320)
                .scaleEffect(
                    reduceMotion
                        ? 1
                        : CGFloat(breath ? 1.012 + energy * 0.008 : 1.0)
                )
                .rotationEffect(
                    .degrees(
                        reduceMotion
                            ? 0
                            : headTilt + (breath ? 0.16 : -0.12)
                    )
                )
                .offset(
                    x: reduceMotion ? 0 : gazeOffset + (breath ? 1.2 : -1.2),
                    y: reduceMotion ? 0 : phaseLift + (breath ? -1.8 : 1.2)
                )
                .clipped()
                .overlay(
                    RadialGradient(
                        colors: [
                            stageAccent.opacity(
                                directedPerformance
                                    ? 0.10 + energy * 0.10
                                    : 0.04
                            ),
                            .clear,
                        ],
                        center: .topTrailing,
                        startRadius: 20,
                        endRadius: compact ? 190 : 260
                    )
                )
                .overlay(
                    LinearGradient(
                        colors: [.clear, MaryTheme.bg.opacity(0.08), MaryTheme.bg.opacity(0.86)],
                        startPoint: .center,
                        endPoint: .bottom
                    )
                )

            if directedPerformance {
                VStack {
                    HStack {
                        Spacer()
                        HStack(spacing: 6) {
                            Circle()
                                .fill(stageAccent)
                                .frame(width: 6, height: 6)
                            Text(app.presentationExpression.replacingOccurrences(of: "_", with: " ").uppercased())
                            if app.presentationGaze != "engaged" {
                                Text("·")
                                Text(app.presentationGaze.replacingOccurrences(of: "_", with: " ").uppercased())
                            }
                        }
                        .font(.system(size: 9, weight: .black, design: .rounded))
                        .tracking(1.1)
                        .foregroundStyle(.white.opacity(0.90))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(MaryTheme.bg.opacity(0.56), in: Capsule())
                        .overlay(Capsule().stroke(stageAccent.opacity(0.30)))
                    }
                    Spacer()
                }
                .padding(12)
            }

            HStack(spacing: 8) {
                Image(systemName: app.phase.symbol)
                Text(app.phase.label).font(.caption.weight(.bold))
                if app.phase != .offline {
                    Text("•")
                    Text(app.performanceMode.title)
                }
                if directedPerformance {
                    Text("•")
                    Text("Presence linked")
                        .foregroundStyle(stageAccent)
                }
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(.ultraThinMaterial, in: Capsule())
            .padding(14)
        }
        .background(MaryTheme.panel)
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .stroke(
                    directedPerformance
                        ? stageAccent.opacity(0.34)
                        : MaryTheme.pink.opacity(0.22)
                )
        )
        .shadow(
            color: directedPerformance
                ? stageAccent.opacity(0.11 + energy * 0.08)
                : MaryTheme.pink.opacity(0.08),
            radius: directedPerformance ? 28 : 24,
            y: 8
        )
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(
                .easeInOut(duration: 2.8)
                    .repeatForever(autoreverses: true)
            ) {
                breath = true
            }
        }
    }
}
