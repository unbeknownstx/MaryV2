import SwiftUI

struct HomeView: View {
    @EnvironmentObject var app: AppState
    let navigate: (WorkspaceKind) -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                hero
                primaryActions

                if !app.snapshot.currentProject.isEmpty {
                    continueCard
                }

                relationshipCard
                lifeStrip
                capabilityStrip
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .refreshable { await app.refreshHome() }
    }

    private var hero: some View {
        ZStack(alignment: .bottomLeading) {
            MaryArtwork(asset: .streamRoom, contentMode: .fill)
                .frame(maxWidth: .infinity)
                .frame(height: 330)
                .clipped()

            LinearGradient(
                colors: [.clear, MaryTheme.bg.opacity(0.18), MaryTheme.bg.opacity(0.98)],
                startPoint: .top,
                endPoint: .bottom
            )

            LinearGradient(
                colors: [MaryTheme.pink.opacity(0.12), .clear, MaryTheme.cyan.opacity(0.08)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    RelationshipBadge(snapshot: app.relationship)
                    Spacer()
                    StatusPill(text: app.phase.label, online: app.isConnected)
                }

                Spacer()

                Text(greeting)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(MaryTheme.pink2)
                Text("Mary")
                    .font(.system(size: 42, weight: .bold, design: .rounded))
                Text(homeSubtitle)
                    .font(.subheadline)
                    .foregroundStyle(MaryTheme.muted)
                    .lineLimit(2)
            }
            .padding(18)
        }
        .frame(height: 330)
        .clipShape(RoundedRectangle(cornerRadius: 32, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 32, style: .continuous)
                .stroke(MaryTheme.pink.opacity(0.18))
        )
        .shadow(color: .black.opacity(0.28), radius: 24, y: 12)
    }

    private var primaryActions: some View {
        HStack(spacing: 10) {
            Button {
                app.openChat()
            } label: {
                Label("Talk to Mary", systemImage: "bubble.left.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(MaryPrimaryButtonStyle())

            Button {
                app.modalRoute = .voiceCall
            } label: {
                Label("Call", systemImage: "phone.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(MarySecondaryButtonStyle())
        }
    }

    private var continueCard: some View {
        GlassCard {
            HStack(alignment: .top, spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(MaryTheme.cyan.opacity(0.09))
                        .frame(width: 52, height: 52)
                    Image(systemName: "arrow.forward.circle.fill")
                        .font(.title2)
                        .foregroundStyle(MaryTheme.cyan)
                }

                VStack(alignment: .leading, spacing: 5) {
                    Eyebrow(text: "Continue")
                    Text(app.snapshot.currentProject)
                        .font(.headline)
                    if !app.snapshot.currentSummary.isEmpty {
                        Text(app.snapshot.currentSummary)
                            .font(.caption)
                            .foregroundStyle(MaryTheme.muted)
                            .lineLimit(2)
                    }
                }

                Spacer(minLength: 4)

                Button {
                    app.selectedTab = .work
                } label: {
                    Image(systemName: "chevron.right")
                        .frame(width: MaryTheme.minimumTouchTarget, height: MaryTheme.minimumTouchTarget)
                }
                .buttonStyle(.plain)
                .foregroundStyle(MaryTheme.muted)
            }
        }
    }

    private var relationshipCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Eyebrow(text: "Us")
                        Text(app.relationship.title)
                            .font(.title3.bold())
                    }
                    Spacer()
                    Image(systemName: app.relationship.symbol)
                        .font(.title2)
                        .foregroundStyle(MaryTheme.pink2)
                }

                Text(app.relationship.subtitle)
                    .font(.subheadline)
                    .foregroundStyle(MaryTheme.muted)

                Button {
                    app.selectedTab = .together
                } label: {
                    HStack {
                        Text("Open Together")
                        Spacer()
                        Image(systemName: "arrow.right")
                    }
                    .font(.subheadline.bold())
                    .foregroundStyle(MaryTheme.pink2)
                    .frame(minHeight: MaryTheme.minimumTouchTarget)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var lifeStrip: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Pick up life together")
                .font(.title3.bold())

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    lifeButton(.unwind)
                    lifeButton(.watch)
                    lifeButton(.create)
                    lifeButton(.music)
                    lifeButton(.date)
                }
            }
        }
    }

    private var capabilityStrip: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Eyebrow(text: "Mary at a glance")
                    Spacer()
                    Text(app.performanceMode.title)
                        .font(.caption.bold())
                        .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.cyan : MaryTheme.pink2)
                }

                HStack(spacing: 9) {
                    MetricChip(
                        symbol: "brain.head.profile",
                        value: app.snapshot.memoryCount == 0 ? "—" : "\(app.snapshot.memoryCount)",
                        label: "Memory"
                    )
                    MetricChip(
                        symbol: "desktopcomputer",
                        value: "\(app.snapshot.connectedNodeCount)",
                        label: "Nodes"
                    )
                    MetricChip(
                        symbol: "waveform",
                        value: app.snapshot.voiceReady ? "Live" : "Text",
                        label: "Voice"
                    )
                }

                HStack(spacing: 8) {
                    quickSpace(.memories)
                    quickSpace(.studio)
                    quickSpace(.devices)
                }
            }
        }
    }

    private func lifeButton(_ activity: SharedLifeActivity) -> some View {
        Button {
            app.prepareSharedActivity(activity)
        } label: {
            HStack(spacing: 8) {
                Image(systemName: activity.symbol)
                    .foregroundStyle(activity == .date ? MaryTheme.pink2 : MaryTheme.cyan)
                Text(activity.title)
                    .font(.subheadline.bold())
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 14)
            .frame(minHeight: MaryTheme.minimumTouchTarget)
            .background(MaryTheme.panel2, in: Capsule())
            .overlay(Capsule().stroke(MaryTheme.hairline))
        }
        .buttonStyle(.plain)
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
            .frame(minHeight: 72)
            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        if hour < 12 { return "Good morning, Unbe" }
        if hour < 18 { return "Good afternoon, Unbe" }
        return "Good evening, Unbe"
    }

    private var homeSubtitle: String {
        if !app.isConnected { return "Reconnect to Mary Core to continue your shared context." }
        if !app.relationship.activeActivityTitle.isEmpty { return "Still with you · \(app.relationship.activeActivityTitle)" }
        switch app.phase {
        case .listening: return "Listening to you"
        case .thinking: return "Thinking about what you said"
        case .speaking: return "Talking with you"
        case .idle: return "Here with you · \(app.relationship.subtitle)"
        case .offline: return "Waiting for Mary Core"
        }
    }
}
