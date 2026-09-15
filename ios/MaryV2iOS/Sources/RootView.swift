import SwiftUI

struct RootView: View {
    @EnvironmentObject var app: AppState
    var body: some View {
        ZStack {
            MaryBackground()
            VStack(spacing: 0) {
                topBar
                Group {
                    switch app.selectedTab {
                    case .home: HomeView()
                    case .chat: ChatView()
                    case .command: CommandView()
                    case .focus: FocusView()
                    case .more: MoreView()
                    }
                }
                bottomBar
            }
        }
        .sheet(item: $app.modal) { modal in
            switch modal {
            case .settings: SettingsView()
            case .conversations: ConversationPickerView()
            }
        }
    }

    private var topBar: some View {
        HStack {
            Button { app.selectedTab = .more } label: { Image(systemName: "square.grid.2x2").font(.title3).foregroundStyle(MaryTheme.pinkSoft) }
            Spacer()
            MaryWordmark(compact: true)
            Spacer()
            StatusPill(online: app.isConnected)
        }
        .padding(.horizontal, 18).padding(.vertical, 10)
        .background(.black.opacity(0.18))
        .overlay(alignment: .bottom) { Rectangle().fill(MaryTheme.pink.opacity(0.20)).frame(height: 1) }
    }

    private var bottomBar: some View {
        HStack {
            ForEach(MainTab.allCases) { tab in
                Button { withAnimation(.easeOut(duration: 0.18)) { app.selectedTab = tab } } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.symbol).font(.system(size: 21, weight: .semibold))
                        Text(tab.title).font(.caption2.weight(.semibold))
                    }
                    .frame(maxWidth: .infinity)
                    .foregroundStyle(app.selectedTab == tab ? MaryTheme.pinkSoft : MaryTheme.muted)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.top, 10).padding(.bottom, 6).padding(.horizontal, 10)
        .background(.ultraThinMaterial).overlay(alignment: .top) { Rectangle().fill(MaryTheme.hairline).frame(height: 1) }
    }
}
