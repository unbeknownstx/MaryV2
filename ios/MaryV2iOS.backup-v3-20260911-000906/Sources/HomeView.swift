import SwiftUI

struct HomeView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                MaryPanel {
                    HStack(spacing: 14) {
                        Circle()
                            .fill(MaryTheme.accentGradient)
                            .frame(width: 68, height: 68)
                            .overlay(Image(systemName: "sparkles").font(.title).foregroundStyle(.white))

                        VStack(alignment: .leading, spacing: 5) {
                            Text("Mary").font(.title2.bold())
                            Text(app.isConnected ? "Canonical continuity online" : "Waiting for Core")
                                .font(.subheadline)
                                .foregroundStyle(MaryTheme.muted)
                            HStack(spacing: 6) {
                                Circle().fill(app.isConnected ? MaryTheme.green : Color.red).frame(width: 7, height: 7)
                                Text("\(app.coreLabel) · \(app.coreVersion)")
                                    .font(.caption2)
                                    .foregroundStyle(MaryTheme.muted)
                            }
                        }
                        Spacer()
                    }
                }

                MaryPanel {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("SOCIAL STAGE")
                            .font(.caption2.weight(.black))
                            .tracking(1.8)
                            .foregroundStyle(MaryTheme.pink2)

                        Text("Switch Mary's current presentation mode just like the PWA.")
                            .font(.subheadline)
                            .foregroundStyle(MaryTheme.muted)

                        ForEach(PerformanceMode.allCases) { mode in
                            Button {
                                Task { await app.changePerformanceMode(mode) }
                            } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(mode.title).font(.body.weight(.semibold))
                                        Text(mode.subtitle).font(.caption).foregroundStyle(MaryTheme.muted)
                                    }
                                    Spacer()
                                    if app.performanceMode == mode {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(mode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                                    }
                                }
                                .padding(.vertical, 6)
                            }
                            .buttonStyle(.plain)
                        }

                        Label(
                            app.performanceMode.isPublic ? "Public privacy guard active" : "Private creator context",
                            systemImage: app.performanceMode.isPublic ? "lock.shield.fill" : "person.crop.circle.badge.checkmark"
                        )
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                    }
                }

                MaryPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("CONTINUITY")
                            .font(.caption2.weight(.black))
                            .tracking(1.8)
                            .foregroundStyle(MaryTheme.pink2)
                        DataRow(label: "Conversation", value: app.conversationID)
                        DataRow(label: "Surface", value: "Native iPhone")
                        DataRow(label: "Conversation mode", value: app.conversationMode.rawValue)
                    }
                }
            }
            .padding(13)
        }
    }
}

struct DataRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label).font(.caption).foregroundStyle(MaryTheme.muted)
            Spacer()
            Text(value).font(.caption.weight(.semibold)).multilineTextAlignment(.trailing)
        }
        .padding(.vertical, 4)
    }
}
