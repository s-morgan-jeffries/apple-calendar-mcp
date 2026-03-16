import EventKit
import Foundation

// MARK: - Argument Parsing

func printUsage() {
    let msg = """
    Usage: get_events.swift --calendar <name> --start <ISO8601> --end <ISO8601>

    Queries Apple Calendar events using EventKit.
    Outputs JSON array to stdout.
    """
    FileHandle.standardError.write(Data(msg.utf8))
}

func parseArgs() -> (calendar: String, start: String, end: String)? {
    let args = CommandLine.arguments
    var calendar: String?
    var start: String?
    var end: String?

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar":
            i += 1; if i < args.count { calendar = args[i] }
        case "--start":
            i += 1; if i < args.count { start = args[i] }
        case "--end":
            i += 1; if i < args.count { end = args[i] }
        default:
            break
        }
        i += 1
    }

    guard let cal = calendar, let s = start, let e = end else {
        return nil
    }
    return (cal, s, e)
}

// MARK: - Date Parsing

func parseISO8601(_ str: String) -> Date? {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    if let date = formatter.date(from: str) { return date }

    // Try without timezone (assume local)
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    if let date = formatter.date(from: str) { return date }

    // Try date-only or datetime without timezone
    let df = DateFormatter()
    df.locale = Locale(identifier: "en_US_POSIX")
    for fmt in ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd"] {
        df.dateFormat = fmt
        if let date = df.date(from: str) { return date }
    }
    return nil
}

// MARK: - JSON Output

func outputError(_ error: String, _ message: String) {
    let obj: [String: String] = ["error": error, "message": message]
    if let data = try? JSONSerialization.data(withJSONObject: obj),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

func eventToDict(_ event: EKEvent) -> [String: Any] {
    let df = ISO8601DateFormatter()
    df.formatOptions = [.withInternetDateTime]

    var dict: [String: Any] = [
        "uid": event.calendarItemIdentifier,
        "summary": event.title ?? "",
        "start_date": df.string(from: event.startDate),
        "end_date": df.string(from: event.endDate),
        "allday_event": event.isAllDay,
        "calendar_name": event.calendar.title,
    ]

    dict["location"] = event.location ?? ""
    dict["description"] = event.notes ?? ""
    dict["url"] = event.url?.absoluteString ?? ""

    switch event.status {
    case .none: dict["status"] = "none"
    case .confirmed: dict["status"] = "confirmed"
    case .tentative: dict["status"] = "tentative"
    case .canceled: dict["status"] = "cancelled"
    @unknown default: dict["status"] = "unknown"
    }

    return dict
}

// MARK: - Main

guard let parsed = parseArgs() else {
    outputError("invalid_args", "Required: --calendar <name> --start <ISO8601> --end <ISO8601>")
    exit(0)
}

guard let startDate = parseISO8601(parsed.start) else {
    outputError("invalid_date", "Cannot parse start date: \(parsed.start)")
    exit(0)
}

guard let endDate = parseISO8601(parsed.end) else {
    outputError("invalid_date", "Cannot parse end date: \(parsed.end)")
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
    let msg = accessError?.localizedDescription ?? "Calendar access denied. Grant permission in System Settings > Privacy & Security > Calendars."
    outputError("calendar_access_denied", msg)
    exit(0)
}

// Refresh sources to pick up recently-created events
store.refreshSourcesIfNecessary()

// Find the calendar by name
let allCalendars = store.calendars(for: .event)
guard let calendar = allCalendars.first(where: { $0.title == parsed.calendar }) else {
    let available = allCalendars.map { $0.title }.joined(separator: ", ")
    outputError("calendar_not_found", "Calendar '\(parsed.calendar)' not found. Available: \(available)")
    exit(0)
}

// Query events
let predicate = store.predicateForEvents(withStart: startDate, end: endDate, calendars: [calendar])
let events = store.events(matching: predicate)

// Build JSON output
let eventDicts = events.map { eventToDict($0) }

if let data = try? JSONSerialization.data(withJSONObject: eventDicts, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize events to JSON")
}
