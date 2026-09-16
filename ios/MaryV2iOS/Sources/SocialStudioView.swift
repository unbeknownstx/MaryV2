import SwiftUI

struct SocialStudioView: View {
    @EnvironmentObject var app: AppState

    @State private var kind = "caption"
    @State private var brief = ""
    @State private var mediaSummary = ""
    @State private var tone = ""
    @State private var audienceText = ""
    @State private var editedContent = ""
    @State private var isWorking = false

    private let kinds: [(String, String)] = [
        ("caption", "Caption"),
        ("reel_script", "Reel"),
        ("reply", "Reply"),
        ("story", "Story"),
        ("bio", "Bio"),
    ]

    private var proposalID: String {
        CoreProjection.string(app.socialProposalData["id"])
    }

    private var proposalStatus: String {
        CoreProjection.string(app.socialProposalData["status"])
    }

    private var proposalContent: String {
        CoreProjection.string(app.socialProposalData["content"])
    }

    var body: some View {
        VStack(spacing: 14) {
            GlassCard {
                VStack(alignment: .leading, spacing: 12) {
                    Eyebrow(text: "Mary authors it")
                    Text("Give Mary the scene and intent. She writes the public line through the same canonical character runtime used by chat.")
                        .font(.subheadline)
                        .foregroundStyle(MaryTheme.muted)

                    Picker("Format", selection: $kind) {
                        ForEach(kinds, id: \.0) { value, label in
                            Text(label).tag(value)
                        }
                    }
                    .pickerStyle(.segmented)

                    TextField("What should Mary react to or communicate?", text: $brief, axis: .vertical)
                        .lineLimit(2...5)
                        .padding(12)
                        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))

                    TextField("What is in the image/video or scene?", text: $mediaSummary, axis: .vertical)
                        .lineLimit(2...5)
                        .padding(12)
                        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))

                    TextField("Optional tone — e.g. sarcastic but warm", text: $tone)
                        .padding(12)
                        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))

                    if kind == "reply" {
                        TextField("Comment/message Mary is replying to", text: $audienceText, axis: .vertical)
                            .lineLimit(2...5)
                            .padding(12)
                            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))
                    }

                    Button {
                        Task { await createDraft() }
                    } label: {
                        HStack {
                            if isWorking { ProgressView().tint(.white) }
                            Text(isWorking ? "Mary is writing…" : "Ask Mary")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(MaryPrimaryButtonStyle())
                    .disabled(isWorking || brief.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }

            if !app.socialProposalData.isEmpty {
                proposalCard
            } else {
                GlassCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Eyebrow(text: "Review queue")
                        Text("Nothing waiting for review").font(.headline)
                        Text("Mary never publishes from this screen automatically. You approve or reject every proposed artifact first.")
                            .font(.caption)
                            .foregroundStyle(MaryTheme.muted)
                    }
                }
            }
        }
    }

    private var proposalCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Eyebrow(text: "Mary's draft")
                    Spacer()
                    StatusPill(text: proposalStatus.isEmpty ? "Proposed" : proposalStatus.capitalized, online: proposalStatus == "approved")
                }

                TextEditor(text: $editedContent)
                    .frame(minHeight: 150)
                    .padding(8)
                    .scrollContentBackground(.hidden)
                    .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))

                if proposalStatus == "proposed" {
                    HStack(spacing: 10) {
                        Button("Reject") {
                            Task {
                                isWorking = true
                                _ = await app.rejectSocial(proposalID: proposalID)
                                isWorking = false
                            }
                        }
                        .buttonStyle(.bordered)

                        Button("Approve") {
                            Task {
                                isWorking = true
                                _ = await app.approveSocial(
                                    proposalID: proposalID,
                                    editedContent: editedContent
                                )
                                isWorking = false
                            }
                        }
                        .buttonStyle(MaryPrimaryButtonStyle())
                    }
                }

                Button {
                    Task { await app.speakSocialProposal() }
                } label: {
                    Label("Hear Mary perform it", systemImage: "waveform")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .disabled(proposalContent.isEmpty || !app.voiceServerAvailable)

                Text("Voice uses the proposal's delivery plan so Mary's timing and emotional weight can carry into the rendered audio.")
                    .font(.caption)
                    .foregroundStyle(MaryTheme.muted)
            }
        }
        .onChange(of: proposalContent) { newValue in
            editedContent = newValue
        }
    }

    private func createDraft() async {
        isWorking = true
        let success = await app.proposeSocial(
            kind: kind,
            brief: brief,
            mediaSummary: mediaSummary,
            tone: tone,
            audienceText: audienceText
        )
        if success {
            editedContent = CoreProjection.string(app.socialProposalData["content"])
        }
        isWorking = false
    }
}
