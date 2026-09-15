import SwiftUI
import UIKit

enum MaryAsset: String, CaseIterable, Identifiable {
    case portrait
    case streamRoom
    case manga
    case reference

    var id: String { rawValue }
    var title: String {
        switch self {
        case .portrait: return "Portrait"
        case .streamRoom: return "Stream Room"
        case .manga: return "Manga"
        case .reference: return "Reference"
        }
    }

    var candidates: [(String, String)] {
        switch self {
        case .portrait:
            return [
                ("mary-reference", "jpeg"),
                ("mary-neon-reference-sheet", "png"),
            ]
        case .streamRoom:
            return [("mary-stream-room-reference", "png")]
        case .manga:
            return [("mary-neon-night-manga", "png")]
        case .reference:
            return [
                ("mary-neon-reference-sheet", "png"),
                ("mary-reference", "jpeg"),
            ]
        }
    }
}

enum MaryAssetLibrary {
    static func image(_ asset: MaryAsset) -> UIImage? {
        for (name, ext) in asset.candidates {
            if let named = UIImage(named: name) { return named }
            if let url = Bundle.main.url(forResource: name, withExtension: ext),
               let image = UIImage(contentsOfFile: url.path) {
                return image
            }
        }

        // Xcode may preserve resource subdirectories differently depending on
        // how the project was generated. The fallback is intentionally read
        // only and searches only the app bundle.
        if let enumerator = FileManager.default.enumerator(
            at: Bundle.main.bundleURL,
            includingPropertiesForKeys: nil
        ) {
            let wanted = Set(asset.candidates.map { "\($0.0).\($0.1)" })
            for case let url as URL in enumerator where wanted.contains(url.lastPathComponent) {
                if let image = UIImage(contentsOfFile: url.path) { return image }
            }
        }
        return nil
    }
}

struct MaryArtwork: View {
    let asset: MaryAsset
    var contentMode: ContentMode = .fill

    var body: some View {
        Group {
            if let image = MaryAssetLibrary.image(asset) {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: contentMode)
            } else {
                ZStack {
                    MaryTheme.panel2
                    VStack(spacing: 8) {
                        Image(systemName: "photo.badge.exclamationmark")
                            .font(.title)
                            .foregroundStyle(MaryTheme.pink)
                        Text("Mary artwork unavailable")
                            .font(.caption)
                            .foregroundStyle(MaryTheme.muted)
                    }
                }
            }
        }
    }
}
