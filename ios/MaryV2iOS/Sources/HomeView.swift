import SwiftUI

struct HomeView: View {
    @EnvironmentObject var app: AppState
    let navigate: (WorkspaceKind) -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                ZStack(alignment: .bottomLeading) {
                    MaryArtwork(asset: .streamRoom, contentMode: .fill)
                        .frame(maxWidth: .infinity)
                        .frame(height: 250)
                        .clipped()

                    LinearGradient(
                        colors: [.clear, MaryTheme.bg.opacity(0.95)],
                        startPoint: .top,
                        endPoint: .bottom
                    )

                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Eyebrow(text: "Mary / live presence")
                            Spacer()
                            StatusPill(text: app.phase.label, online: app.isConnected)
                        }
                        Text("Mary")
                            .font(.system(size: 36, weight: .bold, design: .rounded))
                        Text(app.isConnected
                             ? "Connected to your canonical Mary Core"
                             : "Waiting for Mary Core")
                            .font(.subheadline)
                            .foregroundStyle(MaryTheme.muted)
                    }
                    .padding(18)
                }
                .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 28).stroke(MaryTheme.hairline))

                HStack(spacing: 10) {
                    Button { app.selectedTab = .chat } label: {
                        Label("Chat", systemImage: "bubble.left.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(MaryPrimaryButtonStyle())

                    Button { app.modalRoute = .voiceCall } label: {
                        Label("Voice", systemImage: "phone.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(MarySecondaryButtonStyle())
                }

                if !app.snapshot.currentProject.isEmpty {
                    GlassCard {
                        VStack(alignment: .leading, spacing: 9) {
                            Eyebrow(text: "Continue")
                            Text(app.snapshot.currentProject)
                                .font(.title2.bold())
                            if !app.snapshot.currentSummary.isEmpty {
                                Text(app.snapshot.currentSummary)
                                    .foregroundStyle(MaryTheme.muted)
                            }
                            HStack {
                                Button("Open Work") { app.selectedTab = .work }
                                Spacer()
                                Button("Talk to Mary") { app.selectedTab = .chat }
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }

                HStack(spacing: 10) {
                    MetricChip(
                        symbol: "brain.head.profile",
                        value: app.snapshot.memoryCount == 0 ? "—" : "\(app.snapshot.memoryCount)",
                        label: "Memories"
                    )
                    MetricChip(
                        symbol: "desktopcomputer",
                        value: "\(app.snapshot.connectedNodeCount)",
                        label: "Devices"
                    )
                    MetricChip(
                        symbol: "waveform",
                        value: app.snapshot.voiceReady ? "Ready" : "Text",
                        label: "Voice"
                    )
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Eyebrow(text: "Presence")
                            Spacer()
                            Text(app.performanceMode.title)
                                .font(.caption.bold())
                                .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink : MaryTheme.cyan)
                        }

                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(PerformanceMode.allCases) { mode in
                                    Button {
                                        Task { await app.changePerformanceMode(mode) }
                                    } label: {
                                        Label(mode.title, systemImage: mode.symbol)
                                            .font(.caption.weight(.semibold))
                                            .padding(.horizontal, 12)
                                            .padding(.vertical, 9)
                                            .background(
                                                app.performanceMode == mode
                                                ? MaryTheme.violet.opacity(0.45)
                                                : MaryTheme.panel2,
                                                in: Capsule()
                                            )
                                    }
                                    .buttonStyle(.plain)
                                    .foregroundStyle(.white)
                                }
                            }
                        }

                        Text(app.performanceMode.userDescription)
                            .font(.caption)
                            .foregroundStyle(MaryTheme.muted)
                    }
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 10) {
                        Eyebrow(text: "Quick spaces")
                        HStack {
                            quickSpace(.memories)
                            quickSpace(.study)
                            quickSpace(.studio)
                            quickSpace(.devices)
                        }
                    }
                }
            }
            .padding(16)
            .padding(.bottom, 8)
        }
        .refreshable { await app.refreshHome() }
    }

    private func quickSpace(_ kind: WorkspaceKind) -> some View {
        Button { navigate(kind) } label: {
            VStack(spacing: 7) {
                Image(systemName: kind.symbol)
                    .font(.title3)
                    .foregroundStyle(MaryTheme.cyan)
                Text(kind.title)
                    .font(.caption2.bold())
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
    }
}
