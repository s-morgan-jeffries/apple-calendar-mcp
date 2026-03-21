import EventKit
import Foundation

// MARK: - JSON Output

func outputError(_ error: String, _ message: String) {
    let obj: [String: String] = ["error": error, "message": message]
    if let data = try? JSONSerialization.data(withJSONObject: obj),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

// MARK: - Argument Parsing

struct DeleteCalendarArgs {
    var name: String = ""
}

func parseArgs() -> DeleteCalendarArgs {
    var result = DeleteCalendarArgs()
    let args = CommandLine.arguments
    var i = 1
    while i < args.count {
        switch args[i] {
        case "--name":
            i += 1; if i < args.count { result.name = args[i] }
        default:
            break
        }
        i += 1
    }
    return result
}

// MARK: - Main

let parsed = parseArgs()

guard !parsed.name.isEmpty else {
    outputError("invalid_args", "Required: --name <calendar_name>")
    exit(1)
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
    exit(1)
}

store.refreshSourcesIfNecessary()

// Find the calendar by name
let calendars = store.calendars(for: .event).filter { $0.title == parsed.name }

guard let calendar = calendars.first else {
    let available = store.calendars(for: .event).map { $0.title }.joined(separator: ", ")
    outputError("calendar_not_found", "Calendar '\(parsed.name)' not found. Available: \(available)")
    exit(1)
}

do {
    try store.removeCalendar(calendar, commit: true)
} catch {
    outputError("delete_failed", "Failed to delete calendar: \(error.localizedDescription)")
    exit(1)
}

// Output result
let result: [String: String] = ["name": parsed.name]

if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
}
