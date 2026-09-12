import SwiftUI
import UIKit

struct ChatView: View {
    @EnvironmentObject var app: AppState
    @FocusState private var composerFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            presenceHeader
            conversation
            composer
        }
        .background(MaryTheme.bg)
    }

    private var presenceHeader: some View {
        ZStack(alignment: .bottomLeading) {
            MaryArtwork(asset: .portrait, contentMode: .fill)
                .frame(maxWidth: .infinity)
                .frame(height: 124)
                .clipped()
                .overlay {
                    LinearGradient(
                        colors: [MaryTheme.bg.opacity(0.08), MaryTheme.bg.opacity(0.96)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                }

            HStack(alignment: .bottom, spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(app.isConnected ? MaryTheme.green : MaryTheme.orange)
                            .frame(width: 7, height: 7)
                        Text(app.phase.label.uppercased())
                            .font(.system(size: 9, weight: .black))
                            .tracking(1.3)
                            .foregroundStyle(app.isConnected ? MaryTheme.green : MaryTheme.orange)
                    }
                    Text("Talk with Mary")
                        .font(.title2.bold())
                    Text(app.relationship.title + " · " + app.performanceMode.title)
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                }

                Spacer()

                Button {
                    app.modalRoute = .voiceCall
                } label: {
                    Image(systemName: "phone.fill")
                        .foregroundStyle(.white)
                        .frame(width: MaryTheme.minimumTouchTarget, height: MaryTheme.minimumTouchTarget)
                        .background(MaryTheme.pink.opacity(0.22), in: Circle())
                        .overlay(Circle().stroke(MaryTheme.pink.opacity(0.25)))
                }
                .accessibilityLabel("Call Mary")
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 12)
        }
        .frame(height: 124)
    }

    private var conversation: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    conversationControls
                        .padding(.bottom, 2)

                    if app.messages.count <= 1 {
                        starterChips
                    }

                    ForEach(app.messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }

                    if app.isSending {
                        MaryTypingBubble()
                            .id("mary-thinking")
                    }
                }
                .padding(.horizontal, 14)
                .padding(.top, 10)
                .padding(.bottom, 18)
            }
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: app.messages.count) { _ in
                if let last = app.messages.last?.id {
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo(last, anchor: .bottom)
                    }
                }
            }
            .onChange(of: app.isSending) { sending in
                if sending {
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo("mary-thinking", anchor: .bottom)
                    }
                }
            }
        }
    }

    private var conversationControls: some View {
        HStack(spacing: 7) {
            Menu {
                ForEach(ConversationMode.allCases) { mode in
                    Button {
                        app.conversationMode = mode
                        UISelectionFeedbackGenerator().selectionChanged()
                    } label: {
                        Label(mode.detail, systemImage: mode == app.conversationMode ? "checkmark" : "circle")
                    }
                }
            } label: {
                Label(app.conversationMode.label, systemImage: "slider.horizontal.3")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .frame(minHeight: MaryTheme.minimumTouchTarget)
                    .background(MaryTheme.panel2, in: Capsule())
                    .overlay(Capsule().stroke(MaryTheme.hairline))
            }

            Menu {
                ForEach(PerformanceMode.allCases) { mode in
                    Button {
                        Task { await app.changePerformanceMode(mode) }
                    } label: {
                        Label(mode.title, systemImage: mode.symbol)
                    }
                }
            } label: {
                Label(app.performanceMode.title, systemImage: app.performanceMode.symbol)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.cyan : MaryTheme.pink2)
                    .padding(.horizontal, 12)
                    .frame(minHeight: MaryTheme.minimumTouchTarget)
                    .background(MaryTheme.panel2, in: Capsule())
                    .overlay(Capsule().stroke(MaryTheme.hairline))
            }

            Spacer()
        }
    }

    private var starterChips: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("What do you want to do?")
                .font(.caption.weight(.semibold))
                .foregroundStyle(MaryTheme.muted)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    starter("Hang out", "Hang out with me for a bit. No agenda—just talk with me naturally.")
                    starter("Catch up", "Catch up with me. What feels unfinished or worth talking about from our recent shared context?")
                    starter("Create", SharedLifeActivity.create.prompt)
                    starter("Focus", SharedLifeActivity.work.prompt)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func starter(_ title: String, _ prompt: String) -> some View {
        Button {
            app.draft = prompt
            composerFocused = true
            UISelectionFeedbackGenerator().selectionChanged()
        } label: {
            Text(title)
                .font(.caption.bold())
                .foregroundStyle(.white)
                .padding(.horizontal, 13)
                .frame(minHeight: MaryTheme.minimumTouchTarget)
                .background(MaryTheme.surfaceElevated, in: Capsule())
                .overlay(Capsule().stroke(MaryTheme.hairline))
        }
        .buttonStyle(.plain)
    }

    private var composer: some View {
        VStack(spacing: 7) {
            if app.voice.isListening || !app.voice.transcript.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: app.voice.isListening ? "waveform" : "text.bubble.fill")
                        .foregroundStyle(app.voice.isListening ? MaryTheme.pink2 : MaryTheme.cyan)
                    Text(app.voice.transcript.isEmpty ? "Listening…" : app.voice.transcript)
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted)
                        .lineLimit(2)
                    Spacer()
                    if !app.voice.isListening && !app.voice.transcript.isEmpty {
                        Button("Send") { Task { await app.sendVoiceTranscript() } }
                            .font(.caption.bold())
                            .foregroundStyle(MaryTheme.cyan)
                    }
                }
                .padding(.horizontal, 14)
            }

            HStack(alignment: .bottom, spacing: 8) {
                TextField("Message Mary…", text: $app.draft, axis: .vertical)
                    .lineLimit(1...5)
                    .textFieldStyle(.plain)
                    .focused($composerFocused)
                    .submitLabel(.send)
                    .onSubmit { Task { await app.send() } }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 11)
                    .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(MaryTheme.hairline))

                Button {
                    Task { await app.toggleVoiceCapture() }
                } label: {
                    Image(systemName: app.voice.isListening ? "stop.fill" : app.voice.isTranscribing ? "waveform" : "mic.fill")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(app.voice.isListening ? MaryTheme.pink2 : MaryTheme.cyan)
                        .frame(width: 46, height: 46)
                        .background((app.voice.isListening ? MaryTheme.pink : MaryTheme.cyan).opacity(0.10), in: Circle())
                        .overlay(Circle().stroke((app.voice.isListening ? MaryTheme.pink : MaryTheme.cyan).opacity(0.24)))
                }
                .accessibilityLabel(app.voice.isListening ? "Stop listening" : "Talk to Mary")

                Button {
                    Task { await app.send() }
                } label: {
                    Image(systemName: "arrow.up")
                        .font(.headline.weight(.black))
                        .foregroundStyle(.white)
                        .frame(width: 46, height: 46)
                        .background(MaryTheme.gradient, in: Circle())
                }
                .disabled(app.isSending || app.voice.isTranscribing || app.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .opacity(app.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.45 : 1)
                .accessibilityLabel("Send message")
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 8)
        }
        .padding(.top, 8)
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) { Rectangle().fill(MaryTheme.hairline).frame(height: 1) }
    }
}

