import SwiftUI

struct VoiceCallView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            MaryBackground()
            VStack(spacing: 20) {
                HStack {
                    Button {
                        app.playback.stop()
                        app.voice.cancel()
                        dismiss()
                    } label: {
                        Image(systemName: "chevron.down")
                            .font(.title2.bold())
                            .frame(width: 48, height: 48)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    Spacer()
                    StatusPill(text: app.phase.label, online: app.isConnected)
                }
                .padding(.horizontal, 18)

                Spacer(minLength: 0)

                MaryArtwork(asset: .portrait, contentMode: .fill)
                    .frame(width: 260, height: 360)
                    .clipped()
                    .clipShape(RoundedRectangle(cornerRadius: 36, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 36).stroke(MaryTheme.pink.opacity(0.25)))
                    .shadow(color: MaryTheme.violet.opacity(0.22), radius: 35)

                VStack(spacing: 6) {
                    Text("Mary").font(.largeTitle.bold())
                    Text(app.voiceServerAvailable ? "\(app.voiceProvider.capitalized) voice" : "Voice unavailable")
                        .foregroundStyle(MaryTheme.muted)
                }

                if app.voice.isListening {
                    Text("Listening… tap again when you're done")
                        .font(.subheadline)
                        .foregroundStyle(MaryTheme.cyan)
                }

                Spacer(minLength: 0)

                HStack(spacing: 26) {
                    CallCircle(
                        symbol: app.playback.isPlaying ? "speaker.slash.fill" : "speaker.wave.2.fill",
                        label: "Stop voice"
                    ) { app.playback.stop() }

                    Button {
                        Task { await app.toggleVoiceCapture() }
                    } label: {
                        Image(systemName: app.voice.isListening ? "stop.fill" : "mic.fill")
                            .font(.system(size: 30, weight: .bold))
                            .frame(width: 76, height: 76)
                            .background(app.voice.isListening ? Color.red : MaryTheme.gradient, in: Circle())
                            .foregroundStyle(.white)
                    }

                    CallCircle(symbol: "keyboard", label: "Text") {
                        dismiss()
                        app.selectedTab = .chat
                    }
                }
                .padding(.bottom, 28)
            }
        }
        .presentationDetents([.large])
    }
}

struct CallCircle: View {
    let symbol: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: symbol)
                    .font(.title2)
                    .frame(width: 56, height: 56)
                    .background(.ultraThinMaterial, in: Circle())
                Text(label).font(.caption2)
            }
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
    }
}
