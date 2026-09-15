import SwiftUI
import UIKit

struct RootView: View {
    @EnvironmentObject var app: AppState
<<<<<<< HEAD
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
=======
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
                        case .together: TogetherView()
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
                Image(systemName: "line.3.horizontal")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: MaryTheme.minimumTouchTarget, height: MaryTheme.minimumTouchTarget)
                    .background(MaryTheme.panel2.opacity(0.82), in: Circle())
                    .overlay(Circle().stroke(MaryTheme.hairline))
            }
            .accessibilityLabel("Open Mary settings")

            Spacer()

            VStack(spacing: -1) {
                Text("Mary♡")
                    .font(.system(size: 28, weight: .semibold, design: .serif))
                    .italic()
                Text(app.performanceMode.isPublic ? "PUBLIC PRESENCE" : "PRIVATE PRESENCE")
                    .font(.system(size: 8, weight: .black))
                    .tracking(1.7)
                    .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.cyan : MaryTheme.pink2)
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
            }
        }
    }

    private var topBar: some View {
        HStack {
            Button { app.selectedTab = .more } label: { Image(systemName: "square.grid.2x2").font(.title3).foregroundStyle(MaryTheme.pinkSoft) }
            Spacer()
<<<<<<< HEAD
            MaryWordmark(compact: true)
            Spacer()
            StatusPill(online: app.isConnected)
=======

            Button {
                app.modalRoute = .voiceCall
            } label: {
                ZStack {
                    Circle()
                        .fill((app.isConnected ? MaryTheme.green : MaryTheme.orange).opacity(0.10))
                        .frame(width: MaryTheme.minimumTouchTarget, height: MaryTheme.minimumTouchTarget)
                    Image(systemName: app.phase.symbol)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(app.isConnected ? MaryTheme.green : MaryTheme.orange)
                }
            }
            .accessibilityLabel(app.isConnected ? "Mary is \(app.phase.label). Open voice call." : "Mary is offline")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 7)
        .background(.ultraThinMaterial)
        .overlay(alignment: .bottom) {
            Rectangle().fill(MaryTheme.hairline).frame(height: 1)
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
        }
        .padding(.horizontal, 18).padding(.vertical, 10)
        .background(.black.opacity(0.18))
        .overlay(alignment: .bottom) { Rectangle().fill(MaryTheme.pink.opacity(0.20)).frame(height: 1) }
    }

<<<<<<< HEAD
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
=======
struct MaryTabBar: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        HStack(spacing: 4) {
            ForEach(MainTab.primaryTabs) { tab in
                Button {
                    withAnimation(.easeOut(duration: 0.18)) {
                        app.selectedTab = tab
                    }
                    UISelectionFeedbackGenerator().selectionChanged()
                } label: {
                    VStack(spacing: 4) {
                        ZStack {
                            if app.selectedTab == tab {
                                Capsule()
                                    .fill(MaryTheme.pink.opacity(0.12))
                                    .frame(width: 36, height: 26)
                            }
                            Image(systemName: tab.symbol)
                                .font(.system(size: 18, weight: .semibold))
                        }
                        Text(tab.title)
                            .font(.system(size: 9, weight: .bold))
                    }
                    .foregroundStyle(app.selectedTab == tab ? MaryTheme.pink2 : MaryTheme.muted2)
                    .frame(maxWidth: .infinity)
                    .frame(minHeight: 54)
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
                }
                .buttonStyle(.plain)
            }
        }
<<<<<<< HEAD
        .padding(.top, 10).padding(.bottom, 6).padding(.horizontal, 10)
        .background(.ultraThinMaterial).overlay(alignment: .top) { Rectangle().fill(MaryTheme.hairline).frame(height: 1) }
=======
        .padding(.horizontal, 8)
        .padding(.bottom, 2)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) {
            Rectangle().fill(MaryTheme.hairline).frame(height: 1)
        }
>>>>>>> af6a549d6369d98ee0b5399980c297e333b8962c
    }
}
