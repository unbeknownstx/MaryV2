import SwiftUI
import UIKit

struct ChatView: View {
    @EnvironmentObject var app: AppState
    var body: some View {
        GeometryReader { geo in
            let compact = geo.size.height < 620
            let portraitHeight = max(180, min(compact ? 210 : 280, geo.size.height * 0.34))
            let messageHeight = max(150, min(compact ? 175 : 250, geo.size.height * 0.30))

            VStack(spacing: 0) {
                ZStack {
                    LinearGradient(
                        colors: [MaryTheme.bg2, MaryTheme.bg],
                        startPoint: .top,
                        endPoint: .bottom
                    )

                    VStack(spacing: compact ? 6 : 8) {
                        stageHeader
                        modeBar
                        portraitStage(height: portraitHeight)
                        messagesPanel(height: messageHeight)
                    }
                    .padding(.horizontal, 9)
                    .padding(.top, 8)
                    .padding(.bottom, 7)
                }

                composer
            }
        }
    }

    private var stageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 1) {
                Text("MARY")
                    .font(.system(size: 12, weight: .black))
                    .tracking(1.8)
                Text("Your AI Companion")
                    .font(.system(size: 9))
                    .foregroundStyle(MaryTheme.muted)
            }

            Spacer()

            HStack(spacing: 5) {
                Circle().fill(app.isConnected ? MaryTheme.green : Color.red).frame(width: 6, height: 6)
                Text(app.isConnected ? "LIVE" : "OFFLINE")
                    .font(.system(size: 8, weight: .bold))
                    .foregroundStyle(app.isConnected ? MaryTheme.green : .red)
            }
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background((app.isConnected ? MaryTheme.green : Color.red).opacity(0.05), in: Capsule())
            .overlay(Capsule().stroke((app.isConnected ? MaryTheme.green : Color.red).opacity(0.22)))
        }
        .padding(.horizontal, 5)
    }

    private var modeBar: some View {
        HStack(spacing: 3) {
            ForEach(ConversationMode.allCases) { mode in
                Button {
                    app.conversationMode = mode
                } label: {
                    Text(mode.label)
                        .font(.system(size: 9, weight: .black))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .foregroundStyle(app.conversationMode == mode ? .white : MaryTheme.muted)
                        .background(app.conversationMode == mode ? MaryTheme.violet.opacity(0.34) : .clear)
                        .clipShape(Capsule())
                }
            }

            Spacer(minLength: 4)

            Menu {
                ForEach(PerformanceMode.allCases) { mode in
                    Button {
                        Task { await app.changePerformanceMode(mode) }
                    } label: {
                        Label(mode.title, systemImage: mode.symbol)
                    }
                }
            } label: {
                HStack(spacing: 5) {
                    Image(systemName: app.performanceMode.symbol)
                    Text(app.performanceMode.title.uppercased())
                }
                .font(.system(size: 8, weight: .bold))
                .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
            }
        }
        .padding(4)
        .background(.black.opacity(0.16), in: Capsule())
        .overlay(Capsule().stroke(MaryTheme.cyan.opacity(0.13)))
    }

    private func portraitStage(height: CGFloat) -> some View {
        ZStack(alignment: .bottomLeading) {
            Circle()
                .stroke(MaryTheme.pink.opacity(0.14), lineWidth: 1)
                .frame(width: height * 1.05, height: height * 1.05)

            Circle()
                .stroke(MaryTheme.cyan.opacity(0.10), lineWidth: 1)
                .frame(width: height * 0.78, height: height * 0.78)

            Group {
                if let path = Bundle.main.path(forResource: "mary-reference", ofType: "jpeg"),
                   let image = UIImage(contentsOfFile: path) {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFill()
                        .saturation(1.08)
                        .overlay(
                            LinearGradient(
                                colors: [.clear, MaryTheme.bg.opacity(0.90)],
                                startPoint: .center,
                                endPoint: .bottom
                            )
                        )
                } else {
                    ZStack {
                        RadialGradient(
                            colors: [MaryTheme.violet.opacity(0.30), .clear],
                            center: .center,
                            startRadius: 0,
                            endRadius: height * 0.55
                        )
                        Image(systemName: "sparkles")
                            .font(.system(size: 54))
                            .foregroundStyle(MaryTheme.cyan)
                    }
                }
            }
            .frame(maxWidth: .infinity)
            .frame(height: height)
            .clipped()

            HStack(spacing: 7) {
                Text(app.voice.isListening ? "LISTENING" : app.isSending ? "THINKING" : "IDLE")
                    .font(.system(size: 8, weight: .black))
                    .tracking(1.1)
                    .foregroundStyle(app.voice.isListening ? MaryTheme.pink2 : MaryTheme.cyan)
                Text(app.performanceMode.title)
                    .font(.system(size: 10, weight: .semibold))
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(.black.opacity(0.60), in: RoundedRectangle(cornerRadius: 9))
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(MaryTheme.line))
            .padding(8)
        }
        .frame(maxWidth: .infinity)
        .frame(height: height)
    }

    private func messagesPanel(height: CGFloat) -> some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 9) {
                    ForEach(app.messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }

                    if app.isSending {
                        HStack(spacing: 7) {
                            ProgressView().tint(MaryTheme.pink2)
                            Text("Mary is thinking")
                                .font(.caption2)
                                .foregroundStyle(MaryTheme.muted)
                            Spacer()
                        }
                    }
                }
                .padding(11)
            }
            .frame(height: height)
            .background(
                LinearGradient(
                    colors: [MaryTheme.panel.opacity(0.90), MaryTheme.bg.opacity(0.97)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                ),
                in: RoundedRectangle(cornerRadius: 19)
            )
            .overlay(RoundedRectangle(cornerRadius: 19).stroke(MaryTheme.line))
            .onChange(of: app.messages.count) { _ in
                if let last = app.messages.last?.id {
                    withAnimation(.easeOut(duration: 0.18)) {
                        proxy.scrollTo(last, anchor: .bottom)
                    }
                }
            }
        }
    }

    private var composer: some View {
        VStack(spacing: 5) {
            if app.voice.isListening || !app.voice.transcript.isEmpty {
                HStack(spacing: 8) {
                    Circle()
                        .fill(app.voice.isListening ? MaryTheme.pink : MaryTheme.cyan)
                        .frame(width: 7, height: 7)

                    Text(app.voice.transcript.isEmpty ? "Listening…" : app.voice.transcript)
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                        .lineLimit(2)

                    Spacer()

                    if !app.voice.isListening && !app.voice.transcript.isEmpty {
                        Button("Send") {
                            Task { await app.sendVoiceTranscript() }
                        }
                        .font(.caption.bold())
                        .foregroundStyle(MaryTheme.cyan)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.top, 6)
            }

            HStack(spacing: 7) {
                TextField("Message Mary…", text: $app.draft, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.plain)
                    .submitLabel(.send)
                    .onSubmit { Task { await app.send() } }

                Button {
                    if app.voice.isListening {
                        app.voice.stop()
                    } else {
                        Task { await app.voice.start() }
                    }
                } label: {
                    Image(systemName: app.voice.isListening ? "stop.fill" : "mic.fill")
                        .foregroundStyle(app.voice.isListening ? MaryTheme.pink2 : MaryTheme.cyan)
                        .frame(width: 42, height: 42)
                        .background((app.voice.isListening ? MaryTheme.pink : MaryTheme.cyan).opacity(0.07), in: Circle())
                        .overlay(Circle().stroke((app.voice.isListening ? MaryTheme.pink : MaryTheme.cyan).opacity(0.24)))
                }

                Button {
                    Task { await app.send() }
                } label: {
                    Image(systemName: "arrow.up")
                        .font(.headline.weight(.black))
                        .foregroundStyle(.white)
                        .frame(width: 42, height: 42)
                        .background(MaryTheme.accent, in: Circle())
                }
                .disabled(app.isSending || app.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.horizontal, 9)
            .padding(.bottom, 7)
        }
        .background(.ultraThinMaterial.opacity(0.67))
        .overlay(alignment: .top) { Rectangle().fill(MaryTheme.line).frame(height: 1) }
    }
}

struct MessageBubble: View {
    let message: MaryMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 44) }

            VStack(alignment: .leading, spacing: 4) {
                Text(message.role == .user ? "Unbe" : message.role == .mary ? "Mary" : "System")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(message.role == .user ? MaryTheme.cyan : MaryTheme.pink2)

                Text(message.text)
                    .font(.system(size: 15))
                    .foregroundStyle(.white)
                    .textSelection(.enabled)
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 10)
            .background(
                message.role == .user ? MaryTheme.cyan.opacity(0.055) : MaryTheme.pink.opacity(0.055),
                in: RoundedRectangle(cornerRadius: 11)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 11)
                    .stroke(message.role == .user ? MaryTheme.cyan.opacity(0.20) : MaryTheme.pink.opacity(0.18))
            )

            if message.role != .user { Spacer(minLength: 44) }
        }
    }
}