struct MessageBubble: View {
    let message: MaryMessage

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if message.role == .user { Spacer(minLength: 42) }

            if message.role == .mary {
                ZStack {
                    Circle().fill(MaryTheme.pink.opacity(0.12)).frame(width: 28, height: 28)
                    Text("M")
                        .font(.caption.bold())
                        .foregroundStyle(MaryTheme.pink2)
                }
            }

            VStack(alignment: .leading, spacing: 5) {
                if message.role == .system {
                    Label("System", systemImage: "exclamationmark.triangle.fill")
                        .font(.caption2.bold())
                        .foregroundStyle(MaryTheme.orange)
                }

                Text(message.text)
                    .font(.system(size: 15.5))
                    .foregroundStyle(message.role == .system ? MaryTheme.muted : .white)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.vertical, 10)
            .padding(.horizontal, 12)
            .background(
                message.role == .user
                ? MaryTheme.blue.opacity(0.15)
                : message.role == .system
                ? MaryTheme.orange.opacity(0.06)
                : MaryTheme.panel2,
                in: RoundedRectangle(cornerRadius: 18, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(message.role == .user ? MaryTheme.blue.opacity(0.22) : MaryTheme.hairline)
            )

            if message.role != .user { Spacer(minLength: 42) }
        }
    }
}

struct MaryTypingBubble: View {
    @State private var phase = 0

    var body: some View {
        HStack(alignment: .center, spacing: 8) {
            ZStack {
                Circle().fill(MaryTheme.pink.opacity(0.12)).frame(width: 28, height: 28)
                Text("M").font(.caption.bold()).foregroundStyle(MaryTheme.pink2)
            }
            HStack(spacing: 4) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(MaryTheme.muted)
                        .frame(width: 5, height: 5)
                        .opacity(phase == index ? 1 : 0.35)
                }
            }
            .padding(.horizontal, 13)
            .frame(height: 36)
            .background(MaryTheme.panel2, in: Capsule())
            Spacer()
        }
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 340_000_000)
                withAnimation(.easeInOut(duration: 0.18)) { phase = (phase + 1) % 3 }
            }
        }
    }
}
