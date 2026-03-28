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
    var calendarId: String = ""
    var source: String = ""
}

func parseArgs() -> DeleteCalendarArgs {
    var result = DeleteCalendarArgs()
    let args = CommandLine.arguments
    var i = 1
    while i < args.count {
        switch args[i] {
        case "--name":
            i += 1; if i < args.count { result.name = args[i] }
        case "--calendar-id":
            i += 1; if i < args.count { result.calendarId = args[i] }
        case "--source":
            i += 1; if i < args.count { result.source = args[i] }
        default:
            break
        }
        i += 1
    }
    return result
}

// MARK: - Main

let parsed = parseArgs()

guard !parsed.name.isEmpty || !parsed.calendarId.isEmpty else {
    outputError("invalid_args", "Required: --name <calendar_name> or --calendar-id <uuid>")
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

// Find the calendar by ID, or by name (and optionally source)
let allCalendars = store.calendars(for: .event)
let calendar: EKCalendar
if !parsed.calendarId.isEmpty {
    guard let found = allCalendars.first(where: { $0.calendarIdentifier == parsed.calendarId }) else {
        outputError("calendar_not_found", "Calendar with ID '\(parsed.calendarId)' not found.")
        exit(1)
    }
    calendar = found
} else {
    let matches = allCalendars.filter { $0.title == parsed.name && (parsed.source.isEmpty || $0.source.title == parsed.source) }
    if matches.count > 1 && parsed.source.isEmpty {
        outputError("ambiguous_calendar", "Multiple calendars named '\(parsed.name)' found. Specify calendar_source or calendar_id to disambiguate.")
        exit(1)
    }
    guard let found = matches.first else {
        let displayName = parsed.source.isEmpty ? parsed.name : "\(parsed.name) (\(parsed.source))"
        outputError("calendar_not_found", "Calendar '\(displayName)' not found. Use get_calendars to see available names.")
        exit(1)
    }
    calendar = found
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
