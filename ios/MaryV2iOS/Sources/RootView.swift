import SwiftUI

struct RootView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        ZStack {
            MaryBackground()

            VStack(spacing: 0) {
                TopBar()

                Group {
                    switch app.selectedTab {
                    case .home: HomeView()
                    case .chat: ChatView()
                    case .command: CommandView()
                    case .focus: FocusView()
                    case .more: MoreView()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                BottomBar()
            }
        }
        .sheet(isPresented: $app.showSettings) {
            SettingsView()
                .environmentObject(app)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $app.showWorkspace) {
            MoreView()
                .environmentObject(app)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
        .sheet(item: $app.activeWorkspace) { kind in
            WorkspaceDetailView(kind: kind)
                .environmentObject(app)
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

struct MaryBackground: View {
    var body: some View {
        ZStack {
            MaryTheme.bg.ignoresSafeArea()

            RadialGradient(
                colors: [MaryTheme.violet.opacity(0.18), .clear],
                center: .topTrailing,
                startRadius: 0,
                endRadius: 340
            )
            .ignoresSafeArea()

            RadialGradient(
                colors: [MaryTheme.pink.opacity(0.09), .clear],
                center: .bottomLeading,
                startRadius: 0,
                endRadius: 360
            )
            .ignoresSafeArea()
        }
    }
}

struct TopBar: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        HStack(spacing: 10) {
            Button { app.showWorkspace = true } label: {
                Image(systemName: "square.grid.2x2")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(MaryTheme.pink2)
                    .frame(width: 42, height: 42)
                    .background(.white.opacity(0.025), in: Circle())
            }

            Spacer()

            VStack(spacing: 0) {
                HStack(spacing: 2) {
                    Text("Mary")
                        .font(.system(size: 25, weight: .bold, design: .rounded))
                    Text("♡")
                        .font(.system(size: 17, weight: .bold))
                        .foregroundStyle(MaryTheme.pink)
                }
                Text("MOBILE")
                    .font(.system(size: 7, weight: .black))
                    .tracking(2.0)
                    .foregroundStyle(MaryTheme.muted)
            }

            Spacer()

            Button { app.showSettings = true } label: {
                HStack(spacing: 6) {
                    Circle()
                        .fill(app.isConnected ? MaryTheme.green : Color.red)
                        .frame(width: 7, height: 7)
                    Text(app.statusText)
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(MaryTheme.muted)
                }
                .padding(.horizontal, 10)
                .frame(height: 34)
                .background(.white.opacity(0.03), in: Capsule())
                .overlay(Capsule().stroke(.white.opacity(0.07)))
            }
        }
        .padding(.horizontal, 10)
        .frame(height: 54)
        .background(.ultraThinMaterial.opacity(0.28))
        .overlay(alignment: .bottom) {
            Rectangle().fill(MaryTheme.line).frame(height: 1)
        }
    }
}

struct BottomBar: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        HStack(spacing: 0) {
            ForEach(MainTab.allCases) { tab in
                Button {
                    app.selectedTab = tab
                } label: {
                    VStack(spacing: 3) {
                        Image(systemName: tab.symbol)
                            .font(.system(size: 18, weight: .semibold))
                        Text(tab.title)
                            .font(.system(size: 9, weight: .semibold))
                    }
                    .foregroundStyle(app.selectedTab == tab ? MaryTheme.pink2 : MaryTheme.muted)
                    .frame(maxWidth: .infinity)
                    .frame(height: 54)
                }
            }
        }
        .background(.ultraThinMaterial.opacity(0.58))
        .overlay(alignment: .top) {
            Rectangle().fill(MaryTheme.line).frame(height: 1)
        }
    }
}
