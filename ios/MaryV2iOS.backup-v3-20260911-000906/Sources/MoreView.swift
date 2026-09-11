import SwiftUI

struct MoreView: View {
    @EnvironmentObject var app: AppState

    private let groups: [(String, [(String, String, String)])] = [
        ("COMPANION", [
            ("Memories", "Continuity + recall", "rectangle.stack.fill"),
            ("Growth", "Experience + development", "arrow.up.right.circle.fill"),
            ("Personality", "Mary's developed self", "sparkles"),
            ("Mind", "Cognitive reservoir", "brain.head.profile"),
            ("Presence", "Current context", "dot.radiowaves.left.and.right")
        ]),
        ("WORK", [
            ("Study", "Projects + review", "book.closed.fill"),
            ("Search", "Configured roots", "magnifyingglass"),
            ("Research", "Persistent threads", "doc.text.magnifyingglass"),
            ("Arcade", "Small local games", "gamecontroller.fill")
        ]),
        ("CREATE / MEDIA", [
            ("Studio", "Unbeknownst + creative files", "pencil.and.outline"),
            ("Gallery", "Mary + project art", "photo.on.rectangle.angled"),
            ("Media", "YouTube + research", "play.rectangle.fill"),
            ("Voice & Avatar", "Speech + presentation", "waveform.and.mic")
        ]),
        ("SYSTEM", [
            ("Runtime", "Routing + latency", "gauge.with.dots.needle.67percent"),
            ("Settings", "Connection + device", "gearshape.fill")
        ])
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 15) {
                Text("MARY SYSTEM")
                    .font(.caption2.weight(.black))
                    .tracking(1.8)
                    .foregroundStyle(MaryTheme.pink2)

                Text("Workspaces").font(.largeTitle.bold())

                SocialStageCompact()

                ForEach(groups, id: \.0) { group in
                    VStack(alignment: .leading, spacing: 7) {
                        Text(group.0)
                            .font(.caption2.weight(.black))
                            .tracking(1.5)
                            .foregroundStyle(MaryTheme.muted)
                            .padding(.leading, 3)

                        ForEach(group.1, id: \.0) { item in
                            Button {
                                if item.0 == "Settings" {
                                    app.showWorkspace = false
                                    app.showSettings = true
                                } else {
                                    app.lastError = "\(item.0) is queued for the native workspace migration pass."
                                }
                            } label: {
                                HStack(spacing: 12) {
                                    Image(systemName: item.2)
                                        .font(.title3)
                                        .foregroundStyle(MaryTheme.pink2)
                                        .frame(width: 30)

                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.0).font(.body.weight(.semibold))
                                        Text(item.1).font(.caption).foregroundStyle(MaryTheme.muted)
                                    }

                                    Spacer()
                                    Image(systemName: "chevron.right").foregroundStyle(MaryTheme.muted.opacity(0.6))
                                }
                                .padding(12)
                                .background(.white.opacity(0.025), in: RoundedRectangle(cornerRadius: 14))
                                .overlay(RoundedRectangle(cornerRadius: 14).stroke(.white.opacity(0.06)))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .padding(13)
        }
    }
}

struct SocialStageCompact: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        MaryPanel {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("SOCIAL STAGE")
                        .font(.caption2.weight(.black))
                        .tracking(1.6)
                        .foregroundStyle(MaryTheme.pink2)
                    Spacer()
                    Text(app.performanceMode.title.uppercased())
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                }

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 7) {
                        ForEach(PerformanceMode.allCases) { mode in
                            Button {
                                Task { await app.changePerformanceMode(mode) }
                            } label: {
                                Text(mode.title)
                                    .font(.caption.weight(.semibold))
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .foregroundStyle(app.performanceMode == mode ? .white : MaryTheme.muted)
                                    .background(
                                        app.performanceMode == mode
                                        ? MaryTheme.violet.opacity(0.35)
                                        : Color.white.opacity(0.035)
                                    )
                                    .clipShape(Capsule())
                                    .overlay(Capsule().stroke(.white.opacity(0.07)))
                            }
                        }
                    }
                }

                Text(app.performanceMode.isPublic ? "Public privacy guard is active." : "Private creator context may be used when relevant.")
                    .font(.caption)
                    .foregroundStyle(MaryTheme.muted)
            }
        }
    }
}
