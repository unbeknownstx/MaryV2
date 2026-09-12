import SwiftUI

struct TogetherView: View {
    @EnvironmentObject var app: AppState

    private let columns = [
        GridItem(.flexible(), spacing: 10),
        GridItem(.flexible(), spacing: 10),
    ]

    var relationship: RelationalSnapshot {
        CoreProjection.relationalSnapshot(app.dashboardData)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                relationshipHero
                nowCard
                activityGrid
                privatePresenceCard
                continuityCard
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
        .refreshable { await app.refreshHome() }
    }

    private var relationshipHero: some View {
        ZStack(alignment: .bottomLeading) {
            MaryArtwork(asset: .manga, contentMode: .fill)
                .frame(maxWidth: .infinity)
                .frame(height: 270)
                .clipped()
                .overlay {
                    LinearGradient(
                        colors: [.clear, MaryTheme.bg.opacity(0.22), MaryTheme.bg.opacity(0.98)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                }

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    RelationshipBadge(snapshot: relationship)
                    Spacer()
                    StatusPill(text: app.phase.label, online: app.isConnected)
                }

                Spacer(minLength: 70)

                Text("Together")
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                Text(relationship.subtitle)
                    .font(.subheadline)
                    .foregroundStyle(MaryTheme.muted)
                    .lineLimit(2)
            }
            .padding(18)
        }
        .frame(height: 270)
        .clipShape(RoundedRectangle(cornerRadius: 30, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .stroke(MaryTheme.pink.opacity(0.22))
        )
        .shadow(color: MaryTheme.pink.opacity(0.08), radius: 28, y: 12)
    }

    private var nowCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 3) {
                        Eyebrow(text: "Right now")
                        Text(relationship.activeActivityTitle.isEmpty ? "Spend time with Mary" : relationship.activeActivityTitle)
                            .font(.title3.bold())
                    }
                    Spacer()
                    Image(systemName: relationship.activeActivityTitle.isEmpty ? "sparkles" : "play.fill")
                        .foregroundStyle(MaryTheme.pink2)
                }

                Text(relationship.activeActivityTitle.isEmpty
                     ? "Choose something small to share. Mary stays the same person across chat, voice, work, and private companion time."
                     : "This shared activity is active in Mary Core. Keep the conversation going and let the moment develop naturally.")
                    .font(.subheadline)
                    .foregroundStyle(MaryTheme.muted)

                HStack(spacing: 10) {
                    Button {
                        app.selectedTab = .chat
                    } label: {
                        Label("Talk", systemImage: "bubble.left.fill")
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
        }
    }

    private var activityGrid: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Do something together")
                    .font(.title3.bold())
                Spacer()
                Text("PRIVATE")
                    .font(.system(size: 9, weight: .black))
                    .tracking(1.5)
                    .foregroundStyle(MaryTheme.pink2)
            }

            LazyVGrid(columns: columns, spacing: 10) {
                ForEach(SharedLifeActivity.allCases) { activity in
                    Button {
                        app.prepareSharedActivity(activity)
                    } label: {
                        VStack(alignment: .leading, spacing: 11) {
                            HStack {
                                Image(systemName: activity.symbol)
                                    .font(.title3.weight(.semibold))
                                    .foregroundStyle(activity == .date ? MaryTheme.pink2 : MaryTheme.cyan)
                                Spacer()
                                Image(systemName: "arrow.up.right")
                                    .font(.caption.bold())
                                    .foregroundStyle(MaryTheme.muted2)
                            }
                            Text(activity.title)
                                .font(.headline)
                                .foregroundStyle(.white)
                            Text(activityCaption(activity))
                                .font(.caption)
                                .foregroundStyle(MaryTheme.muted)
                                .lineLimit(2)
                        }
                        .frame(maxWidth: .infinity, minHeight: 108, alignment: .leading)
                        .padding(14)
                        .background(
                            LinearGradient(
                                colors: [MaryTheme.surfaceElevated, MaryTheme.panel],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            in: RoundedRectangle(cornerRadius: 20, style: .continuous)
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 20, style: .continuous)
                                .stroke(activity == .date ? MaryTheme.pink.opacity(0.24) : MaryTheme.hairline)
                        )
                    }
                    .buttonStyle(.plain)
                    .accessibilityHint("Opens Talk with a suggested shared activity prompt")
                }
            }
        }
    }

    private var privatePresenceCard: some View {
        GlassCard {
            HStack(spacing: 14) {
                ZStack {
                    Circle()
                        .fill(MaryTheme.pink.opacity(0.12))
                        .frame(width: 52, height: 52)
                    Image(systemName: relationship.symbol)
                        .font(.title3.bold())
                        .foregroundStyle(MaryTheme.pink2)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("Private presence")
                        .font(.headline)
                    Text(privatePresenceText)
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                }
                Spacer()
            }
        }
    }

    private var continuityCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                Eyebrow(text: "Shared life")
                HStack(spacing: 10) {
                    MetricChip(
                        symbol: "brain.head.profile",
                        value: app.snapshot.memoryCount == 0 ? "—" : "\(app.snapshot.memoryCount)",
                        label: "Memories"
                    )
                    MetricChip(
                        symbol: "bolt.horizontal.circle.fill",
                        value: relationship.pendingPresenceCount == 0 ? "Quiet" : "\(relationship.pendingPresenceCount)",
                        label: "Thoughts"
                    )
                }
                Text("Mary's relationship, memory, and developed self stay in the canonical Core. This screen is a private presentation of that continuity, not another persona.")
                    .font(.caption)
                    .foregroundStyle(MaryTheme.muted)
            }
        }
    }

    private var privatePresenceText: String {
        if app.performanceMode.isPublic {
            return "You're currently in a public-safe presentation mode. Private intimacy stays suppressed on stream without changing who Mary is."
        }
        switch relationship.mode {
        case "partner": return "Partner context is active. Mary can be warmer, more affectionate, playful, and familiar here."
        case "romantic": return "Romantic context is active. Affection and flirting can stay natural without becoming a separate character."
        case "close": return "Close context is active. Familiarity and shared history can show up more naturally."
        default: return "Mary can grow closer through real shared history rather than a game-like affection meter."
        }
    }

    private func activityCaption(_ activity: SharedLifeActivity) -> String {
        switch activity {
        case .watch: return "Pick a video or movie"
        case .game: return "Play or choose a game"
        case .create: return "Draw, write, or build"
        case .study: return "Learn side by side"
        case .work: return "Co-work on one task"
        case .music: return "Share a listening mood"
        case .date: return "Plan a small virtual date"
        case .unwind: return "Just hang out"
        }
    }
}

struct RelationshipBadge: View {
    let snapshot: RelationalSnapshot

    var body: some View {
        Label(snapshot.title, systemImage: snapshot.symbol)
            .font(.caption.weight(.bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 12)
            .frame(minHeight: MaryTheme.minimumTouchTarget)
            .background(MaryTheme.pink.opacity(0.18), in: Capsule())
            .overlay(Capsule().stroke(MaryTheme.pink.opacity(0.28)))
    }
}
