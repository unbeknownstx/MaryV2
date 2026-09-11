import Foundation

enum CoreProjection {
    static func int(_ value: Any?) -> Int {
        if let value = value as? Int { return value }
        if let value = value as? NSNumber { return value.intValue }
        if let value = value as? String { return Int(value) ?? 0 }
        return 0
    }

    static func bool(_ value: Any?) -> Bool {
        if let value = value as? Bool { return value }
        if let value = value as? NSNumber { return value.boolValue }
        if let value = value as? String {
            return ["1", "true", "yes", "on", "connected", "ready"].contains(value.lowercased())
        }
        return false
    }

    static func string(_ value: Any?) -> String {
        guard let value else { return "" }
        if let value = value as? String { return value }
        if let value = value as? NSNumber { return value.stringValue }
        return ""
    }

    static func dict(_ value: Any?) -> [String: Any] { value as? [String: Any] ?? [:] }
    static func array(_ value: Any?) -> [Any] { value as? [Any] ?? [] }

    static func companionSnapshot(
        dashboard: [String: Any],
        workspace: [String: Any],
        voiceReady: Bool
    ) -> CompanionSnapshot {
        var snapshot = CompanionSnapshot()
        let current = dict(workspace["current_work"])
        snapshot.currentProject = string(current["project"])
        snapshot.currentSummary = string(current["summary"])

        let command = dict(workspace["command"])
        snapshot.activeTaskCount = array(command["items"]).filter { item in
            let row = dict(item)
            let status = string(row["status"]).lowercased()
            return status != "done" && status != "completed"
        }.count

        let fabric = dict(dashboard["compute_fabric"])
        snapshot.connectedNodeCount = int(fabric["connected_nodes"] ?? fabric["nodes"])

        let memory = dict(dashboard["memory"])
        let counts = dict(memory["counts"])
        snapshot.memoryCount =
            int(counts["episodic"]) +
            int(counts["semantic"]) +
            int(counts["working"])
        snapshot.voiceReady = voiceReady
        return snapshot
    }

    static func readableMemorySummary(_ raw: [String: Any]) -> (total: Int, sharedEvents: Int, lines: [String]) {
        let counts = dict(raw["counts"])
        let total = int(counts["episodic"]) + int(counts["semantic"]) + int(counts["working"])
        let shared = dict(raw["shared_work"])
        let events = int(shared["durable_events"])
        var lines: [String] = []
        lines.append(total > 0
            ? "Mary has \(total) active memory records available to this Core."
            : "No canonical memory records are currently available to this Core.")
        if events > 0 { lines.append("Shared-work continuity has \(events) durable events.") }
        let consolidation = dict(raw["consolidation"])
        let candidates = int(consolidation["eligible_candidates"])
        if candidates > 0 { lines.append("\(candidates) memories are eligible for consolidation.") }
        return (total, events, lines)
    }

    static func nodeCards(_ raw: [String: Any]) -> [[String: String]] {
        array(raw["nodes"]).compactMap { item in
            let row = dict(item)
            let name = string(row["display_name"] ?? row["node_id"])
            guard !name.isEmpty else { return nil }
            let caps = row["capabilities"] as? [Any] ?? Array(dict(row["capabilities"]).values)
            return [
                "name": name,
                "platform": string(row["platform"]).capitalized,
                "status": bool(row["connected"] ?? row["available"]) ? "Connected" : "Offline",
                "capabilities": String(caps.count),
            ]
        }
    }

    static func integrations(_ raw: [String: Any]) -> [[String: String]] {
        let source = dict(raw["integrations"] ?? raw["services"])
        return source.keys.sorted().map { key in
            let row = dict(source[key])
            let ready = bool(row["available"] ?? row["enabled"] ?? row["connected"])
            return [
                "name": key.replacingOccurrences(of: "_", with: " ").capitalized,
                "status": ready ? "Ready" : "Not connected",
            ]
        }
    }
}
