import SwiftUI

struct MoreView: View {
    @EnvironmentObject var app: AppState

    private let groups: [(String, [(WorkspaceKind, String, String)])] = [
        ("COMPANION", [
            (.memories, "Continuity + recall", "rectangle.stack.fill"),
            (.growth, "Experience + development", "arrow.up.right.circle.fill"),
            (.personality, "Mary's developed self", "sparkles"),
            (.mind, "Model + cognitive state", "brain.head.profile"),
            (.presence, "Current live context", "dot.radiowaves.left.and.right")
        ]),
        ("WORK", [
            (.study, "Projects + review", "book.closed.fill"),
            (.search, "Knowledge + configured roots", "magnifyingglass"),
            (.research, "Persistent research threads", "doc.text.magnifyingglass"),
            (.arcade, "Small local games", "gamecontroller.fill")
        ]),
        ("CREATE / MEDIA", [
            (.studio, "Creative workspace", "pencil.and.outline"),
            (.gallery, "Mary + project art", "photo.on.rectangle.angled"),
            (.media, "Media + integrations", "play.rectangle.fill"),
            (.voiceAvatar, "Speech + presentation", "waveform.and.mic")
        ]),
        ("SYSTEM", [
            (.runtime, "Core dashboard", "gauge.with.dots.needle.67percent"),
            (.nodes, "Connected capability nodes", "server.rack"),
            (.stream, "Streaming state", "dot.radiowaves.left.and.right"),
            (.world, "World context", "globe.americas.fill"),
            (.integrations, "Connected systems", "link.circle.fill"),
            (.training, "Feedback + training state", "checkmark.seal.fill")
        ])
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                TinyCaps(text: "MARY SYSTEM")
                Text("Workspaces").font(.largeTitle.bold())

                MaryPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("SOCIAL STAGE")
                                .font(.caption2.weight(.black))
                                .tracking(1.4)
                                .foregroundStyle(MaryTheme.pink2)
                            Spacer()
                            Text(app.performanceMode.title.uppercased())
                                .font(.caption2.bold())
                                .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                        }

                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 7) {
                                ForEach(PerformanceMode.allCases) { mode in
                                    Button {
                                        Task { await app.changePerformanceMode(mode) }
                                    } label: {
                                        Label(mode.title, systemImage: mode.symbol)
                                            .font(.caption.weight(.semibold))
                                            .padding(.horizontal, 10)
                                            .padding(.vertical, 7)
                                            .foregroundStyle(app.performanceMode == mode ? .white : MaryTheme.muted)
                                            .background(
                                                app.performanceMode == mode
                                                ? MaryTheme.violet.opacity(0.34)
                                                : Color.white.opacity(0.035),
                                                in: Capsule()
                                            )
                                            .overlay(Capsule().stroke(.white.opacity(0.06)))
                                    }
                                }
                            }
                        }
                    }
                }

                ForEach(groups, id: \.0) { group in
                    VStack(alignment: .leading, spacing: 7) {
                        Text(group.0)
                            .font(.system(size: 9, weight: .black))
                            .tracking(1.4)
                            .foregroundStyle(MaryTheme.muted)
                            .padding(.leading, 3)

                        ForEach(group.1, id: \.0.id) { item in
                            Button {
                                Task { await app.loadWorkspace(item.0) }
                            } label: {
                                HStack(spacing: 12) {
                                    Image(systemName: item.2)
                                        .font(.title3)
                                        .foregroundStyle(MaryTheme.pink2)
                                        .frame(width: 30)

                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.0.title).font(.body.weight(.semibold))
                                        Text(item.1).font(.caption).foregroundStyle(MaryTheme.muted)
                                    }

                                    Spacer()
                                    Image(systemName: "chevron.right")
                                        .foregroundStyle(MaryTheme.muted.opacity(0.6))
                                }
                                .padding(12)
                                .background(.white.opacity(0.025), in: RoundedRectangle(cornerRadius: 14))
                                .overlay(RoundedRectangle(cornerRadius: 14).stroke(.white.opacity(0.06)))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }

                Button {
                    app.showSettings = true
                } label: {
                    Label("Settings", systemImage: "gearshape.fill")
                        .frame(maxWidth: .infinity)
                        .frame(height: 46)
                }
                .buttonStyle(.bordered)
            }
            .padding(13)
        }
    }
}

struct WorkspaceDetailView: View {
    @EnvironmentObject var app: AppState
    let kind: WorkspaceKind
    @State private var studyName = ""
    @State private var researchTitle = ""
    @State private var arcadeGuess = "5"

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    TinyCaps(text: "CANONICAL CORE")
                    Text(kind.title).font(.largeTitle.bold())

                    actionPanel

                    MaryPanel {
                        VStack(alignment: .leading, spacing: 9) {
                            Text("LIVE CORE DATA")
                                .font(.caption2.weight(.black))
                                .tracking(1.4)
                                .foregroundStyle(MaryTheme.cyan)

                            if app.liveData.isEmpty {
                                Text("No data returned yet.")
                                    .foregroundStyle(MaryTheme.muted)
                            } else {
                                JSONSummaryView(value: app.liveData)
                            }
                        }
                    }

