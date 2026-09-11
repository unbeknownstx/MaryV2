import SwiftUI

struct RootView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        ZStack {
            MaryTheme.bg.ignoresSafeArea()
            RadialGradient(colors: [MaryTheme.violet.opacity(0.20), .clear],
                           center: .topTrailing, startRadius: 10, endRadius: 340)
                .ignoresSafeArea()
            RadialGradient(colors: [MaryTheme.pink.opacity(0.10), .clear],
                           center: .bottomLeading, startRadius: 10, endRadius: 340)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                TopBar()
                Group {
                    switch app.selectedTab {
                    case .home: HomeView()
                    case .chat: ChatView()
                    case .command: SimpleWorkspaceView(title: "Command", subtitle: "Intentional tasks and instructions.")
                    case .focus: FocusWorkspaceView()
                    case .more: MoreView()
                    }
                }
                BottomBar()
            }
        }
        .sheet(isPresented: $app.showSettings) {
            SettingsView().environmentObject(app)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $app.showWorkspace) {
            MoreView().environmentObject(app)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
        .alert("Mary", isPresented: Binding(
            get: { app.lastError != nil },
            set: { if !$0 { app.lastError = nil } }
        )) {
            Button("OK", role: .cancel) { app.lastError = nil }
        } message: {
            Text(app.lastError ?? "")
        }
    }
}

struct TopBar: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        HStack {
            Button { app.showWorkspace = true } label: {
                Image(systemName: "square.grid.2x2")
                    .font(.title3)
                    .foregroundStyle(MaryTheme.pink2)
                    .frame(width: 42, height: 42)
            }

            Spacer()

            VStack(spacing: -1) {
                HStack(spacing: 2) {
                    Text("Mary").font(.system(size: 28, weight: .bold, design: .rounded))
                    Text("♡").foregroundStyle(MaryTheme.pink)
                }
                Text("MOBILE")
                    .font(.system(size: 7, weight: .bold))
                    .tracking(2)
                    .foregroundStyle(MaryTheme.muted)
            }

            Spacer()

            Button { app.showSettings = true } label: {
                HStack(spacing: 6) {
                    Circle()
                        .fill(app.isConnected ? MaryTheme.green : Color.red)
                        .frame(width: 8, height: 8)
                    Text(app.statusText)
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(MaryTheme.muted)
                }
                .padding(.horizontal, 11)
                .frame(height: 36)
                .background(.white.opacity(0.035), in: Capsule())
                .overlay(Capsule().stroke(.white.opacity(0.08)))
            }
        }
        .padding(.horizontal, 10)
        .frame(height: 58)
        .background(.ultraThinMaterial.opacity(0.35))
        .overlay(alignment: .bottom) { Rectangle().fill(MaryTheme.line).frame(height: 1) }
    }
}

struct BottomBar: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        HStack(spacing: 0) {
            ForEach(MainTab.allCases) { tab in
                Button { app.selectedTab = tab } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.symbol).font(.system(size: 19, weight: .semibold))
                        Text(tab.title).font(.system(size: 9, weight: .semibold))
                    }
                    .foregroundStyle(app.selectedTab == tab ? MaryTheme.pink2 : MaryTheme.muted)
                    .frame(maxWidth: .infinity)
                    .frame(height: 58)
                }
            }
        }
        .background(.ultraThinMaterial.opacity(0.65))
        .overlay(alignment: .top) { Rectangle().fill(MaryTheme.line).frame(height: 1) }
    }
}

struct SimpleWorkspaceView: View {
    let title: String
    let subtitle: String

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("MARY SYSTEM").font(.caption2.weight(.black)).tracking(1.8).foregroundStyle(MaryTheme.pink2)
                Text(title).font(.largeTitle.bold())
                Text(subtitle).foregroundStyle(MaryTheme.muted)
                MaryPanel {
                    Text("This native workspace is ready for the next migration pass.")
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(13)
        }
    }
}

struct FocusWorkspaceView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("MARY SYSTEM").font(.caption2.weight(.black)).tracking(1.8).foregroundStyle(MaryTheme.pink2)
                Text("Focus").font(.largeTitle.bold())
                Text("Quiet the room and reduce interruption while you work.")
                    .foregroundStyle(MaryTheme.muted)

                MaryPanel {
                    VStack(spacing: 18) {
                        ZStack {
                            Circle().stroke(.white.opacity(0.06), lineWidth: 9)
                            Circle().trim(from: 0, to: 0.72)
                                .stroke(MaryTheme.accentGradient, style: StrokeStyle(lineWidth: 9, lineCap: .round))
                                .rotationEffect(.degrees(-90))
                            VStack {
                                Text("25:00").font(.system(size: 38, weight: .bold, design: .rounded))
                                Text("FOCUS READY").font(.caption2.weight(.black)).tracking(1.8).foregroundStyle(MaryTheme.cyan)
                            }
                        }
                        .frame(width: 210, height: 210)

                        Button("Set Mary to Focus") {
                            Task { await app.changePerformanceMode(.focus) }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(MaryTheme.violet)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(13)
        }
    }
}
