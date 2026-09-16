import SwiftUI
import UIKit

private struct SharedWorkItem: Identifiable {
    let id: String
    let kind: String
    let title: String
    let status: String
    let projectID: String
    let projectTitle: String
    let priority: Int

    init?(_ value: [String: Any]) {
        let id = String(describing: value["id"] ?? "")
        let title = String(describing: value["title"] ?? "")
        guard !id.isEmpty, id != "nil", !title.isEmpty, title != "nil" else {
            return nil
        }
        self.id = id
        self.kind = String(describing: value["kind"] ?? "task")
        self.title = title
        self.status = String(describing: value["status"] ?? "active")
        self.projectID = String(describing: value["project_id"] ?? "")
        self.projectTitle = String(describing: value["project_title"] ?? "")
        self.priority = value["priority"] as? Int ?? 0
    }
}

struct WorkView: View {
    @EnvironmentObject var app: AppState
    let navigate: (WorkspaceKind) -> Void
    @State private var newItem = ""
    @State private var kind = "task"
    @State private var selectedProjectID = ""
    @State private var editingItemID = ""
    @State private var editingTitle = ""

    private var commandItems: [SharedWorkItem] {
        guard
            let command = app.workspaceData["command"] as? [String: Any],
            let raw = command["items"] as? [[String: Any]]
        else { return [] }
        return raw.compactMap(SharedWorkItem.init)
    }

    private var projects: [SharedWorkItem] {
        commandItems.filter {
            $0.kind == "project" && $0.status != "done" && $0.status != "archived"
        }
    }

