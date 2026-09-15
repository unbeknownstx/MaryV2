import SwiftUI

struct HomeView: View {
    @EnvironmentObject var app: AppState
    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                GlassCard {
                    HStack(spacing: 14) {
                        MaryArtworkView(baseName: "mary-reference", ext: "jpeg", contentMode: .fill)
                            .frame(width: 82, height: 112).clipped().clipShape(RoundedRectangle(cornerRadius: 18))
                        VStack(alignment: .leading, spacing: 5) {
                            SectionLabel(text: "Mary // Live Presence")
                            Text("Mary").font(.largeTitle.bold())
                            Text(app.isConnected ? "Canonical continuity online" : "Waiting for Mary Core").foregroundStyle(MaryTheme.muted)
                            HStack(spacing: 6) { Circle().fill(app.isConnected ? MaryTheme.green : .red).frame(width: 8, height: 8); Text("\(app.coreLabel) · \(app.coreVersion)").font(.caption).foregroundStyle(MaryTheme.muted) }
                        }
                        Spacer()
                    }
                }

                currentWork

                HStack(spacing: 12) {
                    MetricTile(title: "Connected nodes", value: "\(app.connectedNodeCount)", symbol: "server.rack")
                    MetricTile(title: "Mary voice", value: app.voiceAvailable ? "READY" : "TEXT", symbol: "waveform")
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack { SectionLabel(text: "Social Stage"); Spacer(); Text(app.performanceMode.title.uppercased()).font(.caption.bold()).foregroundStyle(MaryTheme.cyan) }
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(PerformanceMode.allCases) { mode in
                                    Button { Task { await app.setPerformanceMode(mode) } } label: {
                                        Label(mode.title, systemImage: mode.symbol).font(.caption.weight(.semibold)).padding(.horizontal, 12).padding(.vertical, 9)
                                            .foregroundStyle(app.performanceMode == mode ? .white : MaryTheme.muted)
                                            .background(app.performanceMode == mode ? MaryTheme.violet.opacity(0.6) : .white.opacity(0.04), in: Capsule())
                                    }.buttonStyle(.plain)
                                }
                            }
                        }
                        Text(app.performanceMode == .private ? "Private creator context" : "Presentation context is isolated from Mary's canonical identity.")
                            .font(.subheadline).foregroundStyle(MaryTheme.cyan)
                    }
                }
            }
            .padding(16)
        }
        .refreshable { await app.refreshAll() }
    }

    @ViewBuilder private var currentWork: some View {
        if let work = app.workspaceSnapshot["current_work"] as? [String: Any], (work["active"] as? Bool) == true {
            GlassCard {
                VStack(alignment: .leading, spacing: 10) {
                    HStack { SectionLabel(text: "Current Work"); Spacer(); Text(String(describing: work["stage"] ?? "Current").uppercased()).font(.caption.bold()).foregroundStyle(MaryTheme.cyan) }
                    Text(String(describing: work["project"] ?? "Shared work")).font(.title2.bold())
                    Text(String(describing: work["summary"] ?? "")).font(.body).foregroundStyle(MaryTheme.muted)
                    HStack {
                        Button { app.selectedTab = .command } label: { Label("Open Command", systemImage: "checkmark.square.fill") }.buttonStyle(.bordered)
                        Button { app.selectedTab = .chat } label: { Label("Talk to Mary", systemImage: "bubble.left.fill") }.buttonStyle(PrimaryButtonStyle())
                    }
                }
            }
        } else {
            GlassCard {
                VStack(alignment: .leading, spacing: 8) { SectionLabel(text: "Current Work"); Text("Nothing active right now").font(.title3.bold()); Text("Start from Command or talk to Mary about what you want to work on.").foregroundStyle(MaryTheme.muted) }
            }
        }
    }
}
