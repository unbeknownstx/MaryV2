import SwiftUI

struct RootView: View {
    @EnvironmentObject var app: AppState
    @State private var path: [WorkspaceKind] = []

    var body: some View {
        ZStack {
            MaryBackground()

            NavigationStack(path: $path) {
                VStack(spacing: 0) {
                    MaryTopBar(onSettings: { app.modalRoute = .settings })

                    Group {
                        switch app.selectedTab {
                        case .home: HomeView(navigate: navigate)
                        case .chat: ChatView()
                        case .work: WorkView(navigate: navigate)
                        case .focus: FocusView()
                        case .more: MoreView(navigate: navigate)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                    MaryTabBar()
                }
                .toolbar(.hidden, for: .navigationBar)
                .navigationDestination(for: WorkspaceKind.self) { kind in
                    WorkspaceDetailView(kind: kind)
                        .environmentObject(app)
                }
            }
        }
        .preferredColorScheme(.dark)
        .sheet(item: $app.modalRoute) { route in
            switch route {
            case .settings:
                SettingsView().environmentObject(app)
            case .voiceCall:
                VoiceCallView().environmentObject(app)
            }
        }
        .alert(
            "Mary",
            isPresented: Binding(
                get: { app.lastError != nil },
                set: { if !$0 { app.lastError = nil } }
            )
        ) {
            Button("OK", role: .cancel) { app.lastError = nil }
        } message: {
            Text(app.lastError ?? "")
        }
    }

    private func navigate(_ kind: WorkspaceKind) {
        Task {
            await app.loadWorkspace(kind)
            path.append(kind)
        }
    }
}

struct MaryTopBar: View {
    @EnvironmentObject var app: AppState
    let onSettings: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Button(action: onSettings) {
                Image(systemName: "square.grid.2x2.fill")
                    .font(.title3)
                    .foregroundStyle(MaryTheme.pink)
                    .frame(width: 42, height: 42)
            }

            Spacer()

            VStack(spacing: -2) {
                Text("Mary♡")
                    .font(.system(size: 29, weight: .semibold, design: .serif))
                    .italic()
                Text("M O B I L E")
                    .font(.system(size: 8, weight: .bold))
                    .tracking(2)
                    .foregroundStyle(MaryTheme.muted)
            }

            Spacer()

            StatusPill(
                text: app.isConnected ? app.phase.label : "Offline",
                online: app.isConnected
            )
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 9)
        .background(MaryTheme.bg.opacity(0.94))
        .overlay(alignment: .bottom) {
            Rectangle().fill(MaryTheme.pink.opacity(0.2)).frame(height: 1)
        }
    }
}

struct MaryTabBar: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        HStack {
            ForEach(MainTab.allCases) { tab in
                Button {
                    withAnimation(.easeOut(duration: 0.2)) {
                        app.selectedTab = tab
                    }
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.symbol)
                            .font(.system(size: 19, weight: .semibold))
                        Text(tab.title)
                            .font(.system(size: 10, weight: .semibold))
                    }
                    .foregroundStyle(app.selectedTab == tab ? MaryTheme.pink : MaryTheme.muted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 9)
                }
            }
        }
        .padding(.horizontal, 8)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) {
            Rectangle().fill(MaryTheme.hairline).frame(height: 1)
        }
    }
}
