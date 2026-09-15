import SwiftUI

struct VoiceCallView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            MaryBackground()

            MaryArtwork(asset: .portrait, contentMode: .fill)
                .ignoresSafeArea()
                .blur(radius: 24)
                .opacity(0.20)
                .overlay(MaryTheme.bg.opacity(0.72).ignoresSafeArea())

            VStack(spacing: 18) {
                header

                Spacer(minLength: 0)

                portrait

                VStack(spacing: 6) {
                    Text("Mary")
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                    HStack(spacing: 6) {
                        Image(systemName: app.relationship.symbol)
                            .foregroundStyle(MaryTheme.pink2)
                        Text(app.relationship.title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(MaryTheme.muted)
                    }
                    Text(callSubtitle)
                        .font(.caption)
                        .foregroundStyle(MaryTheme.muted2)
                }

                if app.voice.isListening || app.voice.isTranscribing || !app.voice.transcript.isEmpty {
                    transcriptCard
                }

                Spacer(minLength: 0)
                controls
            }
            .padding(.top, 10)
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.hidden)
    }

    private var header: some View {
        HStack {
            Button {
                app.playback.stop()
                app.voice.cancel()
                dismiss()
            } label: {
                Image(systemName: "chevron.down")
                    .font(.title3.bold())
                    .frame(width: MaryTheme.minimumTouchTarget, height: MaryTheme.minimumTouchTarget)
                    .background(.ultraThinMaterial, in: Circle())
                    .overlay(Circle().stroke(MaryTheme.hairline))
            }
            .accessibilityLabel("Close call")

            Spacer()

            VStack(spacing: 1) {
                Text("MARY CALL")
                    .font(.system(size: 10, weight: .black))
                    .tracking(1.7)
                    .foregroundStyle(MaryTheme.pink2)
                Text(app.performanceMode.isPublic ? "Public-safe" : "Private")
                    .font(.caption2)
                    .foregroundStyle(MaryTheme.muted)
            }

            Spacer()

            StatusPill(text: app.phase.label, online: app.isConnected)
        }
        .padding(.horizontal, 18)
    }

    private var portrait: some View {
        ZStack {
            Circle()
                .stroke(MaryTheme.pink.opacity(0.12), lineWidth: 1)
                .frame(width: 286, height: 286)
            Circle()
                .stroke(MaryTheme.cyan.opacity(0.08), lineWidth: 1)
                .frame(width: 244, height: 244)

            MaryArtwork(asset: .portrait, contentMode: .fill)
                .frame(width: 230, height: 300)
                .clipped()
                .clipShape(RoundedRectangle(cornerRadius: 38, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 38, style: .continuous)
                        .stroke(MaryTheme.pink.opacity(app.playback.isPlaying ? 0.48 : 0.22), lineWidth: app.playback.isPlaying ? 2 : 1)
                )
                .shadow(color: MaryTheme.violet.opacity(0.26), radius: 36)
        }
        .frame(height: 315)
    }

    private var transcriptCard: some View {
        HStack(spacing: 10) {
            Image(systemName: app.voice.isListening ? "waveform" : "quote.bubble.fill")
                .foregroundStyle(app.voice.isListening ? MaryTheme.pink2 : MaryTheme.cyan)
            Text(transcriptText)
                .font(.subheadline)
                .foregroundStyle(.white)
                .lineLimit(3)
            Spacer()
        }
        .padding(14)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(MaryTheme.hairline))
        .padding(.horizontal, 24)
    }

    private var controls: some View {
        HStack(spacing: 28) {
            CallCircle(
                symbol: app.playback.isPlaying ? "speaker.slash.fill" : "speaker.wave.2.fill",
                label: app.playback.isPlaying ? "Stop" : "Speaker"
            ) { app.playback.stop() }

            Button {
                Task { await app.toggleVoiceCapture() }
            } label: {
                ZStack {
                    Circle()
                        .fill(app.voice.isListening ? Color.red.opacity(0.92) : MaryTheme.pink)
                        .frame(width: 82, height: 82)
                        .shadow(color: (app.voice.isListening ? Color.red : MaryTheme.pink).opacity(0.28), radius: 22)
                    Image(systemName: app.voice.isListening ? "stop.fill" : "mic.fill")
                        .font(.system(size: 30, weight: .bold))
                        .foregroundStyle(.white)
                }
            }
            .accessibilityLabel(app.voice.isListening ? "Stop listening and send" : "Talk to Mary")

            CallCircle(symbol: "keyboard", label: "Text") {
                dismiss()
                app.selectedTab = .chat
            }
        }
        .padding(.bottom, 30)
    }

    private var callSubtitle: String {
        if !app.voiceServerAvailable { return "Voice unavailable · text still works" }
        if app.playback.isPlaying { return "Mary is speaking" }
        if app.voice.isListening { return "Listening to you" }
        if app.voice.isTranscribing { return "Transcribing on iPhone" }
        return "\(app.voiceProvider.capitalized) · tap the mic when you want to talk"
    }

    private var transcriptText: String {
        if app.voice.isListening && app.voice.transcript.isEmpty { return "Listening… tap the mic again when you're finished." }
        if app.voice.isTranscribing { return "Turning your speech into text on this iPhone…" }
        return app.voice.transcript.isEmpty ? "Ready" : app.voice.transcript
    }
}

struct CallCircle: View {
    let symbol: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 7) {
                Image(systemName: symbol)
                    .font(.title2)
                    .frame(width: 58, height: 58)
                    .background(.ultraThinMaterial, in: Circle())
                    .overlay(Circle().stroke(MaryTheme.hairline))
                Text(label)
                    .font(.caption2.weight(.semibold))
            }
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
    }
}