    private var openTasks: [SharedWorkItem] {
        commandItems.filter {
            $0.kind == "task" && $0.status != "done" && $0.status != "archived"
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 5) {
                    Eyebrow(text: "Shared work")
                    Text("Work with Mary").font(.largeTitle.bold())
                    Text("Projects and tasks live in Mary Core, so the same work follows you across phone, desktop, and Mac.")
                        .foregroundStyle(MaryTheme.muted)
                }

                GlassCard {
                    VStack(alignment: .leading, spacing: 12) {
                        TextField(
                            kind == "project" ? "Name a project…" :
                                kind == "task" ? "Add a task…" : "Capture an idea…",
                            text: $newItem
                        )
                        .padding(12)
                        .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 14))

                        Picker("Type", selection: $kind) {
                            Text("Task").tag("task")
                            Text("Project").tag("project")
                            Text("Idea").tag("idea")
                        }
                        .pickerStyle(.segmented)

                        if kind == "task", !projects.isEmpty {
                            Picker("Project", selection: $selectedProjectID) {
                                Text("No project").tag("")
                                ForEach(projects) { project in
                                    Text(project.title).tag(project.id)
                                }
                            }
                            .pickerStyle(.menu)
                            .tint(MaryTheme.cyan)
                        }

                        Button {
                            Task { await addSharedWork() }
                        } label: {
                            Label(
                                kind == "project" ? "Create project" :
                                    kind == "task" ? "Create task" : "Save idea",
                                systemImage: "plus.circle.fill"
                            )
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

                if !projects.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Projects").font(.title3.bold())
                            Spacer()
                            Text("\(projects.count)")
                                .font(.caption.bold())
                                .foregroundStyle(MaryTheme.muted)
                        }

                        ForEach(projects) { project in
                            GlassCard {
                                if editingItemID == project.id {
                                    VStack(alignment: .leading, spacing: 10) {
                                        TextField("Project name", text: $editingTitle)
                                            .textFieldStyle(.plain)
                                            .padding(10)
                                            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 12))
                                        HStack {
                                            Button("Cancel") { cancelEditing() }
                                                .buttonStyle(.plain)
                                                .foregroundStyle(MaryTheme.muted)
                                            Spacer()
                                            Button("Save") {
                                                Task { await updateSharedWork(project) }
                                            }
                                            .buttonStyle(.plain)
                                            .foregroundStyle(MaryTheme.cyan)
                                            .disabled(editingTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                                        }
                                    }
                                } else {
                                    HStack(spacing: 12) {
                                        Image(systemName: "folder.fill")
                                            .foregroundStyle(MaryTheme.cyan)
                                        VStack(alignment: .leading, spacing: 3) {
                                            Text(project.title).font(.headline)
                                            let taskCount = openTasks.filter { $0.projectID == project.id }.count
                                            Text("\(taskCount) open task\(taskCount == 1 ? "" : "s")")
                                                .font(.caption)
                                                .foregroundStyle(MaryTheme.muted)
                                        }
                                        Spacer()
                                        Button { beginEditing(project) } label: {
                                            Image(systemName: "pencil.circle")
                                                .font(.title3)
                                                .foregroundStyle(MaryTheme.muted)
                                        }
                                        .buttonStyle(.plain)
                                        .accessibilityLabel("Rename \(project.title)")
                                    }
                                }
                            }
                        }
                    }
                }

                if !openTasks.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Open tasks").font(.title3.bold())
                            Spacer()
                            Text("\(openTasks.count)")
                                .font(.caption.bold())
                                .foregroundStyle(MaryTheme.muted)
                        }

                        ForEach(openTasks) { item in
                            GlassCard {
                                if editingItemID == item.id {
                                    VStack(alignment: .leading, spacing: 10) {
                                        TextField("Task name", text: $editingTitle)
                                            .textFieldStyle(.plain)
                                            .padding(10)
                                            .background(MaryTheme.panel2, in: RoundedRectangle(cornerRadius: 12))
                                        HStack {
                                            Button("Cancel") { cancelEditing() }
                                                .buttonStyle(.plain)
                                                .foregroundStyle(MaryTheme.muted)
                                            Spacer()
                                            Button("Save") {
                                                Task { await updateSharedWork(item) }
                                            }
                                            .buttonStyle(.plain)
                                            .foregroundStyle(MaryTheme.cyan)
                                            .disabled(editingTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                                        }
                                    }
                                } else {
                                    HStack(spacing: 12) {
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(item.title).font(.headline)
                                            if !item.projectTitle.isEmpty, item.projectTitle != "nil" {
                                                Label(item.projectTitle, systemImage: "folder")
                                                    .font(.caption)
                                                    .foregroundStyle(MaryTheme.muted)
                                            }
                                        }
                                        Spacer()
                                        Button { beginEditing(item) } label: {
                                            Image(systemName: "pencil.circle")
                                                .font(.title3)
                                                .foregroundStyle(MaryTheme.muted)
                                        }
                                        .buttonStyle(.plain)
                                        .accessibilityLabel("Rename \(item.title)")
                                        Button {
                                            Task { await completeTask(item) }
                                        } label: {
                                            Image(systemName: "checkmark.circle")
                                                .font(.title2)
                                                .foregroundStyle(MaryTheme.cyan)
                                        }
                                        .buttonStyle(.plain)
                                        .accessibilityLabel("Complete \(item.title)")
                                    }
                                }
                            }
                        }
                    }
                }

                if projects.isEmpty && openTasks.isEmpty {
                    GlassCard {
                        VStack(alignment: .leading, spacing: 6) {
                            Eyebrow(text: "Ready")
                            Text("No active projects or tasks")
                                .font(.headline)
                            Text("Create one here or tell Mary in chat: “create a project called Cleaning Business.”")
                                .font(.subheadline)
                                .foregroundStyle(MaryTheme.muted)
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

    private func addSharedWork() async {
        let title = newItem.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else { return }

        let success: Bool
        switch kind {
        case "project":
            success = await app.runWorkspaceAction(
                "project.create",
                args: [
                    "title": title,
                    "priority": 2,
                    "notes": "",
                ]
            )
        case "task":
            success = await app.runWorkspaceAction(
                "task.create",
                args: [
                    "title": title,
                    "project_id": selectedProjectID,
                    "priority": 2,
                    "notes": "",
                    "due_at": "",
                ]
            )
        default:
            success = await app.runWorkspaceAction(
                "command.add",
                args: [
                    "title": title,
                    "kind": "idea",
                    "priority": 2,
                    "notes": "",
                ]
            )
        }

        if success {
            newItem = ""
            UIImpactFeedbackGenerator(style: .soft).impactOccurred()
        }
    }

    private func beginEditing(_ item: SharedWorkItem) {
        editingItemID = item.id
        editingTitle = item.title
    }

    private func cancelEditing() {
        editingItemID = ""
        editingTitle = ""
    }

    private func updateSharedWork(_ item: SharedWorkItem) async {
        let title = editingTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else { return }

        let action = item.kind == "project" ? "project.update" : "task.update"
        let idKey = item.kind == "project" ? "project_id" : "task_id"
        if await app.runWorkspaceAction(
            action,
            args: [idKey: item.id, "title": title]
        ) {
            cancelEditing()
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        }
    }

    private func completeTask(_ item: SharedWorkItem) async {
        if await app.runWorkspaceAction(
            "task.complete",
            args: ["task_id": item.id]
        ) {
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        }
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
