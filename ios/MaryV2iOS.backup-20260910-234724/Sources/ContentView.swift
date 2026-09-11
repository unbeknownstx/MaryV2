import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var appState: AppState
    @State private var composer = ""

    var body: some View {
        NavigationStack {
            ZStack {
                LinearGradient(
                    colors: [
                        Color(red: 0.025, green: 0.035, blue: 0.09),
                        Color(red: 0.06, green: 0.02, blue: 0.11)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ).ignoresSafeArea()

                VStack(spacing: 0) {
                    statusBar
                    Divider().overlay(Color.cyan.opacity(0.25))
                    conversation
                    composerBar
                }
            }
            .navigationTitle("Mary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { appState.showingSettings = true } label: {
                        Image(systemName: "gearshape.fill")
                    }
                }
            }
            .sheet(isPresented: $appState.showingSettings) {
                SettingsView().environmentObject(appState)
            }
        }
        .tint(.cyan)
    }

    private var statusBar: some View {
        HStack(spacing: 9) {
            Circle()
                .fill(appState.isOnline ? Color.green : Color.orange)
                .frame(width: 8, height: 8)
            Text(appState.isOnline ? "Canonical Core" : "Not connected")
                .font(.caption.weight(.semibold))
            Spacer()
            Text(appState.coreStatus)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.black.opacity(0.18))
    }

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 14) {
                    if appState.messages.isEmpty {
                        VStack(spacing: 10) {
                            Image(systemName: "sparkles")
                                .font(.system(size: 36))
                                .foregroundStyle(.cyan)
                            Text("Mary is here.")
                                .font(.title3.weight(.semibold))
                            Text("This iPhone is a surface for the same canonical Mary running on Core.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 30)
                        }
                        .padding(.top, 70)
                    }

                    ForEach(appState.messages) { message in
                        MessageBubble(message: message).id(message.id)
                    }

                    if appState.isSending {
                        HStack {
                            ProgressView()
                            Text("Mary is thinking…")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Spacer()
                        }.padding(.horizontal)
                    }
                }
                .padding(.vertical, 16)
            }
            .onChange(of: appState.messages.count) { _ in
                if let last = appState.messages.last {
                    withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
        }
    }

    private var composerBar: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Message Mary…", text: $composer, axis: .vertical)
                .lineLimit(1...5)
                .padding(.horizontal, 14)
                .padding(.vertical, 11)
                .background(
                    RoundedRectangle(cornerRadius: 18)
                        .fill(Color.white.opacity(0.08))
                        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Color.cyan.opacity(0.25)))
                )

            Button {
                let text = composer
                composer = ""
                Task { await appState.send(text) }
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 34))
                    .symbolRenderingMode(.palette)
                    .foregroundStyle(.white, .cyan)
            }
            .disabled(composer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || appState.isSending)
        }
        .padding(12)
        .background(.ultraThinMaterial)
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 42) }

            VStack(alignment: .leading, spacing: 5) {
                Text(label)
                    .font(.caption.weight(.bold))
                    .foregroundStyle(labelColor)
                Text(message.text)
                    .font(.body)
                    .textSelection(.enabled)
            }
            .padding(12)
            .background(background)
            .clipShape(RoundedRectangle(cornerRadius: 16))

            if message.role != .user { Spacer(minLength: 42) }
        }
        .padding(.horizontal, 12)
    }

    private var label: String {
        switch message.role {
        case .user: return "Unbe"
        case .mary: return "Mary"
        case .system: return "System"
        }
    }

    private var labelColor: Color {
        switch message.role {
        case .user: return .cyan
        case .mary: return .pink
        case .system: return .orange
        }
    }

    private var background: Color {
        switch message.role {
        case .user: return Color.blue.opacity(0.20)
        case .mary: return Color.purple.opacity(0.24)
        case .system: return Color.orange.opacity(0.14)
        }
    }
}
