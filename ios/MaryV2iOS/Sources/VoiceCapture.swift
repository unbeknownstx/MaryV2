import Foundation
import AVFoundation
import Speech

@MainActor
final class VoiceCapture: ObservableObject {
    @Published var isListening = false
    @Published var transcript = ""
    @Published var errorText: String?
    private var recorder: AVAudioRecorder?
    private var recordingURL: URL?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))

    func start() async {
        let speech = await withCheckedContinuation { c in SFSpeechRecognizer.requestAuthorization { c.resume(returning: $0 == .authorized) } }
        let mic = await withCheckedContinuation { c in AVAudioSession.sharedInstance().requestRecordPermission { c.resume(returning: $0) } }
        guard speech && mic else { errorText = "Microphone and speech recognition access are required."; return }
        guard let recognizer, recognizer.isAvailable, recognizer.supportsOnDeviceRecognition else { errorText = "On-device speech recognition is unavailable."; return }
        do {
            let s = AVAudioSession.sharedInstance(); try s.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .allowBluetoothHFP]); try s.setActive(true)
            let u = FileManager.default.temporaryDirectory.appendingPathComponent("mary-\(UUID().uuidString).m4a")
            let settings: [String: Any] = [AVFormatIDKey: Int(kAudioFormatMPEG4AAC), AVSampleRateKey: 16000, AVNumberOfChannelsKey: 1, AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue]
            let r = try AVAudioRecorder(url: u, settings: settings); r.prepareToRecord(); guard r.record() else { throw NSError(domain: "MaryVoice", code: 1) }
            recorder = r; recordingURL = u; transcript = ""; isListening = true; errorText = nil
        } catch { errorText = error.localizedDescription }
    }
    func stopAndTranscribe() async -> String? {
        guard isListening, let u = recordingURL else { return nil }; recorder?.stop(); recorder = nil; isListening = false
        defer { try? FileManager.default.removeItem(at: u); recordingURL = nil; try? AVAudioSession.sharedInstance().setActive(false) }
        guard let recognizer else { return nil }
        do {
            let text: String = try await withCheckedThrowingContinuation { c in
                let req = SFSpeechURLRecognitionRequest(url: u); req.requiresOnDeviceRecognition = true; req.shouldReportPartialResults = false
                recognitionTask = recognizer.recognitionTask(with: req) { result, error in
                    if let result, result.isFinal { c.resume(returning: result.bestTranscription.formattedString) }
                    else if let error { c.resume(throwing: error) }
                }
            }
            transcript = text; return text
        } catch { errorText = error.localizedDescription; return nil }
    }
    func cancel() { recorder?.stop(); recognitionTask?.cancel(); isListening = false }
}
