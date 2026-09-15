import SwiftUI

struct MoreView: View {
    @EnvironmentObject var app: AppState
    private let groups: [(String, [WorkspaceKind])] = [
        ("Companion", [.memories, .growth, .personality, .presence]),
        ("Work", [.study, .search, .research]),
        ("Create", [.studio, .gallery, .voiceAvatar]),
        ("System", [.nodes, .runtime, .integrations, .training, .world, .stream])
    ]
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    SectionLabel(text: "Mary System")
                    Text("More").font(.largeTitle.bold())
                    Text("Everything important, organized around what it means—not how the backend stores it.").foregroundStyle(MaryTheme.muted)
                    ForEach(groups, id: \.0) { group in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(group.0.uppercased()).font(.caption2.bold()).tracking(1.7).foregroundStyle(MaryTheme.muted)
                            ForEach(group.1) { kind in
                                NavigationLink(value: kind) {
                                    HStack(spacing: 12) {
                                        Image(systemName: kind.symbol).frame(width: 28).foregroundStyle(MaryTheme.pinkSoft)
                                        VStack(alignment: .leading, spacing: 2) { Text(kind.title).font(.body.weight(.semibold)); Text(kind.subtitle).font(.caption).foregroundStyle(MaryTheme.muted) }
                                        Spacer(); Image(systemName: "chevron.right").foregroundStyle(MaryTheme.muted)
                                    }.padding(14).background(MaryTheme.surface.opacity(0.8), in: RoundedRectangle(cornerRadius: 18)).overlay(RoundedRectangle(cornerRadius: 18).stroke(MaryTheme.hairline))
                                }.buttonStyle(.plain)
                            }
                        }
                    }
                    Button { app.modal = .settings } label: { Label("Settings", systemImage: "gearshape.fill").frame(maxWidth: .infinity) }.buttonStyle(.bordered)
                }.padding(16)
            }
            .navigationDestination(for: WorkspaceKind.self) { kind in WorkspaceDetailView(kind: kind) }
            .maryScreen()
        }
    }
}
