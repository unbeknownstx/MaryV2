import AVFoundation
import Speech
import UIKit
import WebKit

final class MaryNativeBridge: NSObject, WKScriptMessageHandler, AVSpeechSynthesizerDelegate {
    static let handlerName = "maryNative"

    private weak var webView: WKWebView?
    private let synthesizer = AVSpeechSynthesizer()
    private let audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var speechRecognizer: SFSpeechRecognizer?
    private var listening = false

    init(webView: WKWebView) {
        self.webView = webView
        super.init()
        synthesizer.delegate = self
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == Self.handlerName,
              let body = message.body as? [String: Any],
              let method = body["method"] as? String else { return }

        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            switch method {
            case "ready":
                self.emit(["type": "nativeReady", "platform": "ios"])
            case "haptic":
                self.haptic(style: body["style"] as? String ?? "light")
            case "speak":
                self.speak(text: body["text"] as? String ?? "", webRate: body["rate"] as? Double ?? 1.0)
            case "stopSpeaking":
                self.synthesizer.stopSpeaking(at: .immediate)
            case "startListening":
                self.startListening(locale: body["locale"] as? String)
            case "stopListening":
                self.stopListening()
            case "openURL":
                if let value = body["url"] as? String, let url = URL(string: value), ["http", "https"].contains(url.scheme?.lowercased() ?? "") {
                    UIApplication.shared.open(url)
                }
            default:
                break
            }
        }
    }

    func shutdown() {
        stopListening()
        synthesizer.stopSpeaking(at: .immediate)
    }

    func emitLifecycle(_ type: String) {
        emit(["type": type])
    }

    private func haptic(style: String) {
        switch style.lowercased() {
        case "success":
            let generator = UINotificationFeedbackGenerator()
            generator.prepare()
            generator.notificationOccurred(.success)
        case "warning":
            let generator = UINotificationFeedbackGenerator()
            generator.prepare()
            generator.notificationOccurred(.warning)
        case "error":
            let generator = UINotificationFeedbackGenerator()
            generator.prepare()
            generator.notificationOccurred(.error)
        case "medium":
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.prepare()
            generator.impactOccurred()
        default:
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.prepare()
            generator.impactOccurred()
        }
    }

    private func speak(text: String, webRate: Double) {
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return }
        if synthesizer.isSpeaking { synthesizer.stopSpeaking(at: .immediate) }
        let utterance = AVSpeechUtterance(string: value)
        let normalized = min(1.35, max(0.75, webRate))
        let factor = (normalized - 0.75) / 0.60
        utterance.rate = Float(0.40 + factor * 0.16)
        utterance.pitchMultiplier = 1.02
        utterance.volume = 1.0
        if let preferred = AVSpeechSynthesisVoice(language: Locale.preferredLanguages.first ?? "en-US") {
            utterance.voice = preferred
        }
        synthesizer.speak(utterance)
    }

    private func startListening(locale: String?) {
        if listening {
            stopListening()
            return
        }
        SFSpeechRecognizer.requestAuthorization { [weak self] speechStatus in
            DispatchQueue.main.async {
                guard let self else { return }
                guard speechStatus == .authorized else {
                    self.emit(["type": "speechError", "message": "Speech recognition permission was not granted."])
                    return
                }
                AVAudioSession.sharedInstance().requestRecordPermission { granted in
                    DispatchQueue.main.async {
                        guard granted else {
                            self.emit(["type": "speechError", "message": "Microphone permission was not granted."])
                            return
                        }
                        self.beginRecognition(locale: locale)
                    }
                }
            }
        }
    }

    private func beginRecognition(locale: String?) {
        stopListening(emitState: false)
        let identifier = (locale?.isEmpty == false ? locale! : (Locale.preferredLanguages.first ?? "en-US"))
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: identifier))
        guard let speechRecognizer, speechRecognizer.isAvailable else {
            emit(["type": "speechError", "message": "Speech recognition is unavailable right now."])
            return
        }

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        recognitionRequest = request

        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .spokenAudio, options: [.defaultToSpeaker, .allowBluetooth])
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            let input = audioEngine.inputNode
            let format = input.outputFormat(forBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak request] buffer, _ in
                request?.append(buffer)
            }
            audioEngine.prepare()
            try audioEngine.start()
        } catch {
            emit(["type": "speechError", "message": "Microphone could not start: \(error.localizedDescription)"])
            stopListening(emitState: false)
            return
        }

        listening = true
        emit(["type": "listening", "active": true])
        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let result {
                let text = result.bestTranscription.formattedString
                if result.isFinal {
                    DispatchQueue.main.async {
                        self.emit(["type": "speechResult", "text": text])
                        self.stopListening()
                    }
                    return
                }
            }
            if let error {
                DispatchQueue.main.async {
                    self.emit(["type": "speechError", "message": error.localizedDescription])
                    self.stopListening()
                }
            }
        }
    }

    private func stopListening(emitState: Bool = true) {
        if audioEngine.isRunning { audioEngine.stop() }
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        speechRecognizer = nil
        listening = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        if emitState { emit(["type": "listening", "active": false]) }
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didStart utterance: AVSpeechUtterance) {
        emit(["type": "speaking", "active": true])
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        emit(["type": "speaking", "active": false])
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        emit(["type": "speaking", "active": false])
    }

    private func emit(_ detail: [String: Any]) {
        guard JSONSerialization.isValidJSONObject(detail),
              let data = try? JSONSerialization.data(withJSONObject: detail),
              let json = String(data: data, encoding: .utf8) else { return }
        let script = "window.dispatchEvent(new CustomEvent('marynative',{detail:\(json)}));"
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(script, completionHandler: nil)
        }
    }
}
