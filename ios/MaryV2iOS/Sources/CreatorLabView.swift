import PhotosUI
import SwiftUI

/// Native creative intake for the same canonical Mary.
/// Photos remain local until an explicit Core asset-upload transport is available.
struct CreatorLabView: View {
    @EnvironmentObject var app: AppState
    @State private var pickerItem: PhotosPickerItem?
    @State private var imageData: Data?
    @State private var sceneSummary = ""
    @State private var intent = "Tell me what you'd say about this in your own voice."
    @State private var tone = "natural"
    @State private var working = false

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                Eyebrow(text: "Creator Lab")
                Text("Make something with Mary").font(.title2.bold())
                Text("Choose an image, ground what Mary is looking at, then let the same Mary who chats with you author the caption or narration. Voice and video can build from the same artifact.")
                    .font(.caption).foregroundStyle(MaryTheme.muted)

                PhotosPicker(selection: $pickerItem, matching: .images) {
                    Label(imageData == nil ? "Choose image" : "Change image", systemImage: "photo.badge.plus")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(MaryPrimaryButtonStyle())
                .onChange(of: pickerItem) { item in
                    Task { imageData = try? await item?.loadTransferable(type: Data.self) }
                }

                if let imageData, let image = UIImage(data: imageData) {
                    Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 280)
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 18).stroke(MaryTheme.hairline))
                }

                TextField("What Mary sees (you can edit this)", text: $sceneSummary, axis: .vertical)
                    .lineLimit(2...5).padding(12)
                    .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                TextField("What should Mary do with it?", text: $intent, axis: .vertical)
                    .lineLimit(2...5).padding(12)
                    .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                TextField("Tone", text: $tone).padding(12)
                    .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))

                if imageData != nil {
                    Button {
                        guard let imageData else { return }
                        working = true
                        Task {
                            if let description = await app.describeCreatorImage(imageData) {
                                sceneSummary = description
                            }
                            working = false
                        }
                    } label: {
                        Label("Let Mary look at the image", systemImage: "eye.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(MarySecondaryButtonStyle())
                    .disabled(working)
                }

                Button {
                    working = true
                    Task {
                        var grounded = sceneSummary.trimmingCharacters(in: .whitespacesAndNewlines)
                        if grounded.isEmpty, let imageData {
                            grounded = await app.describeCreatorImage(imageData) ?? ""
                            if !grounded.isEmpty { sceneSummary = grounded }
                        }
                        if !grounded.isEmpty {
                            _ = await app.proposeSocial(
                                kind: "caption",
                                brief: intent,
                                mediaSummary: grounded,
                                tone: tone
                            )
                        }
                        working = false
                    }
                } label: {
                    Label(working ? "Mary is creating…" : "Create with Mary", systemImage: "sparkles")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(MaryPrimaryButtonStyle())
                .disabled(working || (imageData == nil && sceneSummary.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty))

                if !app.socialProposalData.isEmpty {
                    let text = CoreProjection.string(app.socialProposalData["content"])
                    if !text.isEmpty {
                        Divider().overlay(MaryTheme.hairline)
                        Eyebrow(text: "Mary's draft")
                        Text(text).textSelection(.enabled)
                        Button { Task { await app.speakMaryResponse(text) } } label: {
                            Label("Hear Mary say it", systemImage: "speaker.wave.2.fill")
                        }
                        .buttonStyle(MarySecondaryButtonStyle())
                    }
                }

                Text("A picked image is compressed on-device and sent only after you explicitly ask Mary to look or create. Raw pixels are ephemeral task input; Core retains bounded asset metadata and the grounded visual description, not the image bytes.")
                    .font(.caption2).foregroundStyle(MaryTheme.muted)
            }
        }
    }
}
