import UIKit
import WebKit

final class MaryViewController: UIViewController, WKNavigationDelegate {
    private var webView: WKWebView!
    private var nativeBridge: MaryNativeBridge!

    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.02, green: 0.024, blue: 0.067, alpha: 1)

        let contentController = WKUserContentController()
        let configuration = WKWebViewConfiguration()
        configuration.userContentController = contentController
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false

        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.isOpaque = false
        webView.backgroundColor = view.backgroundColor
        webView.scrollView.backgroundColor = view.backgroundColor
        webView.scrollView.bounces = false
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = false

        nativeBridge = MaryNativeBridge(webView: webView)
        contentController.add(nativeBridge, name: MaryNativeBridge.handlerName)

        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webView.topAnchor.constraint(equalTo: view.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        guard
            let wwwURL = Bundle.main.url(forResource: "www", withExtension: nil),
            let indexURL = Bundle.main.url(forResource: "index", withExtension: "html", subdirectory: "www")
        else {
            showFatal("Mary's bundled mobile interface could not be found.")
            return
        }
        webView.loadFileURL(indexURL, allowingReadAccessTo: wwwURL)
    }

    deinit {
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: MaryNativeBridge.handlerName)
        nativeBridge?.shutdown()
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if navigationAction.navigationType == .linkActivated,
           let scheme = url.scheme?.lowercased(),
           scheme == "http" || scheme == "https" {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    private func showFatal(_ message: String) {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = message
        label.textColor = .white
        label.numberOfLines = 0
        label.textAlignment = .center
        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            label.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
            label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
        ])
    }
}
