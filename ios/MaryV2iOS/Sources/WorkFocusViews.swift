import SwiftUI

struct WorkView: View {
    @EnvironmentObject var app: AppState
    let navigate: (WorkspaceKind) -> Void
    @State private var newItem = ""
    @State private var kind = "task"

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 5) {
                    Eyebrow(text: "Shared work")
                    Text("Work with Mary").font(.largeTitle.bold())
                    Text("Capture tasks, study, research, and creative work in the same canonical workspace.")
                        .foregroundStyle(MaryTheme.muted)
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        TextField("Add something to work on…", text: $newItem)
                            .padding(12)
                            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))

                        Picker("Type", selection: $kind) {
                            Text("Task").tag("task")
                            Text("Project").tag("project")
                            Text("Note").tag("note")
                        }
                        .pickerStyle(.segmented)

                        Button {
                            Task {
                                if await app.runWorkspaceAction(
                                    "command.add",
                                    args: [
                                        "title": newItem,
                                        "kind": kind,
                                        "priority": 2,
                                        "notes": "",
                                    ]
                                ) {
                                    newItem = ""
                                }
                            }
                        } label: {
                            Label("Add to shared work", systemImage: "plus.circle.fill")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(MaryPrimaryButtonStyle())
                        .disabled(newItem.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }

                if !app.snapshot.currentProject.isEmpty {
                    GlassCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Eyebrow(text: "Current")
                            Text(app.snapshot.currentProject).font(.title2.bold())
                            if !app.snapshot.currentSummary.isEmpty {
                                Text(app.snapshot.currentSummary)
                                    .foregroundStyle(MaryTheme.muted)
                            }
                        }
                    }
                }

                Text("Spaces").font(.title3.bold())
                HStack(spacing: 10) {
                    workspaceButton(.study)
                    workspaceButton(.research)
                }
                HStack(spacing: 10) {
                    workspaceButton(.search)
                    workspaceButton(.studio)
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Eyebrow(text: "Shared Core")
                        HStack {
                            Label("\(app.snapshot.activeTaskCount) active", systemImage: "checklist")
                            Spacer()
                            Label("\(app.snapshot.connectedNodeCount) devices", systemImage: "desktopcomputer")
                        }
                        .font(.subheadline)
                        .foregroundStyle(MaryTheme.muted)
                    }
                }
            }
            .padding(16)
            .padding(.bottom, 8)
        }
        .refreshable { await app.refreshHome() }
    }

    private func workspaceButton(_ workspace: WorkspaceKind) -> some View {
        Button { navigate(workspace) } label: {
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: workspace.symbol)
                    .font(.title2)
                    .foregroundStyle(MaryTheme.cyan)
                Text(workspace.title).font(.headline)
                Text(workspace.subtitle)
                    .font(.caption)
                    .foregroundStyle(MaryTheme.muted)
                    .multilineTextAlignment(.leading)
            }
            .frame(maxWidth: .infinity, minHeight: 112, alignment: .leading)
            .padding(14)
            .background(MaryTheme.panel, in: RoundedRectangle(cornerRadius: 20))
            .overlay(RoundedRectangle(cornerRadius: 20).stroke(MaryTheme.hairline))
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
    }
}

struct FocusView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 5) {
                    Eyebrow(text: "Quiet presence")
                    Text("Focus").font(.largeTitle.bold())
                    Text("Keep Mary present without turning the screen into a backend dashboard.")
                        .foregroundStyle(MaryTheme.muted)
                }

                MaryStageView(compact: true)

                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Presence mode").font(.headline)
                        ForEach([PerformanceMode.focus, .private, .casual]) { mode in
                            Button {
                                Task { await app.changePerformanceMode(mode) }
                            } label: {
                                HStack {
                                    Label(mode.title, systemImage: mode.symbol)
                                    Spacer()
                                    if app.performanceMode == mode {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(MaryTheme.cyan)
                                    }
                                }
                                .padding(.vertical, 6)
                            }
                            .buttonStyle(.plain)
                            .foregroundStyle(.white)
                        }
                    }
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Eyebrow(text: "Status")
                        DataRow(label: "Core", value: app.isConnected ? "Online" : "Offline")
                        DataRow(label: "Conversation", value: app.conversationMode.label)
                        DataRow(label: "Voice", value: app.voiceServerAvailable ? app.voiceProvider : "Text only")
                    }
                }
            }
            .padding(16)
        }
    }
}
