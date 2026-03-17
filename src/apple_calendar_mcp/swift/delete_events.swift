import EventKit
import Foundation

// MARK: - Argument Parsing

func parseArgs() -> (calendar: String, uids: [String], span: EKSpan)? {
    let args = CommandLine.arguments
    var calendar: String?
    var uids: [String] = []
    var span: EKSpan = .thisEvent

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar":
            i += 1; if i < args.count { calendar = args[i] }
        case "--uid":
            i += 1; if i < args.count { uids.append(args[i]) }
        case "--span":
            i += 1; if i < args.count { span = args[i] == "future_events" ? .futureEvents : .thisEvent }
        default:
            break
        }
        i += 1
    }

    guard let cal = calendar, !uids.isEmpty else {
        return nil
    }
    return (cal, uids, span)
}

// MARK: - JSON Output

func outputError(_ error: String, _ message: String) {
    let obj: [String: String] = ["error": error, "message": message]
    if let data = try? JSONSerialization.data(withJSONObject: obj),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

// MARK: - Main

guard let parsed = parseArgs() else {
    outputError("invalid_args", "Required: --calendar <name> --uid <uid> [--uid <uid> ...]")
    exit(0)
}

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
var accessGranted = false
var accessError: Error?

store.requestFullAccessToEvents { granted, error in
    accessGranted = granted
    accessError = error
    semaphore.signal()
}

semaphore.wait()

if !accessGranted {
    let msg = accessError?.localizedDescription ?? "Calendar access denied."
    outputError("calendar_access_denied", msg)
    exit(0)
}

store.refreshSourcesIfNecessary()

// Find the calendar by name
let allCalendars = store.calendars(for: .event)
guard let calendar = allCalendars.first(where: { $0.title == parsed.calendar }) else {
    let available = allCalendars.map { $0.title }.joined(separator: ", ")
    outputError("calendar_not_found", "Calendar '\(parsed.calendar)' not found. Available: \(available)")
    exit(0)
}

// Delete events by UID using direct calendarItem lookup
var deletedUids: [String] = []
var notFoundUids: [String] = []

for uid in parsed.uids {
    let items = store.calendarItems(withExternalIdentifier: uid)
    let matches = items.compactMap { $0 as? EKEvent }.filter { $0.calendar.title == parsed.calendar }
    if matches.isEmpty {
        notFoundUids.append(uid)
    } else {
        do {
            if parsed.span == .futureEvents {
                // For futureEvents, remove the first match with futureEvents span
                // (this deletes the series from this occurrence onward)
                try store.remove(matches.first!, span: .futureEvents, commit: false)
            } else {
                // For thisEvent, remove all matching occurrences individually
                for event in matches {
                    try store.remove(event, span: .thisEvent, commit: false)
                }
            }
            deletedUids.append(uid)
        } catch {
            notFoundUids.append(uid)
        }
    }
}

// Commit all deletions at once
if !deletedUids.isEmpty {
    do {
        try store.commit()
    } catch {
        outputError("delete_failed", "Failed to commit deletions: \(error.localizedDescription)")
        exit(0)
    }
}

// Output result
let result: [String: Any] = [
    "deleted_uids": deletedUids,
    "not_found_uids": notFoundUids,
]

if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize result to JSON")
}
