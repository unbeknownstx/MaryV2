import SwiftUI
import UIKit

struct ChatView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        VStack(spacing: 0) {
            ZStack {
                LinearGradient(
                    colors: [Color(red: 0.035, green: 0.035, blue: 0.11), MaryTheme.bg],
                    startPoint: .top,
                    endPoint: .bottom
                )

                VStack(spacing: 8) {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("MARY").font(.caption.weight(.black)).tracking(2.1)
                            Text("Your AI Companion").font(.caption2).foregroundStyle(MaryTheme.muted)
                        }
                        Spacer()
                        HStack(spacing: 5) {
                            Circle().fill(MaryTheme.green).frame(width: 6, height: 6)
                            Text("LIVE").font(.caption2.weight(.bold)).foregroundStyle(MaryTheme.green)
                        }
                        .padding(.horizontal, 9).padding(.vertical, 6)
                        .background(MaryTheme.green.opacity(0.05), in: Capsule())
                        .overlay(Capsule().stroke(MaryTheme.green.opacity(0.25)))
                    }
                    .padding(.horizontal, 6)

                    HStack(spacing: 4) {
                        ForEach(ConversationMode.allCases) { mode in
                            Button { app.conversationMode = mode } label: {
                                Text(mode.label)
                                    .font(.system(size: 9, weight: .black))
                                    .padding(.horizontal, 10).padding(.vertical, 7)
                                    .foregroundStyle(app.conversationMode == mode ? .white : MaryTheme.muted)
                                    .background(app.conversationMode == mode ? MaryTheme.violet.opacity(0.28) : .clear)
                                    .clipShape(Capsule())
                            }
                        }

                        Spacer(minLength: 4)

                        Menu {
                            ForEach(PerformanceMode.allCases) { mode in
                                Button(mode.title) {
                                    Task { await app.changePerformanceMode(mode) }
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: app.performanceMode.isPublic ? "person.3.fill" : "person.fill")
                                Text(app.performanceMode.title.uppercased())
                            }
                            .font(.system(size: 8, weight: .bold))
                            .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                        }
                    }
                    .padding(4)
                    .background(.black.opacity(0.18), in: Capsule())
                    .overlay(Capsule().stroke(MaryTheme.cyan.opacity(0.13)))

                    ZStack(alignment: .bottomLeading) {
                        Circle()
                            .stroke(MaryTheme.pink.opacity(0.16), lineWidth: 1)
                            .frame(width: 280, height: 280)
                        Circle()
                            .stroke(MaryTheme.cyan.opacity(0.12), lineWidth: 1)
                            .frame(width: 220, height: 220)

                        Group {
                            if let path = Bundle.main.path(forResource: "mary-reference", ofType: "jpeg"),
                               let image = UIImage(contentsOfFile: path) {
                                Image(uiImage: image)
                                    .resizable()
                                    .scaledToFill()
                                    .saturation(1.08)
                                    .overlay(
                                        LinearGradient(
                                            colors: [.clear, MaryTheme.bg.opacity(0.92)],
                                            startPoint: .center,
                                            endPoint: .bottom
                                        )
                                    )
                            } else {
                                ZStack {
                                    RadialGradient(colors: [MaryTheme.violet.opacity(0.28), .clear],
                                                   center: .center, startRadius: 5, endRadius: 160)
                                    Image(systemName: "sparkles")
                                        .font(.system(size: 58))
                                        .foregroundStyle(MaryTheme.cyan)
                                }
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .frame(height: 245)
                        .clipped()

                        HStack(spacing: 8) {
                            Text(app.isSending ? "THINKING" : "IDLE")
                                .font(.system(size: 8, weight: .bold))
                                .tracking(1.2)
                                .foregroundStyle(MaryTheme.cyan)
                            Text(app.performanceMode.title)
                                .font(.caption2.weight(.semibold))
                        }
                        .padding(.horizontal, 10).padding(.vertical, 7)
                        .background(.black.opacity(0.58), in: RoundedRectangle(cornerRadius: 9))
                        .overlay(RoundedRectangle(cornerRadius: 9).stroke(MaryTheme.line))
                        .padding(8)
                    }
                    .frame(maxWidth: .infinity)

                    ScrollViewReader { proxy in
                        ScrollView {
                            LazyVStack(spacing: 10) {
                                ForEach(app.messages) { message in
                                    MessageBubble(message: message).id(message.id)
                                }
                                if app.isSending {
                                    HStack(spacing: 6) {
                                        ProgressView().tint(MaryTheme.pink2)
                                        Text("Mary is thinking").font(.caption2).foregroundStyle(MaryTheme.muted)
                                        Spacer()
                                    }
                                }
                            }
                            .padding(12)
                        }
                        .frame(minHeight: 150, maxHeight: 230)
                        .background(
                            LinearGradient(
                                colors: [MaryTheme.panel.opacity(0.88), MaryTheme.bg.opacity(0.95)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            in: RoundedRectangle(cornerRadius: 20)
                        )
                        .overlay(RoundedRectangle(cornerRadius: 20).stroke(MaryTheme.line))
                        .onChange(of: app.messages.count) { _ in
                            if let last = app.messages.last?.id {
                                withAnimation { proxy.scrollTo(last, anchor: .bottom) }
                            }
                        }
                    }
                }
                .padding(.horizontal, 9)
                .padding(.top, 10)
                .padding(.bottom, 7)
            }

            HStack(spacing: 7) {
                TextField("Message Mary…", text: $app.draft, axis: .vertical)
                    .lineLimit(1...4)
                    .textFieldStyle(.plain)
                    .font(.body)
                    .submitLabel(.send)
                    .onSubmit { Task { await app.send() } }

                Button {
                    app.lastError = "Native push-to-talk is next in Phase 3B."
                } label: {
                    Image(systemName: "mic.fill")
                        .foregroundStyle(MaryTheme.cyan)
                        .frame(width: 42, height: 42)
                        .background(MaryTheme.cyan.opacity(0.07), in: Circle())
                        .overlay(Circle().stroke(MaryTheme.cyan.opacity(0.22)))
                }

                Button { Task { await app.send() } } label: {
                    Image(systemName: "arrow.up")
                        .font(.headline.weight(.black))
                        .foregroundStyle(.white)
                        .frame(width: 42, height: 42)
                        .background(MaryTheme.accentGradient, in: Circle())
                }
                .disabled(app.isSending || app.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.leading, 14).padding(.trailing, 8).padding(.vertical, 8)
            .background(.ultraThinMaterial.opacity(0.70))
            .overlay(alignment: .top) { Rectangle().fill(MaryTheme.line).frame(height: 1) }
        }
    }
}

struct MessageBubble: View {
    let message: MaryMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer(minLength: 48) }

            VStack(alignment: .leading, spacing: 4) {
                Text(message.role == .user ? "Unbe" : message.role == .mary ? "Mary" : "System")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(message.role == .user ? MaryTheme.cyan : MaryTheme.pink2)
                Text(message.text)
                    .font(.system(size: 15))
                    .foregroundStyle(.white)
                    .textSelection(.enabled)
            }
            .padding(.vertical, 9).padding(.horizontal, 11)
            .background(
                message.role == .user ? MaryTheme.cyan.opacity(0.055) : MaryTheme.pink.opacity(0.055),
                in: RoundedRectangle(cornerRadius: 11)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 11)
                    .stroke(message.role == .user ? MaryTheme.cyan.opacity(0.22) : MaryTheme.pink.opacity(0.20))
            )

            if message.role != .user { Spacer(minLength: 48) }
        }
    }
}