                    Button {
                        Task { await app.loadWorkspace(kind) }
                    } label: {
                        Label("Refresh", systemImage: "arrow.clockwise")
                            .frame(maxWidth: .infinity)
                            .frame(height: 44)
                    }
                    .buttonStyle(.bordered)
                }
                .padding(13)
            }
            .background(MaryTheme.bg.ignoresSafeArea())
            .navigationTitle(kind.title)
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    @ViewBuilder
    private var actionPanel: some View {
        switch kind {
        case .study:
            MaryPanel {
                VStack(spacing: 10) {
                    TextField("New study project", text: $studyName)
                        .textFieldStyle(.roundedBorder)
                    Button("Create Study Project") {
                        Task {
                            if await app.runWorkspaceAction("study.create_project", args: ["title": studyName]) {
                                studyName = ""
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(MaryTheme.violet)
                    .disabled(studyName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }

        case .research:
            MaryPanel {
                VStack(spacing: 10) {
                    TextField("New research thread", text: $researchTitle)
                        .textFieldStyle(.roundedBorder)
                    Button("Create Research Thread") {
                        Task {
                            if await app.runWorkspaceAction("research.create_thread", args: ["title": researchTitle]) {
                                researchTitle = ""
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(MaryTheme.violet)
                    .disabled(researchTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }

        case .arcade:
            MaryPanel {
                VStack(spacing: 10) {
                    HStack {
                        Button("Flip Coin") {
                            Task { _ = await app.runWorkspaceAction("arcade.play", args: ["game": "coin", "payload": ""]) }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(MaryTheme.violet)

                        Spacer()

                        TextField("1-10", text: $arcadeGuess)
                            .keyboardType(.numberPad)
                            .frame(width: 70)
                            .textFieldStyle(.roundedBorder)

                        Button("Guess") {
                            Task { _ = await app.runWorkspaceAction("arcade.play", args: ["game": "number", "payload": arcadeGuess]) }
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }

        case .stream:
            MaryPanel {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Stream mode controls Mary's public privacy guard.")
                        .foregroundStyle(MaryTheme.muted)
                    Button("Switch to Stream") {
                        Task { await app.changePerformanceMode(.stream) }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(MaryTheme.pink)
                    Button("Return to Private") {
                        Task { await app.changePerformanceMode(.private) }
                    }
                    .buttonStyle(.bordered)
                }
            }

        case .voiceAvatar:
            VStack(spacing: 12) {
                MaryPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            TinyCaps(text: "MARY VOICE")
                            Spacer()
                            Text(app.voiceServerAvailable ? app.voiceProvider.uppercased() : "CORE VOICE OFFLINE")
                                .font(.caption2.bold())
                                .foregroundStyle(app.voiceServerAvailable ? MaryTheme.cyan : MaryTheme.orange)
                        }
                        DataRow(label: "Playback", value: app.voiceServerAvailable ? "Mary Core → iPhone" : "Text only")
                        DataRow(label: "Microphone", value: "On-device transcription")
                        Text("Provider credentials remain on Mary Core. Raw microphone audio stays on this iPhone and only the transcript is sent to Core.")
                            .font(.caption)
                            .foregroundStyle(MaryTheme.muted)
                        HStack {
                            Button("Refresh") { Task { await app.refreshVoiceStatus() } }
                                .buttonStyle(.bordered)
                            Button("Test Mary voice") {
                                Task { await app.speakMaryResponse("Hey, I’m here. This is my Core voice playing on your iPhone.") }
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(MaryTheme.violet)
                            .disabled(!app.voiceServerAvailable)
                        }
                    }
                }

                MaryPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            TinyCaps(text: "AVATAR / STAGE FALLBACK")
                            Spacer()
                            Text("LOCAL ART")
                                .font(.caption2.bold())
                                .foregroundStyle(MaryTheme.pink2)
                        }
                        MaryStageArtwork(height: 260)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                        Text("The native iPhone surface uses Mary's generated local artwork until a live VRM renderer is added. Desktop keeps the VRM when available and falls back to the same art set if loading fails.")
                            .font(.caption)
                            .foregroundStyle(MaryTheme.muted)
                    }
                }
            }

        default:
            EmptyView()
        }
    }
}

struct JSONSummaryView: View {
    let value: [String: Any]

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            ForEach(Array(value.keys.sorted().prefix(24)), id: \.self) { key in
                HStack(alignment: .top, spacing: 8) {
                    Text(key.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                        .frame(width: 108, alignment: .leading)

                    Text(summary(value[key]))
                        .font(.caption.monospaced())
                        .foregroundStyle(.white)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.vertical, 2)
            }
        }
    }

    private func summary(_ any: Any?) -> String {
        guard let any else { return "—" }
        if let s = any as? String { return s }
        if let n = any as? NSNumber { return n.stringValue }
        if let d = any as? [String: Any] {
            let pairs = d.keys.sorted().prefix(6).map { "\($0)=\(short(d[$0]))" }
            return "{ " + pairs.joined(separator: ", ") + (d.count > 6 ? ", …" : "") + " }"
        }
        if let a = any as? [Any] {
            return "[\(a.count) items]"
        }
        return String(describing: any)
    }

    private func short(_ any: Any?) -> String {
        guard let any else { return "nil" }
        if let s = any as? String { return String(s.prefix(34)) }
        if let n = any as? NSNumber { return n.stringValue }
        if let d = any as? [String: Any] { return "{\(d.count)}" }
        if let a = any as? [Any] { return "[\(a.count)]" }
        return String(describing: any)
    }
}
