import Foundation
import AVFoundation
import Speech

@MainActor
final class VoiceCapture: ObservableObject {
    @Published var isListening = false
    @Published var isTranscribing = false
    @Published var transcript = ""
    @Published var errorText: String?

    private var recorder: AVAudioRecorder?
    private var recordingURL: URL?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))

    func requestPermissions() async -> Bool {
        let speechOK = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
        let micOK = await withCheckedContinuation { continuation in
            AVAudioSession.sharedInstance().requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
        if !speechOK { errorText = "Speech recognition permission is required." }
        if !micOK { errorText = "Microphone permission is required." }
        return speechOK && micOK
    }

    func start() async {
        guard !isListening && !isTranscribing else { return }
        guard await requestPermissions() else { return }
        guard let recognizer, recognizer.isAvailable else {
            errorText = "On-device speech recognition is unavailable right now."
            return
        }
        guard recognizer.supportsOnDeviceRecognition else {
            errorText = "This iPhone does not currently support on-device transcription."
            return
        }

        recognitionTask?.cancel()
        recognitionTask = nil
        transcript = ""
        errorText = nil

        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .allowBluetooth])
            try session.setActive(true, options: .notifyOthersOnDeactivation)

            let url = FileManager.default.temporaryDirectory
                .appendingPathComponent("mary-ios-\(UUID().uuidString).m4a")
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 16_000,
                AVNumberOfChannelsKey: 1,
                AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
                AVEncoderBitRateKey: 64_000
            ]
            let recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder.prepareToRecord()
            guard recorder.record() else {
                throw NSError(domain: "MaryVoice", code: 1, userInfo: [NSLocalizedDescriptionKey: "The microphone did not start recording."])
            }
            self.recorder = recorder
            recordingURL = url
            isListening = true
        } catch {
            errorText = error.localizedDescription
            cleanupRecording(deleteFile: true)
        }
    }

    func stopAndTranscribe() async -> String? {
        guard isListening, let url = recordingURL else { return nil }
        recorder?.stop()
        recorder = nil
        isListening = false
        isTranscribing = true

        defer {
            isTranscribing = false
            try? FileManager.default.removeItem(at: url)
            recordingURL = nil
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }

        do {
            let text = try await transcribeLocalFile(url)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else {
                errorText = "No speech was detected."
                return nil
            }
            transcript = text
            errorText = nil
            return text
        } catch {
            errorText = error.localizedDescription
            return nil
        }
    }

    func cancel() {
        recognitionTask?.cancel()
        recognitionTask = nil
        recorder?.stop()
        recorder = nil
        isListening = false
        isTranscribing = false
        cleanupRecording(deleteFile: true)
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    private func transcribeLocalFile(_ url: URL) async throws -> String {
        guard let recognizer, recognizer.isAvailable else {
            throw NSError(domain: "MaryVoice", code: 2, userInfo: [NSLocalizedDescriptionKey: "Speech recognition is unavailable."])
        }
        guard recognizer.supportsOnDeviceRecognition else {
            throw NSError(domain: "MaryVoice", code: 3, userInfo: [NSLocalizedDescriptionKey: "On-device speech recognition is unavailable."])
        }

        return try await withCheckedThrowingContinuation { continuation in
            let request = SFSpeechURLRecognitionRequest(url: url)
            request.requiresOnDeviceRecognition = true
            request.shouldReportPartialResults = false
            var finished = false

            recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
                guard !finished else { return }
                if let result, result.isFinal {
                    finished = true
                    self?.recognitionTask = nil
                    continuation.resume(returning: result.bestTranscription.formattedString)
                    return
                }
                if let error {
                    finished = true
                    self?.recognitionTask = nil
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    private func cleanupRecording(deleteFile: Bool) {
        if deleteFile, let recordingURL {
            try? FileManager.default.removeItem(at: recordingURL)
        }
        recordingURL = nil
    }
}
