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
    var calendarId: String = ""
}

func parseArgs() -> DeleteCalendarArgs {
    var result = DeleteCalendarArgs()
    let args = CommandLine.arguments
    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar-id":
            i += 1; if i < args.count { result.calendarId = args[i] }
        default:
            break
        }
        i += 1
    }
    return result
}

// MARK: - Main

let parsed = parseArgs()

guard !parsed.calendarId.isEmpty else {
    outputError("invalid_args", "Required: --calendar-id <uuid>")
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

// Find the calendar by ID
let allCalendars = store.calendars(for: .event)
guard let calendar = allCalendars.first(where: { $0.calendarIdentifier == parsed.calendarId }) else {
    outputError("calendar_not_found", "Calendar with ID '\(parsed.calendarId)' not found.")
    exit(1)
}

do {
    try store.removeCalendar(calendar, commit: true)
} catch {
    outputError("delete_failed", "Failed to delete calendar: \(error.localizedDescription)")
    exit(1)
}

// Output result
let result: [String: String] = ["name": calendar.title, "calendar_id": calendar.calendarIdentifier]

if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
}
