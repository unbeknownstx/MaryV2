import SwiftUI

struct WorkspaceDetailView: View {
    @EnvironmentObject var app: AppState
    let kind: WorkspaceKind

    @State private var studyName = ""
    @State private var researchTitle = ""
    @State private var searchQuery = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    Image(systemName: kind.symbol)
                        .font(.title)
                        .foregroundStyle(MaryTheme.pink)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(kind.title).font(.largeTitle.bold())
                        Text(kind.subtitle).foregroundStyle(MaryTheme.muted)
                    }
                }

                actionPanel
                content
            }
            .padding(16)
            .padding(.bottom, 20)
        }
        .background(MaryBackground())
        .navigationTitle(kind.title)
        .navigationBarTitleDisplayMode(.inline)
        .task { await app.loadWorkspace(kind) }
        .refreshable { await app.loadWorkspace(kind) }
    }

    @ViewBuilder
    private var actionPanel: some View {
        switch kind {
        case .study:
            GlassCard {
                VStack(spacing: 10) {
                    TextField("New study project", text: $studyName)
                        .padding(12)
                        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                    Button("Create Study Project") {
                        Task {
                            if await app.runWorkspaceAction(
                                "study.create_project",
                                args: ["title": studyName, "objective": ""]
                            ) {
                                studyName = ""
                                await app.loadWorkspace(kind)
                            }
                        }
                    }
                    .buttonStyle(MaryPrimaryButtonStyle())
                    .disabled(studyName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }

        case .research:
            GlassCard {
                VStack(spacing: 10) {
                    TextField("New research thread", text: $researchTitle)
                        .padding(12)
                        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                    Button("Create Research Thread") {
                        Task {
                            if await app.runWorkspaceAction(
                                "research.create_thread",
                                args: ["title": researchTitle, "question": researchTitle]
                            ) {
                                researchTitle = ""
                                await app.loadWorkspace(kind)
                            }
                        }
                    }
                    .buttonStyle(MaryPrimaryButtonStyle())
                    .disabled(researchTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }

        case .search:
            GlassCard {
                VStack(spacing: 10) {
                    TextField("Search approved files on your connected device…", text: $searchQuery)
                        .padding(12)
                        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                    Button {
                        Task { await app.personalSearch(searchQuery) }
                    } label: {
                        Label("Search connected files", systemImage: "magnifyingglass")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(MaryPrimaryButtonStyle())
                    .disabled(searchQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }

        case .voiceAvatar:
            GlassCard {
                VStack(alignment: .leading, spacing: 10) {
                    Eyebrow(text: "Voice & presentation")
                    DataRow(label: "Mary voice", value: app.voiceServerAvailable ? app.voiceProvider : "Unavailable")
                    DataRow(label: "Microphone", value: "On-device transcription")
                    Text("Provider credentials stay on Mary Core. The iPhone keeps microphone capture local and sends only the resulting transcript.")
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                    Button("Open voice call") { app.modalRoute = .voiceCall }
                        .buttonStyle(MaryPrimaryButtonStyle())
                }
            }

        case .gallery:
            VStack(spacing: 12) {
                MaryArtwork(asset: .manga, contentMode: .fit)
                    .frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 24))
                    .overlay(RoundedRectangle(cornerRadius: 24).stroke(MaryTheme.hairline))
                MaryArtwork(asset: .reference, contentMode: .fit)
                    .frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 24))
                    .overlay(RoundedRectangle(cornerRadius: 24).stroke(MaryTheme.hairline))
            }

        default:
            EmptyView()
        }
    }

    @ViewBuilder
    private var content: some View {
        switch kind {
        case .memories:
            memoryCard
        case .devices:
            deviceCards
        case .integrations:
            integrationCards
        case .search:
            searchCards
        case .presence:
            statusCard(
                eyebrow: "Presence",
                title: app.performanceMode.title,
                body: app.performanceMode.userDescription
            )
        case .growth:
            statusCard(
                eyebrow: "Growth",
                title: "Developing continuity",
                body: "Mary's growth, journal, and feedback signals remain owned by canonical Core."
            )
        case .personality:
            statusCard(
                eyebrow: "Character",
                title: "Mary remains one identity",
                body: "This surface reads the same character and relationship state used by Mac, PC, and web clients."
            )
        case .study:
            summaryList(rootKeys: ["study", "projects"], empty: "No study projects yet.")
        case .research:
            summaryList(rootKeys: ["research", "threads"], empty: "No research threads yet.")
        case .studio:
            statusCard(
                eyebrow: "Studio",
                title: "Creative workspace",
                body: "Creative projects remain synchronized through Mary's shared workspace and connected capability nodes."
            )
        case .media:
            statusCard(
                eyebrow: "Media",
                title: "Connected media",
                body: "YouTube, OBS, Twitch, and other media capabilities appear here only when Core reports them as available."
            )
        case .voiceAvatar:
            MaryStageView(compact: true)
        case .world:
            statusCard(
                eyebrow: "World",
                title: "Current context",
                body: CoreProjection.string(app.liveData["summary"]).isEmpty
                    ? "No bounded world-context summary is available yet."
                    : CoreProjection.string(app.liveData["summary"])
            )
        case .training:
            statusCard(
                eyebrow: "Feedback",
                title: "Training signals",
                body: "Explicit feedback can improve future behavior without exposing internal training mechanics on the main app surface."
            )
        case .advanced:
            advancedCard
        case .gallery, .search, .devices, .integrations:
            EmptyView()
        }
    }

    private var memoryCard: some View {
        let summary = CoreProjection.readableMemorySummary(app.liveData)
        return GlassCard {
            VStack(alignment: .leading, spacing: 9) {
                Eyebrow(text: "Continuity")
                Text(summary.total == 0 ? "Memory" : "\(summary.total) memory records")
                    .font(.title2.bold())
                ForEach(Array(summary.lines.enumerated()), id: \\.offset) { _, line in
                    Text(line).foregroundStyle(MaryTheme.muted)
                }
            }
        }
    }

    private var deviceCards: some View {
        VStack(spacing: 10) {
            let cards = CoreProjection.nodeCards(app.liveData)
            if cards.isEmpty {
                statusCard(
                    eyebrow: "Devices",
                    title: "No capability node online",
                    body: "Your Mac or PC can come online as a capability host without owning Mary's identity or memory."
                )
            }
            ForEach(Array(cards.enumerated()), id: \\.offset) { _, card in
                GlassCard {
                    HStack {
                        Image(systemName: "desktopcomputer")
                            .font(.title2)
                            .foregroundStyle(MaryTheme.cyan)
                        VStack(alignment: .leading) {
                            Text(card["name"] ?? "Device").font(.headline)
                            Text("\(card["platform"] ?? "") • \(card["capabilities"] ?? "0") capabilities")
                                .font(.caption)
                                .foregroundStyle(MaryTheme.muted)
                        }
                        Spacer()
                        StatusPill(
                            text: card["status"] ?? "Offline",
                            online: card["status"] == "Connected"
                        )
                    }
                }
            }
        }
    }

    private var integrationCards: some View {
        VStack(spacing: 10) {
            let items = CoreProjection.integrations(app.liveData)
            if items.isEmpty {
                statusCard(
                    eyebrow: "Integrations",
                    title: "No summary yet",
                    body: "Connected services will appear here when Mary Core reports them."
                )
            }
            ForEach(Array(items.enumerated()), id: \\.offset) { _, item in
                GlassCard {
                    HStack {
                        Image(systemName: "link").foregroundStyle(MaryTheme.pink)
                        Text(item["name"] ?? "Service").font(.headline)
                        Spacer()
                        Text(item["status"] ?? "")
                            .font(.caption)
                            .foregroundStyle(MaryTheme.muted)
                    }
                }
            }
        }
    }

    private var searchCards: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 9) {
                Eyebrow(text: "Results")
                if app.searchResult.isEmpty {
                    Text("Search runs only through an explicitly allowed personal_search capability on a connected device.")
                        .foregroundStyle(MaryTheme.muted)
                } else {
                    let task = CoreProjection.string(app.searchResult["task_id"] ?? app.searchResult["status"])
                    Text(task.isEmpty ? "Search dispatched." : "Search: \(task)")
                        .font(.headline)
                    Text("Results stay bounded by the selected device's local permission policy.")
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                }
            }
        }
    }

    private var advancedCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 9) {
                Eyebrow(text: "Advanced")
                Text("Core diagnostics").font(.title2.bold())
                Text("Raw backend state is intentionally hidden from normal app surfaces. Use repository diagnostics and CLI verification for deep inspection.")
                    .foregroundStyle(MaryTheme.muted)
                DataRow(label: "Core", value: app.coreLabel)
                DataRow(label: "Architecture", value: app.coreVersion.isEmpty ? "unknown" : app.coreVersion)
                DataRow(label: "Device", value: String(app.deviceID.prefix(20)))
            }
        }
    }

    private func statusCard(eyebrow: String, title: String, body: String) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 8) {
                Eyebrow(text: eyebrow)
                Text(title).font(.title2.bold())
                Text(body).foregroundStyle(MaryTheme.muted)
            }
        }
    }

    private func summaryList(rootKeys: [String], empty: String) -> some View {
        var items: [Any] = []
        for key in rootKeys {
            if let candidate = app.liveData[key] as? [Any] { items = candidate; break }
            if let object = app.liveData[key] as? [String: Any],
               let candidate = object["items"] as? [Any] { items = candidate; break }
        }

        return GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Eyebrow(text: kind.title)
                if items.isEmpty {
                    Text(empty).foregroundStyle(MaryTheme.muted)
                } else {
                    ForEach(Array(items.prefix(12).enumerated()), id: \\.offset) { _, item in
                        let row = CoreProjection.dict(item)
                        let title = CoreProjection.string(row["title"] ?? row["name"])
                        HStack {
                            Image(systemName: "circle.fill")
                                .font(.system(size: 5))
                                .foregroundStyle(MaryTheme.cyan)
                            Text(title.isEmpty ? "Item" : title)
                            Spacer()
                        }
                    }
                }
            }
        }
    }
}
