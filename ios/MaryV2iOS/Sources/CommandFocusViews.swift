import SwiftUI

struct CommandView: View {
    @EnvironmentObject var app: AppState
    @State private var title = ""
    @State private var kind = "task"

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 13) {
                TinyCaps(text: "MARY SYSTEM")
                Text("Command").font(.largeTitle.bold())
                Text("Add intentional work to Mary's canonical workspace.")
                    .foregroundStyle(MaryTheme.muted)

                MaryPanel {
                    VStack(spacing: 10) {
                        TextField("Task or project", text: $title)
                            .textFieldStyle(.roundedBorder)

                        Picker("Kind", selection: $kind) {
                            Text("Task").tag("task")
                            Text("Project").tag("project")
                            Text("Note").tag("note")
                        }
                        .pickerStyle(.segmented)

                        Button {
                            Task {
                                if await app.runWorkspaceAction("command.add", args: [
                                    "title": title,
                                    "kind": kind,
                                    "priority": 2,
                                    "notes": ""
                                ]) {
                                    title = ""
                                }
                            }
                        } label: {
                            Label("Add to Mary", systemImage: "plus.circle.fill")
                                .frame(maxWidth: .infinity)
                                .frame(height: 44)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(MaryTheme.violet)
                        .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }

                Button {
                    app.draft = title
                    app.selectedTab = .chat
                } label: {
                    Label("Talk to Mary about this instead", systemImage: "bubble.left.fill")
                }
                .buttonStyle(.bordered)
            }
            .padding(13)
        }
    }
}

struct FocusView: View {
    @EnvironmentObject var app: AppState
    @State private var minutes = 25
    @State private var task = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 13) {
                TinyCaps(text: "MARY SYSTEM")
                Text("Focus").font(.largeTitle.bold())
                Text("Start a focus session and optionally quiet Mary's presentation.")
                    .foregroundStyle(MaryTheme.muted)

                MaryPanel {
                    VStack(spacing: 14) {
                        ZStack {
                            Circle().stroke(.white.opacity(0.06), lineWidth: 9)
                            Circle()
                                .trim(from: 0, to: 0.78)
                                .stroke(MaryTheme.accent, style: StrokeStyle(lineWidth: 9, lineCap: .round))
                                .rotationEffect(.degrees(-90))

                            VStack(spacing: 3) {
                                Text("\(minutes):00")
                                    .font(.system(size: 38, weight: .bold, design: .rounded))
                                Text("FOCUS READY")
                                    .font(.caption2.weight(.black))
                                    .tracking(1.6)
                                    .foregroundStyle(MaryTheme.cyan)
                            }
                        }
                        .frame(width: 210, height: 210)

                        Stepper("Minutes: \(minutes)", value: $minutes, in: 5...180, step: 5)
                        TextField("What are you focusing on?", text: $task)
                            .textFieldStyle(.roundedBorder)

                        Button("Start Focus") {
                            Task {
                                _ = await app.runWorkspaceAction("focus.start", args: [
                                    "minutes": minutes,
                                    "task": task
                                ])
                                await app.changePerformanceMode(.focus)
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(MaryTheme.violet)

                        Button("Stop Focus") {
                            Task {
                                _ = await app.runWorkspaceAction("focus.stop", args: [:])
                            }
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
            .padding(13)
        }
    }
}
