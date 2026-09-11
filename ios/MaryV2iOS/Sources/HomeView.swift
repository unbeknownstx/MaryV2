import SwiftUI

struct HomeView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                MaryPanel {
                    HStack(spacing: 14) {
                        Circle()
                            .fill(MaryTheme.accent)
                            .frame(width: 64, height: 64)
                            .overlay(Image(systemName: "sparkles").font(.title2).foregroundStyle(.white))

                        VStack(alignment: .leading, spacing: 4) {
                            Text("Mary").font(.title2.bold())
                            Text(app.isConnected ? "Canonical continuity online" : "Waiting for Core")
                                .font(.subheadline)
                                .foregroundStyle(MaryTheme.muted)
                            Text("\(app.coreLabel) · \(app.coreVersion)")
                                .font(.caption2)
                                .foregroundStyle(MaryTheme.muted)
                        }

                        Spacer()

                        Circle()
                            .fill(app.isConnected ? MaryTheme.green : Color.red)
                            .frame(width: 10, height: 10)
                    }
                }

                MaryPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            TinyCaps(text: "SOCIAL STAGE")
                            Spacer()
                            Text(app.performanceMode.title.uppercased())
                                .font(.caption2.bold())
                                .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                        }

                        ForEach(PerformanceMode.allCases) { mode in
                            Button {
                                Task { await app.changePerformanceMode(mode) }
                            } label: {
                                HStack {
                                    Label(mode.title, systemImage: mode.symbol)
                                        .font(.body.weight(.semibold))
                                    Spacer()
                                    if app.performanceMode == mode {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(mode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                                    }
                                }
                                .padding(.vertical, 5)
                            }
                            .buttonStyle(.plain)
                        }

                        Label(
                            app.performanceMode.isPublic ? "Public privacy guard active" : "Private creator context",
                            systemImage: app.performanceMode.isPublic ? "lock.shield.fill" : "person.crop.circle.badge.checkmark"
                        )
                        .font(.caption)
                        .foregroundStyle(app.performanceMode.isPublic ? MaryTheme.pink2 : MaryTheme.cyan)
                    }
                }

                MaryPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        TinyCaps(text: "THIS SURFACE")
                        DataRow(label: "Conversation", value: app.conversationID)
                        DataRow(label: "Surface", value: "Native iPhone")
                        DataRow(label: "Mode", value: app.conversationMode.rawValue)
                        DataRow(label: "Device", value: String(app.deviceID.prefix(18)))
                    }
                }

                Button {
                    Task { await app.refreshHome() }
                } label: {
                    Label("Refresh Mary status", systemImage: "arrow.clockwise")
                        .frame(maxWidth: .infinity)
                        .frame(height: 46)
                }
                .buttonStyle(.borderedProminent)
                .tint(MaryTheme.violet)
            }
            .padding(13)
        }
        .refreshable { await app.refreshHome() }
    }
}

struct DataRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .top) {
            Text(label)
                .font(.caption)
                .foregroundStyle(MaryTheme.muted)
            Spacer()
            Text(value)
                .font(.caption.weight(.semibold))
                .multilineTextAlignment(.trailing)
        }
        .padding(.vertical, 3)
    }
}
