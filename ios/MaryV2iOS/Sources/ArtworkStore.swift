import SwiftUI
import UIKit

enum ArtworkStore {
    static let items: [GalleryItem] = [
        GalleryItem(title: "Portrait", baseName: "mary-reference", ext: "jpeg"),
        GalleryItem(title: "Stream Room", baseName: "mary-stream-room-reference", ext: "png"),
        GalleryItem(title: "Manga", baseName: "mary-neon-night-manga", ext: "png"),
        GalleryItem(title: "Reference", baseName: "mary-neon-reference-sheet", ext: "png")
    ]

    static func image(baseName: String, ext: String) -> UIImage? {
        if let named = UIImage(named: baseName) { return named }
        let candidates: [URL?] = [
            Bundle.main.url(forResource: baseName, withExtension: ext),
            Bundle.main.url(forResource: baseName, withExtension: ext, subdirectory: "Art"),
            Bundle.main.resourceURL?.appendingPathComponent("Art/\(baseName).\(ext)")
        ]
        for candidate in candidates {
            if let url = candidate, let data = try? Data(contentsOf: url), let image = UIImage(data: data) { return image }
        }
        return nil
    }
}

struct MaryArtworkView: View {
    let baseName: String
    let ext: String
    var contentMode: ContentMode = .fill
    var body: some View {
        Group {
            if let ui = ArtworkStore.image(baseName: baseName, ext: ext) {
                Image(uiImage: ui).resizable().aspectRatio(contentMode: contentMode)
            } else {
                ZStack {
                    LinearGradient(colors: [MaryTheme.surface2, MaryTheme.bg], startPoint: .topLeading, endPoint: .bottomTrailing)
                    VStack(spacing: 10) {
                        Image(systemName: "sparkles").font(.largeTitle).foregroundStyle(MaryTheme.pink)
                        Text("Mary").font(.headline)
                    }.foregroundStyle(.white)
                }
            }
        }
    }
}

struct MaryStageView: View {
    var height: CGFloat = 320
    var body: some View {
        ZStack(alignment: .bottomLeading) {
            MaryArtworkView(baseName: "mary-reference", ext: "jpeg", contentMode: .fill)
                .frame(maxWidth: .infinity).frame(height: height).clipped()
            LinearGradient(colors: [.clear, MaryTheme.bg.opacity(0.20), MaryTheme.bg.opacity(0.85)], startPoint: .top, endPoint: .bottom)
            HStack(spacing: 8) {
                Circle().fill(MaryTheme.green).frame(width: 8, height: 8)
                Text("MARY // LIVE PRESENCE").font(.caption2.weight(.black)).tracking(1.8)
            }
            .foregroundStyle(.white)
            .padding(14)
        }
        .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 28).stroke(MaryTheme.pink.opacity(0.25)))
    }
}
