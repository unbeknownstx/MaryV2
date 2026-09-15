import SwiftUI

struct MaryStageView: View {
    @EnvironmentObject var app: AppState
    var compact = false

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            MaryArtwork(asset: .portrait, contentMode: .fill)
                .frame(maxWidth: .infinity)
                .frame(height: compact ? 230 : 320)
                .clipped()
                .overlay(
                    LinearGradient(
                        colors: [.clear, MaryTheme.bg.opacity(0.08), MaryTheme.bg.opacity(0.86)],
                        startPoint: .center,
                        endPoint: .bottom
                    )
                )

            HStack(spacing: 8) {
                Image(systemName: app.phase.symbol)
                Text(app.phase.label).font(.caption.weight(.bold))
                if app.phase != .offline {
                    Text("•")
                    Text(app.performanceMode.title)
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
                .stroke(MaryTheme.pink.opacity(0.22))
        )
        .shadow(color: MaryTheme.pink.opacity(0.08), radius: 24, y: 8)
    }
}
