import SwiftUI

struct MoreView: View {
    @EnvironmentObject var app: AppState
    let navigate: (WorkspaceKind) -> Void

    private let companion: [WorkspaceKind] = [.memories, .growth, .personality, .presence]
    private let create: [WorkspaceKind] = [.gallery, .voiceAvatar, .media]
    private let system: [WorkspaceKind] = [.devices, .integrations, .world, .training]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 5) {
                    Eyebrow(text: "Mary")
                    Text("Everything else").font(.largeTitle.bold())
                    Text("Companion continuity, creative tools, devices, and connected systems.")
                        .foregroundStyle(MaryTheme.muted)
                }

                section("Companion", items: companion)
                section("Create & media", items: create)
                section("Connected systems", items: system)

                Button { app.modalRoute = .settings } label: {
                    HStack {
                        Image(systemName: "gearshape.fill").foregroundStyle(MaryTheme.cyan)
                        Text("Settings").font(.headline)
                        Spacer()
                        Image(systemName: "chevron.right").foregroundStyle(MaryTheme.muted)
                    }
                    .padding(16)
                    .background(MaryTheme.panel, in: RoundedRectangle(cornerRadius: 20))
                    .overlay(RoundedRectangle(cornerRadius: 20).stroke(MaryTheme.hairline))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white)
            }
            .padding(16)
        }
    }

    @ViewBuilder
    private func section(_ title: String, items: [WorkspaceKind]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.title3.bold())
            ForEach(items) { item in
                Button { navigate(item) } label: {
                    HStack(spacing: 13) {
                        Image(systemName: item.symbol)
                            .font(.title3)
                            .foregroundStyle(MaryTheme.pink)
                            .frame(width: 30)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.title).font(.headline)
                            Text(item.subtitle).font(.caption).foregroundStyle(MaryTheme.muted)
                        }

                        Spacer()
                        Image(systemName: "chevron.right")
                            .foregroundStyle(MaryTheme.muted.opacity(0.6))
                    }
                    .padding(14)
                    .background(MaryTheme.panel, in: RoundedRectangle(cornerRadius: 20))
                    .overlay(RoundedRectangle(cornerRadius: 20).stroke(MaryTheme.hairline))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white)
            }
        }
    }
}
