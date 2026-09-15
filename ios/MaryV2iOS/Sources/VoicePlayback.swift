import Foundation
import AVFoundation

@MainActor
final class VoicePlayback: NSObject, ObservableObject, AVAudioPlayerDelegate {
    @Published var isPlaying = false
    private var player: AVAudioPlayer?
    func play(_ audio: MaryVoiceAudio) throws {
        stop(); let s = AVAudioSession.sharedInstance(); try s.setCategory(.playback, mode: .spokenAudio, options: [.duckOthers]); try s.setActive(true, options: .notifyOthersOnDeactivation)
        let p = try AVAudioPlayer(data: audio.data); p.delegate = self; p.prepareToPlay(); guard p.play() else { throw MaryClientError.emptyVoiceAudio }; player = p; isPlaying = true
    }
    func stop() { player?.stop(); player = nil; isPlaying = false; try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) }
    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) { Task { @MainActor in self.player = nil; self.isPlaying = false } }
}
