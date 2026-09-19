import SwiftUI

struct WorkspaceDetailView: View {
    @EnvironmentObject var app: AppState
    let kind: WorkspaceKind

    @State private var studyName = ""
    @State private var researchTitle = ""
    @State private var searchQuery = ""
    @State private var modelTrialPrompt = "Give a concise character-consistent response to this held-out trial prompt."
    @State private var modelTrialStatus = ""
    @State private var modelTrialOutput = ""
    @State private var modelTrialProvider = ""
    @State private var modelTrialModel = ""
    @State private var modelTrialRunning = false
    @State private var skillRevisionID = ""
    @State private var skillRevisionReason = ""
    @State private var skillRevisionSteps = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    Image(systemName: kind.symbol).font(.title).foregroundStyle(MaryTheme.pink)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(kind.title).font(.largeTitle.bold())
                        Text(kind.subtitle).foregroundStyle(MaryTheme.muted)
                    }
                }
                actionPanel
                content
            }
            .padding(16).padding(.bottom, 20)
        }
        .background(MaryBackground())
        .navigationTitle(kind.title)
        .navigationBarTitleDisplayMode(.inline)
        .task { await app.loadWorkspace(kind) }
        .refreshable { await app.loadWorkspace(kind) }
    }

    @ViewBuilder private var actionPanel: some View {
        switch kind {
        case .study:
            GlassCard { VStack(spacing: 10) {
                TextField("New study project", text: $studyName).padding(12).background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                Button("Create Study Project") { Task { if await app.runWorkspaceAction("study.create_project", args: ["title": studyName, "objective": ""]) { studyName = ""; await app.loadWorkspace(kind) } } }
                    .buttonStyle(MaryPrimaryButtonStyle()).disabled(studyName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }}
        case .research:
            GlassCard { VStack(spacing: 10) {
                TextField("New research thread", text: $researchTitle).padding(12).background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                Button("Create Research Thread") { Task { if await app.runWorkspaceAction("research.create_thread", args: ["title": researchTitle, "question": researchTitle]) { researchTitle = ""; await app.loadWorkspace(kind) } } }
                    .buttonStyle(MaryPrimaryButtonStyle()).disabled(researchTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }}
        case .search:
            GlassCard { VStack(spacing: 10) {
                TextField("Search approved files on your connected device…", text: $searchQuery).padding(12).background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                Button { Task { await app.personalSearch(searchQuery) } } label: { Label("Search connected files", systemImage: "magnifyingglass").frame(maxWidth: .infinity) }
                    .buttonStyle(MaryPrimaryButtonStyle()).disabled(searchQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }}
        case .voiceAvatar:
            GlassCard { VStack(alignment: .leading, spacing: 10) {
                Eyebrow(text: "Voice & presentation")
                DataRow(label: "Mary voice", value: app.voiceServerAvailable ? app.voiceProvider : "Unavailable")
                DataRow(label: "Microphone", value: "On-device transcription")
                Text("Provider credentials stay on Mary Core. The iPhone keeps microphone capture local and sends only the resulting transcript.").font(.caption).foregroundStyle(MaryTheme.muted)
                Button("Open voice call") { app.modalRoute = .voiceCall }.buttonStyle(MaryPrimaryButtonStyle())
            }}
        case .gallery:
            VStack(spacing: 12) {
                CreatorLabView()
                MaryArtwork(asset: .manga, contentMode: .fit).frame(maxWidth: .infinity).clipShape(RoundedRectangle(cornerRadius: 24)).overlay(RoundedRectangle(cornerRadius: 24).stroke(MaryTheme.hairline))
                MaryArtwork(asset: .reference, contentMode: .fit).frame(maxWidth: .infinity).clipShape(RoundedRectangle(cornerRadius: 24)).overlay(RoundedRectangle(cornerRadius: 24).stroke(MaryTheme.hairline))
            }
        default: EmptyView()
        }
    }

    @ViewBuilder private var content: some View {
        switch kind {
        case .memories: memoryCard
        case .devices: deviceCards
        case .integrations: integrationCards
        case .search: searchCards
        case .presence: statusCard(eyebrow: "Presence", title: app.performanceMode.title, body: app.performanceMode.userDescription)
        case .growth: statusCard(eyebrow: "Growth", title: "Developing continuity", body: "Mary's growth, journal, and feedback signals remain owned by canonical Core.")
        case .personality: statusCard(eyebrow: "Character", title: "Mary remains one identity", body: "This surface reads the same character and relationship state used by Mac, PC, and web clients.")
        case .study: summaryList(rootKeys: ["study", "projects"], empty: "No study projects yet.")
        case .research: summaryList(rootKeys: ["research", "threads"], empty: "No research threads yet.")
        case .studio: statusCard(eyebrow: "Studio", title: "Creative workspace", body: "Creative projects remain synchronized through Mary's shared workspace and connected capability nodes.")
        case .social: SocialStudioView()
        case .media: statusCard(eyebrow: "Media", title: "Connected media", body: "YouTube, OBS, Twitch, and other media capabilities appear here only when Core reports them as available.")
        case .voiceAvatar: MaryStageView(compact: true)
        case .world: worldCard
        case .knowledge: knowledgeCard
        case .procedures: proceduresCard
        case .modelLab: modelLabCard
        case .training: statusCard(eyebrow: "Feedback", title: "Training signals", body: "Explicit feedback can improve future behavior without exposing internal training mechanics on the main app surface.")
        case .advanced: advancedCard
        case .gallery: EmptyView()
        }
    }

    private var worldCard: some View {
        let context = CoreProjection.dict(app.liveData["context"])
        let pulse = CoreProjection.dict(app.liveData["pulse"])
        let beliefs = CoreProjection.dict(app.liveData["beliefs"])
        let epistemic = CoreProjection.dict(beliefs["epistemic"])
        let temporal = CoreProjection.dict(app.liveData["temporal"])
        let contradictions = CoreProjection.array(app.liveData["contradictions"])
        let reconciliationGroups = CoreProjection.array(
            app.liveData["reconciliation_queue"]
        ).map { CoreProjection.dict($0) }
        let recent = CoreProjection.array(context["recent"])
        let due = CoreProjection.array(pulse["due"])

        return VStack(spacing: 12) {
            GlassCard { VStack(alignment: .leading, spacing: 9) {
                Eyebrow(text: "World pulse")
                Text("\(CoreProjection.int(context["count"])) current context items")
                    .font(.title2.bold())
                DataRow(label: "Refresh lanes due", value: "\(due.count)")
                DataRow(label: "Current beliefs", value: "\(CoreProjection.int(beliefs["current_beliefs"]))")
                DataRow(label: "Contested beliefs", value: "\(CoreProjection.int(epistemic["contested"]))")
                DataRow(label: "Temporal relations", value: "\(CoreProjection.int(temporal["relations"]))")
                DataRow(label: "Contradictions", value: "\(contradictions.count)")
                DataRow(label: "Reconciliation groups", value: "\(reconciliationGroups.count)")
                Text("World Pulse only plans refreshes. External context expires and cannot promote itself into Mary truth; acceptance and reconciliation remain explicit Core actions.")
                    .font(.caption)
                    .foregroundStyle(MaryTheme.muted)
            }}

            if !reconciliationGroups.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 12) {
                    Eyebrow(text: "World reconciliation")
                    Text("Claims are grouped by subject and predicate. Selecting one retires competing current claims as history without deleting their evidence.")
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)

                    ForEach(Array(reconciliationGroups.prefix(10).enumerated()), id: \.offset) { _, group in
                        let candidates = CoreProjection.array(group["candidates"]).map {
                            CoreProjection.dict($0)
                        }
                        VStack(alignment: .leading, spacing: 8) {
                            Text(
                                CoreProjection.string(group["subject"])
                                + " · "
                                + CoreProjection.string(group["predicate"])
                            )
                            .font(.subheadline.bold())
                            Text("\(CoreProjection.int(group["candidate_count"])) competing current claim(s)")
                                .font(.caption)
                                .foregroundStyle(MaryTheme.muted)

                            ForEach(Array(candidates.prefix(8).enumerated()), id: \.offset) { _, row in
                                let beliefID = CoreProjection.string(row["belief_id"])
                                let rawValue = row["value"]
                                let value = CoreProjection.string(rawValue).isEmpty
                                    ? String(describing: rawValue ?? "—")
                                    : CoreProjection.string(rawValue)
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(value).font(.subheadline)
                                    Text(
                                        (CoreProjection.string(row["source"]).isEmpty
                                            ? "unknown source"
                                            : CoreProjection.string(row["source"]))
                                        + " · "
                                        + CoreProjection.string(row["verification"])
                                    )
                                    .font(.caption)
                                    .foregroundStyle(MaryTheme.muted)
                                    Button("Keep this as current") {
                                        Task {
                                            _ = await app.reconcileWorldBelief(beliefID)
                                        }
                                    }
                                    .buttonStyle(MarySecondaryButtonStyle())
                                    .disabled(beliefID.isEmpty)
                                }
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }}
            } else if !contradictions.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 12) {
                    Eyebrow(text: "World reconciliation")
                    Text("Legacy contradiction view; explicit reconciliation remains required.")
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                    ForEach(Array(contradictions.prefix(12).enumerated()), id: \.offset) { _, item in
                        let row = CoreProjection.dict(item)
                        let beliefID = CoreProjection.string(row["id"])
                        VStack(alignment: .leading, spacing: 7) {
                            Text(
                                CoreProjection.string(row["subject"])
                                + " · "
                                + CoreProjection.string(row["predicate"])
                            )
                            .font(.subheadline.bold())
                            Button("Keep this as current") {
                                Task { _ = await app.reconcileWorldBelief(beliefID) }
                            }
                            .buttonStyle(MarySecondaryButtonStyle())
                            .disabled(beliefID.isEmpty)
                        }
                    }
                }}
            }

            if !due.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 8) {
                    Eyebrow(text: "Needs refresh")
                    ForEach(Array(due.prefix(8).enumerated()), id: \.offset) { _, item in
                        let row = CoreProjection.dict(item)
                        HStack {
                            Image(systemName: "clock.arrow.circlepath")
                                .foregroundStyle(MaryTheme.cyan)
                            Text(CoreProjection.string(row["lane"]).replacingOccurrences(of: "_", with: " ").capitalized)
                            Spacer()
                        }
                        .font(.subheadline)
                    }
                }}
            }

            if !contradictions.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 10) {
                    Eyebrow(text: "World reconciliation")
                    Text("Choosing one claim retires competing claims as history; it does not erase the evidence.")
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                    ForEach(Array(contradictions.prefix(8).enumerated()), id: \.offset) { _, item in
                        let row = CoreProjection.dict(item)
                        VStack(alignment: .leading, spacing: 6) {
                            Text("\(CoreProjection.string(row["subject"])) · \(CoreProjection.string(row["predicate"]))")
                                .font(.subheadline.bold())
                            Text(CoreProjection.string(row["value"]))
                                .font(.caption)
                            Button("Keep this as current") {
                                Task {
                                    _ = await app.reconcileWorldBelief(
                                        CoreProjection.string(row["id"])
                                    )
                                }
                            }
                            .buttonStyle(MarySecondaryButtonStyle())
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }}
            }

            if !recent.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 8) {
                    Eyebrow(text: "Current external context")
                    ForEach(Array(recent.suffix(6).enumerated()), id: \.offset) { _, item in
                        let row = CoreProjection.dict(item)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(CoreProjection.string(row["topic"]).isEmpty ? "World context" : CoreProjection.string(row["topic"]))
                                .font(.subheadline.bold())
                            Text(CoreProjection.string(row["source"]).isEmpty ? "Source-attributed evidence" : CoreProjection.string(row["source"]))
                                .font(.caption)
                                .foregroundStyle(MaryTheme.muted)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }}
            }
        }
    }

    private var knowledgeCard: some View {
        GlassCard { VStack(alignment: .leading, spacing: 9) {
            Eyebrow(text: "Local knowledge")
            Text("\(CoreProjection.int(app.liveData["enabled"])) of \(CoreProjection.int(app.liveData["packs"])) packs enabled").font(.title2.bold())
            DataRow(label: "Indexed chunks", value: "\(CoreProjection.int(app.liveData["indexed_documents"]))")
            DataRow(label: "Disabled documents", value: "\(CoreProjection.int(app.liveData["disabled_documents"]))")
            Text("Local documents, Kiwix and optional vector indexes are evidence sources. They never become memory or truth just because retrieval found them.").font(.caption).foregroundStyle(MaryTheme.muted)
        }}
    }

    private var proceduresCard: some View {
        let skills = CoreProjection.dict(app.liveData["skills"])
        let plans = CoreProjection.dict(app.liveData["plans"])
        let replay = CoreProjection.dict(app.liveData["replay"])
        let competence = CoreProjection.dict(app.liveData["competence"])
        let review = CoreProjection.dict(app.liveData["review"])
        let candidates = CoreProjection.array(review["candidates"]).map {
            CoreProjection.dict($0)
        }
        let approved = CoreProjection.array(review["approved"]).map {
            CoreProjection.dict($0)
        }
        let revisionQueue = CoreProjection.array(review["revision_queue"]).map {
            CoreProjection.dict($0)
        }

        return VStack(spacing: 12) {
            GlassCard { VStack(alignment: .leading, spacing: 9) {
                Eyebrow(text: "Procedural continuity")
                Text("\(CoreProjection.int(skills["approved"])) approved skills").font(.title2.bold())
                DataRow(label: "Skill candidates", value: "\(CoreProjection.int(skills["candidates"]))")
                DataRow(label: "Active plans", value: "\(CoreProjection.int(plans["active_plans"]))")
                DataRow(label: "Replay lessons", value: "\(CoreProjection.int(replay["lessons"]))")
                DataRow(label: "Competence records", value: "\(CoreProjection.int(competence["records"]))")
                DataRow(label: "Revision attention", value: "\(revisionQueue.count)")
                Text("Replay may suggest procedures, but approval and execution permissions remain explicit.").font(.caption).foregroundStyle(MaryTheme.muted)
            }}

            if !candidates.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 10) {
                    Eyebrow(text: "Procedure review")
                    ForEach(Array(candidates.prefix(10).enumerated()), id: \.offset) { _, item in
                        let skillID = CoreProjection.string(item["id"])
                        VStack(alignment: .leading, spacing: 6) {
                            Text(CoreProjection.string(item["name"]).isEmpty ? "Procedure candidate" : CoreProjection.string(item["name"]))
                                .font(.subheadline.bold())
                            Text(CoreProjection.string(item["description"]))
                                .font(.caption)
                                .foregroundStyle(MaryTheme.muted)
                            HStack {
                                Button("Approve") {
                                    Task { _ = await app.approveSkillCandidate(skillID) }
                                }
                                .buttonStyle(MaryPrimaryButtonStyle())
                                Button("Reject") {
                                    Task { _ = await app.rejectSkillCandidate(skillID) }
                                }
                                .buttonStyle(MarySecondaryButtonStyle())
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }}
            }

            if !revisionQueue.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 8) {
                    Eyebrow(text: "Revision pressure")
                    Text("Repeated outcome evidence can flag an approved procedure for review, but it cannot rewrite that procedure.")
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                    ForEach(Array(revisionQueue.prefix(8).enumerated()), id: \.offset) { _, item in
                        DataRow(
                            label: CoreProjection.string(item["name"]),
                            value: "\(Int((CoreProjection.double(item["failure_rate"]) * 100).rounded()))% failure"
                        )
                    }
                }}
            }

            if !approved.isEmpty {
                GlassCard { VStack(alignment: .leading, spacing: 10) {
                    Eyebrow(text: "Approved procedures")
                    ForEach(Array(approved.prefix(8).enumerated()), id: \.offset) { _, item in
                        let skillID = CoreProjection.string(item["id"])
                        let steps = CoreProjection.array(item["steps"]).map {
                            CoreProjection.string($0)
                        }
                        VStack(alignment: .leading, spacing: 6) {
                            Text(CoreProjection.string(item["name"]).isEmpty ? "Approved procedure" : CoreProjection.string(item["name"]))
                                .font(.subheadline.bold())
                            Button("Propose revision") {
                                skillRevisionID = skillID
                                skillRevisionReason = ""
                                skillRevisionSteps = steps.joined(separator: "\n")
                            }
                            .buttonStyle(MarySecondaryButtonStyle())
                        }
                    }

                    if !skillRevisionID.isEmpty {
                        Divider().overlay(MaryTheme.hairline)
                        TextField("Why should this procedure change?", text: $skillRevisionReason, axis: .vertical)
                            .lineLimit(2...4)
                            .padding(12)
                            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                        TextField("One procedure step per line", text: $skillRevisionSteps, axis: .vertical)
                            .lineLimit(3...8)
                            .padding(12)
                            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                        Button("Create revision candidate") {
                            let steps = skillRevisionSteps
                                .split(whereSeparator: \.isNewline)
                                .map { String($0) }
                            Task {
                                if await app.reviseApprovedSkill(
                                    skillRevisionID,
                                    reason: skillRevisionReason,
                                    steps: steps
                                ) {
                                    skillRevisionID = ""
                                    skillRevisionReason = ""
                                    skillRevisionSteps = ""
                                }
                            }
                        }
                        .buttonStyle(MaryPrimaryButtonStyle())
                        .disabled(
                            skillRevisionReason.trimmingCharacters(
                                in: .whitespacesAndNewlines
                            ).isEmpty
                        )
                    }
                }}
            }
        }
    }

    private var modelLabCard: some View {
        let lab = CoreProjection.dict(app.liveData["adapter_lab"])
        let candidates = CoreProjection.dict(app.liveData["candidates"])
        let experiments = CoreProjection.dict(app.liveData["experiments"])
        let records = CoreProjection.array(experiments["records"]).map {
            CoreProjection.dict($0)
        }
        let ready = records.filter {
            CoreProjection.bool($0["trial_ready"])
        }
        let selected = ready.first ?? [:]
        let experimentID = CoreProjection.string(selected["id"])
        let candidateID = CoreProjection.string(
            selected["candidate_id"] ?? selected["id"]
        )
        let nodeIntelligence = CoreProjection.dict(app.liveData["node_intelligence"])
        let intelligenceNodes = CoreProjection.array(nodeIntelligence["nodes"]).map {
            CoreProjection.dict($0)
        }
        let authorizedCapabilities = intelligenceNodes.reduce(0) { total, node in
            total + CoreProjection.int(CoreProjection.dict(node["counts"])["authorized"])
        }
        let demonstratedCapabilities = intelligenceNodes.reduce(0) { total, node in
            total + CoreProjection.int(CoreProjection.dict(node["counts"])["demonstrated"])
        }

        return VStack(spacing: 12) {
            GlassCard { VStack(alignment: .leading, spacing: 9) {
                Eyebrow(text: "Model lab")
                Text("\(CoreProjection.int(candidates["count"])) reviewed candidates").font(.title2.bold())
                DataRow(label: "Trial-ready experiments", value: "\(CoreProjection.int(experiments["trial_ready"]))")
                DataRow(label: "Lineage events", value: "\(CoreProjection.int(experiments["event_count"]))")
                DataRow(label: "Authorized node capabilities", value: "\(authorizedCapabilities)")
                DataRow(label: "Demonstrated capabilities", value: "\(demonstratedCapabilities)")
                DataRow(label: "Configurations", value: "\(CoreProjection.array(lab["configurations"]).count)")
                DataRow(label: "Evaluations", value: "\(CoreProjection.array(lab["evaluations"]).count)")
                DataRow(label: "Promotion", value: "Creator-reviewed")
                Text("Models and LoRAs are replaceable capabilities. Exact lineage, held-out MaryBench and runtime evidence are required before routing changes.").font(.caption).foregroundStyle(MaryTheme.muted)
            }}

            GlassCard { VStack(alignment: .leading, spacing: 10) {
                Eyebrow(text: "Explicit model trial")
                Text(candidateID.isEmpty ? "No trial-ready experiment" : candidateID)
                    .font(.headline)
                Text("Runs only an already-reviewed, benchmarked experiment on the exact authorized local experiment node. The output never becomes Mary's production response, memory, or routing policy.")
                    .font(.caption)
                    .foregroundStyle(MaryTheme.muted)

                TextField("Held-out prompt", text: $modelTrialPrompt, axis: .vertical)
                    .lineLimit(2...5)
                    .padding(12)
                    .background(
                        MaryTheme.panel2,
                        in: RoundedRectangle(cornerRadius: 14)
                    )
                    .disabled(experimentID.isEmpty || modelTrialRunning)

                Button {
                    Task {
                        modelTrialRunning = true
                        modelTrialOutput = ""
                        modelTrialStatus = "Core is verifying exact experiment and node readiness…"

                        if let result = await app.runModelExperiment(
                            experimentID: experimentID,
                            prompt: modelTrialPrompt
                        ) {
                            modelTrialOutput = CoreProjection.string(
                                result["content"]
                            )
                            modelTrialProvider = CoreProjection.string(
                                result["provider"]
                            )
                            modelTrialModel = CoreProjection.string(
                                result["model"]
                            )
                            modelTrialStatus = "Trial completed · experimental output only."
                            UINotificationFeedbackGenerator()
                                .notificationOccurred(.success)
                        } else {
                            modelTrialStatus =
                                app.lastError ?? "The bounded trial did not complete."
                            UINotificationFeedbackGenerator()
                                .notificationOccurred(.error)
                        }

                        modelTrialRunning = false
                    }
                } label: {
                    Label(
                        modelTrialRunning
                            ? "Experiment running…"
                            : "Run bounded trial",
                        systemImage: "flask.fill"
                    )
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(MaryPrimaryButtonStyle())
                .disabled(
                    experimentID.isEmpty
                    || modelTrialRunning
                    || modelTrialPrompt.trimmingCharacters(
                        in: .whitespacesAndNewlines
                    ).isEmpty
                )

                if !modelTrialStatus.isEmpty {
                    Text(modelTrialStatus)
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                }

                if !modelTrialOutput.isEmpty {
                    Divider().overlay(MaryTheme.hairline)
                    DataRow(
                        label: "Provider",
                        value: modelTrialProvider.isEmpty
                            ? "Local experiment"
                            : modelTrialProvider
                    )
                    DataRow(
                        label: "Model",
                        value: modelTrialModel.isEmpty
                            ? CoreProjection.string(selected["model"])
                            : modelTrialModel
                    )
                    Text(modelTrialOutput)
                        .font(.body)
                    Text("LAB OUTPUT · not written to memory or production routing")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(MaryTheme.pink2)
                }
            }}
        }
    }

    private var memoryCard: some View {
        let summary = CoreProjection.readableMemorySummary(app.liveData)
        return GlassCard { VStack(alignment: .leading, spacing: 9) {
            Eyebrow(text: "Continuity")
            Text(summary.total == 0 ? "Memory" : "\(summary.total) memory records").font(.title2.bold())
            ForEach(Array(summary.lines.enumerated()), id: \.offset) { _, line in Text(line).foregroundStyle(MaryTheme.muted) }
        }}
    }

    private var deviceCards: some View { VStack(spacing: 10) {
        let cards = CoreProjection.nodeCards(app.liveData)
        if cards.isEmpty { statusCard(eyebrow: "Devices", title: "No capability node online", body: "Your Mac or PC can come online as a capability host without owning Mary's identity or memory.") }
        ForEach(Array(cards.enumerated()), id: \.offset) { _, card in GlassCard { HStack {
            Image(systemName: "desktopcomputer").font(.title2).foregroundStyle(MaryTheme.cyan)
            VStack(alignment: .leading) { Text(card["name"] ?? "Device").font(.headline); Text("\(card["platform"] ?? "") • \(card["capabilities"] ?? "0") capabilities").font(.caption).foregroundStyle(MaryTheme.muted) }
            Spacer(); StatusPill(text: card["status"] ?? "Offline", online: card["status"] == "Connected")
        }}}
    }}

    private var integrationCards: some View { VStack(spacing: 10) {
        let items = CoreProjection.integrations(app.liveData)
        if items.isEmpty { statusCard(eyebrow: "Integrations", title: "No summary yet", body: "Connected services will appear here when Mary Core reports them.") }
        ForEach(Array(items.enumerated()), id: \.offset) { _, item in GlassCard { HStack { Image(systemName: "link").foregroundStyle(MaryTheme.pink); Text(item["name"] ?? "Service").font(.headline); Spacer(); Text(item["status"] ?? "").font(.caption).foregroundStyle(MaryTheme.muted) }}}
    }}

    private var searchCards: some View { GlassCard { VStack(alignment: .leading, spacing: 9) {
        Eyebrow(text: "Results")
        if app.searchResult.isEmpty { Text("Search runs only through an explicitly allowed personal_search capability on a connected device.").foregroundStyle(MaryTheme.muted) }
        else { let task = CoreProjection.string(app.searchResult["task_id"] ?? app.searchResult["status"]); Text(task.isEmpty ? "Search dispatched." : "Search: \(task)").font(.headline); Text("Results stay bounded by the selected device's local permission policy.").font(.caption).foregroundStyle(MaryTheme.muted) }
    }}}

    private var advancedCard: some View { GlassCard { VStack(alignment: .leading, spacing: 9) {
        Eyebrow(text: "Advanced"); Text("Core diagnostics").font(.title2.bold()); Text("Raw backend state is intentionally hidden from normal app surfaces. Use repository diagnostics and CLI verification for deep inspection.").foregroundStyle(MaryTheme.muted)
        DataRow(label: "Core", value: app.coreLabel); DataRow(label: "Architecture", value: app.coreVersion.isEmpty ? "unknown" : app.coreVersion); DataRow(label: "Device", value: String(app.deviceID.prefix(20)))
    }}}

    private func statusCard(eyebrow: String, title: String, body: String) -> some View { GlassCard { VStack(alignment: .leading, spacing: 8) { Eyebrow(text: eyebrow); Text(title).font(.title2.bold()); Text(body).foregroundStyle(MaryTheme.muted) } } }

    private func summaryList(rootKeys: [String], empty: String) -> some View {
        var items: [Any] = []
        for key in rootKeys { if let candidate = app.liveData[key] as? [Any] { items = candidate; break }; if let object = app.liveData[key] as? [String: Any], let candidate = object["items"] as? [Any] { items = candidate; break } }
        return GlassCard { VStack(alignment: .leading, spacing: 10) { Eyebrow(text: kind.title); if items.isEmpty { Text(empty).foregroundStyle(MaryTheme.muted) } else { ForEach(Array(items.prefix(12).enumerated()), id: \.offset) { _, item in let row = CoreProjection.dict(item); let title = CoreProjection.string(row["title"] ?? row["name"]); HStack { Image(systemName: "circle.fill").font(.system(size: 5)).foregroundStyle(MaryTheme.cyan); Text(title.isEmpty ? "Item" : title); Spacer() } } } } }
    }
}
