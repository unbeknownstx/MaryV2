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
                    Text("More")
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                    Text("Memory, focus, creative tools, devices, and the systems behind your shared experience.")
                        .foregroundStyle(MaryTheme.muted)
                }

                FocusShortcut {
                    app.selectedTab = .focus
                }

                section("Companion", items: companion)
                section("Create & media", items: create)
                section("Connected systems", items: system)

                Button { app.modalRoute = .settings } label: {
                    HStack(spacing: 13) {
                        iconTile("gearshape.fill", tint: MaryTheme.cyan)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Settings").font(.headline)
                            Text("Mary Core, connection, voice and privacy")
                                .font(.caption)
                                .foregroundStyle(MaryTheme.muted)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                            .foregroundStyle(MaryTheme.muted.opacity(0.6))
                    }
                    .padding(14)
                    .background(MaryTheme.panel, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(MaryTheme.hairline))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white)
            }
            .padding(16)
            .padding(.bottom, 12)
        }
    }

    @ViewBuilder
    private func section(_ title: String, items: [WorkspaceKind]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.title3.bold())
            ForEach(items) { item in
                Button { navigate(item) } label: {
                    HStack(spacing: 13) {
                        iconTile(item.symbol, tint: MaryTheme.pink2)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.title).font(.headline)
                            Text(item.subtitle).font(.caption).foregroundStyle(MaryTheme.muted)
                        }

                        Spacer()
                        Image(systemName: "chevron.right")
                            .foregroundStyle(MaryTheme.muted.opacity(0.55))
                    }
                    .padding(14)
                    .background(MaryTheme.panel, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(MaryTheme.hairline))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white)
            }
        }
    }

    private func iconTile(_ symbol: String, tint: Color) -> some View {
        ZStack {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .fill(tint.opacity(0.10))
                .frame(width: 42, height: 42)
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(tint)
        }
    }
}

private struct FocusShortcut: View {
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                ZStack {
                    Circle()
                        .fill(MaryTheme.violet.opacity(0.15))
                        .frame(width: 52, height: 52)
                    Image(systemName: "scope")
                        .font(.title3.bold())
                        .foregroundStyle(MaryTheme.cyan)
                }

                VStack(alignment: .leading, spacing: 3) {
                    Text("Focus with Mary")
                        .font(.headline)
                    Text("Quiet task-centered presence without leaving the companion app.")
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                }
                Spacer()
                Image(systemName: "arrow.right")
                    .foregroundStyle(MaryTheme.cyan)
            }
            .padding(16)
            .background(
                LinearGradient(
                    colors: [MaryTheme.surfaceElevated, MaryTheme.panel],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: RoundedRectangle(cornerRadius: 22, style: .continuous)
            )
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).stroke(MaryTheme.cyan.opacity(0.13)))
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
    }
}
