import SwiftUI

struct WorkspaceDetailView: View {
    @EnvironmentObject var app: AppState
    let kind: WorkspaceKind
    @State private var studyTitle = ""
    @State private var researchTitle = ""
    @State private var searchText = ""
    @State private var searchResult: [String: Any] = [:]
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionLabel(text: "Canonical Core")
                Text(kind.title).font(.largeTitle.bold())
                Text(kind.subtitle).font(.title3).foregroundStyle(MaryTheme.muted)
                specializedContent
                if kind != .gallery && kind != .voiceAvatar {
                    HumanSummaryCard(title: "What Mary knows here", data: app.data(for: kind))
                }
            }.padding(16)
        }
        .navigationTitle(kind.title).navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { Task { await app.refresh(kind) } } label: { Image(systemName: "arrow.clockwise") } } }
        .task { await app.refresh(kind) }
        .maryScreen()
    }

    @ViewBuilder private var specializedContent: some View {
        switch kind {
        case .gallery: GalleryView()
        case .voiceAvatar: VoiceAvatarView()
        case .search:
            GlassCard {
                VStack(spacing: 10) {
                    TextField("Search your connected files", text: $searchText).textFieldStyle(.roundedBorder)
                    Button { Task { searchResult = await app.searchPersonalFiles(searchText) } } label: { Label("Search Mac / PC", systemImage: "magnifyingglass").frame(maxWidth: .infinity) }.buttonStyle(PrimaryButtonStyle()).disabled(searchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    if !searchResult.isEmpty { Text("Search sent to the best authorized device. Results will return through Mary Core.").font(.caption).foregroundStyle(MaryTheme.cyan) }
                }
            }
        case .study:
            ActionEntryCard(title: "New study project", placeholder: "What are you learning?", text: $studyTitle, button: "Create") { Task { if await app.runWorkspace("study.create_project", args: ["title": studyTitle]) { studyTitle = "" } } }
        case .research:
            ActionEntryCard(title: "New research thread", placeholder: "What do you want to investigate?", text: $researchTitle, button: "Create") { Task { if await app.runWorkspace("research.create_thread", args: ["title": researchTitle]) { researchTitle = "" } } }
        case .nodes:
            GlassCard { VStack(alignment: .leading, spacing: 8) { SectionLabel(text: "Capability Fabric"); Text("Mac and PC stay replaceable capability hosts. Mary Core remains the single authority for identity, memory, and continuity.").foregroundStyle(MaryTheme.muted); HStack { MetricTile(title: "Connected", value: "\(app.connectedNodeCount)", symbol: "server.rack"); MetricTile(title: "Authority", value: "CORE", symbol: "lock.shield.fill") } } }
        case .runtime:
            GlassCard { VStack(alignment: .leading, spacing: 10) { SectionLabel(text: "Core Health"); StatusLine(label: "Connection", value: app.isConnected ? "Online" : "Offline", positive: app.isConnected); StatusLine(label: "Core", value: "\(app.coreLabel) \(app.coreVersion)", positive: true); StatusLine(label: "Surface", value: "iPhone", positive: true); StatusLine(label: "Voice", value: app.voiceAvailable ? app.voiceProvider : "Text only", positive: app.voiceAvailable) } }
        default: EmptyView()
        }
    }
}

struct GalleryView: View {
    private let cols = [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)]
    var body: some View {
        LazyVGrid(columns: cols, spacing: 14) {
            ForEach(ArtworkStore.items) { item in
                VStack(alignment: .leading, spacing: 7) {
                    MaryArtworkView(baseName: item.baseName, ext: item.ext, contentMode: .fill).frame(height: 220).clipped().clipShape(RoundedRectangle(cornerRadius: 20))
                    Text(item.title).font(.headline)
                }
            }
        }
    }
}

struct VoiceAvatarView: View {
    @EnvironmentObject var app: AppState
    var body: some View {
        VStack(spacing: 14) {
            GlassCard {
                VStack(alignment: .leading, spacing: 10) {
                    HStack { SectionLabel(text: "Mary Voice"); Spacer(); Text(app.voiceProvider.uppercased()).font(.caption.bold()).foregroundStyle(MaryTheme.cyan) }
                    StatusLine(label: "Playback", value: app.voiceAvailable ? "Mary Core → iPhone" : "Text only", positive: app.voiceAvailable)
                    StatusLine(label: "Microphone", value: "On-device transcription", positive: true)
                    Text("Provider credentials stay on Mary Core. Raw microphone audio stays on this iPhone; only the transcript is sent to Core.").font(.subheadline).foregroundStyle(MaryTheme.muted)
                    Button("Test Mary voice") { Task { await app.speak("Hey. I'm right here on your iPhone.") } }.buttonStyle(PrimaryButtonStyle()).disabled(!app.voiceAvailable)
                }
            }
            MaryStageView(height: 360)
            Text("The stage is renderer-isolated so a future 2.5D or native 3D Mary can replace the static renderer without touching Core, chat, memory, or voice.").font(.subheadline).foregroundStyle(MaryTheme.muted)
        }
    }
}

struct HumanSummaryCard: View {
    let title: String
    let data: [String: Any]
    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                SectionLabel(text: title)
                if data.isEmpty { Text("No current information yet.").foregroundStyle(MaryTheme.muted) }
                else { ForEach(summaryRows(data).prefix(8), id: \.0) { row in StatusLine(label: row.0, value: row.1, positive: true) } }
            }
        }
    }

    private func summaryRows(_ dict: [String: Any]) -> [(String, String)] {
        dict.keys.sorted().compactMap { key in
            guard !["policy", "semantics", "authority", "version", "updated_at"].contains(key.lowercased()) else { return nil }
            return (friendly(key), friendlyValue(dict[key]))
        }
    }
    private func friendly(_ key: String) -> String { key.replacingOccurrences(of: "_", with: " ").split(separator: " ").map { $0.capitalized }.joined(separator: " ") }
    private func friendlyValue(_ value: Any?) -> String {
        guard let value else { return "—" }
        if let s = value as? String { return s.isEmpty ? "—" : s }
        if let n = value as? NSNumber { return n.boolValue == true && (n == 0 || n == 1) ? (n.boolValue ? "Yes" : "No") : n.stringValue }
        if let a = value as? [Any] { return a.isEmpty ? "None" : "\(a.count) items" }
        if let d = value as? [String: Any] {
            if let count = d["count"] as? NSNumber { return count.stringValue }
            let meaningful = d.filter { !["policy", "semantics", "authority"].contains($0.key.lowercased()) }
            return meaningful.isEmpty ? "Available" : "\(meaningful.count) details"
        }
        return String(describing: value)
    }
}

struct StatusLine: View {
    let label: String, value: String, positive: Bool
    var body: some View { HStack(alignment: .firstTextBaseline) { Text(label).foregroundStyle(MaryTheme.muted); Spacer(); Text(value).font(.body.weight(.semibold)).multilineTextAlignment(.trailing).foregroundStyle(positive ? .white : MaryTheme.muted) } }
}

struct ActionEntryCard: View {
    let title: String, placeholder: String
    @Binding var text: String
    let button: String
    let action: () -> Void
    var body: some View { GlassCard { VStack(alignment: .leading, spacing: 10) { SectionLabel(text: title); TextField(placeholder, text: $text).textFieldStyle(.roundedBorder); Button(button, action: action).buttonStyle(PrimaryButtonStyle()).disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) } } }
}
