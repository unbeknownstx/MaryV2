import SwiftUI

struct ChatView: View {
    @EnvironmentObject var app: AppState
    @FocusState private var focused: Bool
    var body: some View {
        VStack(spacing: 0) {
            modeBar
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        MaryStageView(height: 255).padding(.horizontal, 14).padding(.top, 12)
                        ForEach(app.messages) { message in MessageBubble(message: message).id(message.id) }
                        if app.isSending { HStack { ProgressView(); Text("Mary is thinking…").foregroundStyle(MaryTheme.muted); Spacer() }.padding(.horizontal, 18) }
                    }
                    .padding(.bottom, 14)
                }
                .onChange(of: app.messages.count) { _ in if let last = app.messages.last { withAnimation { proxy.scrollTo(last.id, anchor: .bottom) } } }
            }
            composer
        }
        .maryScreen()
    }

    private var modeBar: some View {
        HStack(spacing: 4) {
            ForEach(ConversationMode.allCases) { mode in
                Button { Task { await app.setConversationMode(mode) } } label: {
                    Text(mode.label).font(.caption.bold()).padding(.horizontal, 13).padding(.vertical, 8)
                        .background(app.conversationMode == mode ? MaryTheme.violet.opacity(0.65) : .clear, in: Capsule())
                }.buttonStyle(.plain)
            }
            Spacer()
            Button { app.modal = .conversations } label: { Label("Main", systemImage: "chevron.down").labelStyle(.titleAndIcon).font(.caption.bold()).foregroundStyle(MaryTheme.cyan) }
        }
        .padding(10).background(MaryTheme.surface.opacity(0.85)).overlay(alignment: .bottom) { Rectangle().fill(MaryTheme.hairline).frame(height: 1) }
    }

    private var composer: some View {
        HStack(spacing: 10) {
            TextField("Message Mary…", text: $app.draft, axis: .vertical).lineLimit(1...4).focused($focused)
                .padding(.horizontal, 14).padding(.vertical, 12).background(.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 18)).overlay(RoundedRectangle(cornerRadius: 18).stroke(MaryTheme.hairline))
            Button { Task { await app.toggleVoice() } } label: {
                Image(systemName: app.voice.isListening ? "stop.fill" : "mic.fill").font(.title3).frame(width: 48, height: 48).background(MaryTheme.cyan.opacity(0.12), in: Circle()).foregroundStyle(MaryTheme.cyan)
            }
            Button { Task { await app.send() } } label: { Image(systemName: "arrow.up").font(.title3.bold()).frame(width: 48, height: 48).background(LinearGradient(colors: [MaryTheme.pink, MaryTheme.violet], startPoint: .topLeading, endPoint: .bottomTrailing), in: Circle()).foregroundStyle(.white) }
                .disabled(app.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || app.isSending)
        }
        .padding(12).background(.ultraThinMaterial).overlay(alignment: .top) { Rectangle().fill(MaryTheme.hairline).frame(height: 1) }
    }
}

struct MessageBubble: View {
    let message: MaryMessage
    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 56) }
            VStack(alignment: .leading, spacing: 5) {
                Text(message.role == .mary ? "Mary" : message.role == .user ? "You" : "System").font(.caption.bold()).foregroundStyle(message.role == .mary ? MaryTheme.pinkSoft : MaryTheme.cyan)
                Text(message.text).font(.body).textSelection(.enabled)
            }
            .padding(14).background(message.role == .user ? MaryTheme.surface2 : MaryTheme.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20).stroke(message.role == .mary ? MaryTheme.pink.opacity(0.22) : MaryTheme.hairline))
            if message.role != .user { Spacer(minLength: 36) }
        }.padding(.horizontal, 14)
    }
}
