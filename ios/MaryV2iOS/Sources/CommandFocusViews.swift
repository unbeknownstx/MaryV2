import SwiftUI

struct CommandView: View {
    @EnvironmentObject var app: AppState
    @State private var title = ""
    @State private var kind = "task"
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionLabel(text: "Mary System")
                Text("Command").font(.largeTitle.bold())
                Text("Turn intentions into shared work without exposing backend details.").foregroundStyle(MaryTheme.muted)
                GlassCard {
                    VStack(spacing: 12) {
                        TextField("What do you want to do?", text: $title).textFieldStyle(.roundedBorder)
                        Picker("Kind", selection: $kind) { Text("Task").tag("task"); Text("Project").tag("project"); Text("Note").tag("note") }.pickerStyle(.segmented)
                        Button { Task { if await app.runWorkspace("command.add", args: ["title": title, "kind": kind, "priority": 2, "notes": ""]) { title = "" } } } label: { Label("Add to Mary", systemImage: "plus.circle.fill").frame(maxWidth: .infinity) }.buttonStyle(PrimaryButtonStyle()).disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
                if let commands = app.workspaceSnapshot["command"] as? [String: Any] {
                    HumanSummaryCard(title: "Shared work", data: commands)
                }
            }.padding(16)
        }.maryScreen()
    }
}

struct FocusView: View {
    @EnvironmentObject var app: AppState
    @State private var minutes = 25
    @State private var task = ""
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionLabel(text: "Mary System")
                Text("Focus").font(.largeTitle.bold())
                Text("A quiet session with Mary keeping the context nearby.").foregroundStyle(MaryTheme.muted)
                GlassCard {
                    VStack(spacing: 18) {
                        ZStack {
                            Circle().stroke(.white.opacity(0.06), lineWidth: 10)
                            Circle().trim(from: 0, to: 0.78).stroke(LinearGradient(colors: [MaryTheme.pink, MaryTheme.violet], startPoint: .topLeading, endPoint: .bottomTrailing), style: StrokeStyle(lineWidth: 10, lineCap: .round)).rotationEffect(.degrees(-90))
                            VStack { Text("\(minutes)").font(.system(size: 48, weight: .bold, design: .rounded)); Text("MINUTES").font(.caption2.bold()).tracking(2).foregroundStyle(MaryTheme.cyan) }
                        }.frame(width: 210, height: 210)
                        Stepper("Session length: \(minutes) min", value: $minutes, in: 5...180, step: 5)
                        TextField("What are you focusing on?", text: $task).textFieldStyle(.roundedBorder)
                        HStack {
                            Button("Start") { Task { _ = await app.runWorkspace("focus.start", args: ["minutes": minutes, "task": task]); await app.setPerformanceMode(.focus) } }.buttonStyle(PrimaryButtonStyle())
                            Button("Stop") { Task { _ = await app.runWorkspace("focus.stop", args: [:]) } }.buttonStyle(.bordered)
                        }
                    }
                }
            }.padding(16)
        }.maryScreen()
    }
}
