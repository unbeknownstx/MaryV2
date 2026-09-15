import SwiftUI
import UIKit

/// Local presentation-only artwork used whenever this surface does not have a
/// live VRM renderer. These images never become identity/memory authority.
struct MaryStageArtwork: View {
    @State private var selection = 0

    private let artwork: [(name: String, ext: String, label: String, position: Alignment)] = [
        ("mary-reference", "jpeg", "Portrait", .center),
        ("mary-stream-room-reference", "png", "Stream Room", .center),
        ("mary-neon-night-manga", "png", "Manga", .center),
        ("mary-neon-reference-sheet", "png", "Reference", .center),
    ]

    var height: CGFloat

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            TabView(selection: $selection) {
                ForEach(Array(artwork.enumerated()), id: \.offset) { index, item in
                    if let image = load(item.name, ext: item.ext) {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFill()
                            .frame(maxWidth: .infinity)
                            .frame(height: height)
                            .clipped()
                            .tag(index)
                            .accessibilityLabel("Mary \(item.label) artwork")
                    }
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))

            LinearGradient(
                colors: [.clear, MaryTheme.bg.opacity(0.06), MaryTheme.bg.opacity(0.92)],
                startPoint: .center,
                endPoint: .bottom
            )
            .allowsHitTesting(false)

            if artwork.count > 1 {
                HStack(spacing: 4) {
                    Image(systemName: "photo.stack.fill")
                    Text("ART \(selection + 1)/\(artwork.count)")
                }
                .font(.system(size: 7, weight: .black))
                .tracking(0.8)
                .foregroundStyle(MaryTheme.pink2)
                .padding(.horizontal, 8)
                .padding(.vertical, 5)
                .background(.black.opacity(0.58), in: Capsule())
                .overlay(Capsule().stroke(MaryTheme.line))
                .padding(8)
            }
        }
    }

    private func load(_ name: String, ext: String) -> UIImage? {
        guard let path = Bundle.main.path(forResource: name, ofType: ext) else { return nil }
        return UIImage(contentsOfFile: path)
    }
}
