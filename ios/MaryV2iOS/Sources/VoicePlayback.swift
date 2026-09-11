import Foundation
import AVFoundation

@MainActor
final class VoicePlayback: NSObject, ObservableObject, AVAudioPlayerDelegate {
    @Published var isPlaying = false
    @Published var provider = "Core voice"
    @Published var errorText: String?

    private var player: AVAudioPlayer?

    func play(_ audio: MaryVoiceAudio) throws {
        stop()
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
        try session.setActive(true, options: .notifyOthersOnDeactivation)
        let player = try AVAudioPlayer(data: audio.data)
        player.delegate = self
        player.prepareToPlay()
        guard player.play() else {
            throw NSError(domain: "MaryVoice", code: 20, userInfo: [NSLocalizedDescriptionKey: "Mary's voice audio could not start playback."])
        }
        self.player = player
        provider = audio.provider
        errorText = nil
        isPlaying = true
    }

    func stop() {
        player?.stop()
        player = nil
        isPlaying = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            self.player = nil
            self.isPlaying = false
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }

    nonisolated func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        Task { @MainActor in
            self.player = nil
            self.isPlaying = false
            self.errorText = error?.localizedDescription ?? "Mary's voice audio could not be decoded."
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }
}
