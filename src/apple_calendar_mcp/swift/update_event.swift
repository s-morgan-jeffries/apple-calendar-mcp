import EventKit
import Foundation

// MARK: - Argument Parsing

struct UpdateEventArgs {
    let calendar: String
    let uid: String
    var summary: String?
    var start: String?
    var end: String?
    var location: String?
    var clearLocation = false
    var description: String?
    var clearDescription = false
    var url: String?
    var clearUrl = false
    var allday: Bool?
    var alertMinutes: [Int] = []
    var clearAlerts = false
    var occurrenceDate: String?
    var span: EKSpan = .thisEvent
    var updatedFields: [String] = []
}

func parseArgs() -> UpdateEventArgs? {
    let args = CommandLine.arguments
    var calendar: String?
    var uid: String?
    var result = UpdateEventArgs(calendar: "", uid: "")

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar":
            i += 1; if i < args.count { calendar = args[i] }
        case "--uid":
            i += 1; if i < args.count { uid = args[i] }
        case "--summary":
            i += 1; if i < args.count { result.summary = args[i]; result.updatedFields.append("summary") }
        case "--start":
            i += 1; if i < args.count { result.start = args[i]; result.updatedFields.append("start_date") }
        case "--end":
            i += 1; if i < args.count { result.end = args[i]; result.updatedFields.append("end_date") }
        case "--location":
            i += 1; if i < args.count { result.location = args[i]; result.updatedFields.append("location") }
        case "--clear-location":
            result.clearLocation = true; result.updatedFields.append("location")
        case "--description":
            i += 1; if i < args.count { result.description = args[i]; result.updatedFields.append("description") }
        case "--clear-description":
            result.clearDescription = true; result.updatedFields.append("description")
        case "--url":
            i += 1; if i < args.count { result.url = args[i]; result.updatedFields.append("url") }
        case "--clear-url":
            result.clearUrl = true; result.updatedFields.append("url")
        case "--allday":
            i += 1; if i < args.count { result.allday = args[i] == "true"; result.updatedFields.append("allday_event") }
        case "--alert":
            i += 1; if i < args.count, let mins = Int(args[i]) { result.alertMinutes.append(mins) }
            if !result.updatedFields.contains("alerts") { result.updatedFields.append("alerts") }
        case "--clear-alerts":
            result.clearAlerts = true
            if !result.updatedFields.contains("alerts") { result.updatedFields.append("alerts") }
        case "--occurrence-date":
            i += 1; if i < args.count { result.occurrenceDate = args[i] }
        case "--span":
            i += 1; if i < args.count { result.span = args[i] == "future_events" ? .futureEvents : .thisEvent }
        default:
            break
        }
        i += 1
    }

    guard let cal = calendar, let u = uid else {
        return nil
    }
    result = UpdateEventArgs(
        calendar: cal, uid: u,
        summary: result.summary, start: result.start, end: result.end,
        location: result.location, clearLocation: result.clearLocation,
        description: result.description, clearDescription: result.clearDescription,
        url: result.url, clearUrl: result.clearUrl,
        allday: result.allday, alertMinutes: result.alertMinutes,
        clearAlerts: result.clearAlerts, occurrenceDate: result.occurrenceDate,
        span: result.span, updatedFields: result.updatedFields
    )
    return result
}

// MARK: - Date Parsing

func parseISO8601(_ str: String) -> Date? {
    let isoFormatter = ISO8601DateFormatter()
    isoFormatter.formatOptions = [.withInternetDateTime]
    if let date = isoFormatter.date(from: str) { return date }

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

// MARK: - Main

guard let parsed = parseArgs() else {
    outputError("invalid_args", "Required: --calendar <name> --uid <uid> and at least one field to update")
    exit(0)
}

if parsed.updatedFields.isEmpty {
    outputError("no_fields", "At least one field must be provided to update")
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

// Find event by UID (and optionally by occurrence date)
let items = store.calendarItems(withExternalIdentifier: parsed.uid)
var matches = items.compactMap { $0 as? EKEvent }.filter { $0.calendar.title == parsed.calendar }

// If occurrence date specified, find the specific occurrence
if let occDateStr = parsed.occurrenceDate, let occDate = parseISO8601(occDateStr) {
    let tolerance: TimeInterval = 60 // 1 minute tolerance
    matches = matches.filter { abs($0.occurrenceDate.timeIntervalSince(occDate)) < tolerance }
}

guard let event = matches.first else {
    outputError("event_not_found", "Event not found: \(parsed.uid)")
    exit(0)
}

// Apply updates
if let summary = parsed.summary {
    event.title = summary
}
if let startStr = parsed.start, let startDate = parseISO8601(startStr) {
    event.startDate = startDate
} else if parsed.start != nil {
    outputError("invalid_date", "Cannot parse start date: \(parsed.start!)")
    exit(0)
}
if let endStr = parsed.end, let endDate = parseISO8601(endStr) {
    event.endDate = endDate
} else if parsed.end != nil {
    outputError("invalid_date", "Cannot parse end date: \(parsed.end!)")
    exit(0)
}
if let location = parsed.location {
    event.location = location
} else if parsed.clearLocation {
    event.location = nil
}
if let description = parsed.description {
    event.notes = description
} else if parsed.clearDescription {
    event.notes = nil
}
if let urlStr = parsed.url, let url = URL(string: urlStr) {
    event.url = url
} else if parsed.clearUrl {
    event.url = nil
}
if let allday = parsed.allday {
    event.isAllDay = allday
}
if parsed.clearAlerts || !parsed.alertMinutes.isEmpty {
    event.alarms = nil
    for mins in parsed.alertMinutes {
        event.addAlarm(EKAlarm(relativeOffset: TimeInterval(-mins * 60)))
    }
}

// Save
do {
    try store.save(event, span: parsed.span)
} catch {
    outputError("save_failed", "Failed to save event: \(error.localizedDescription)")
    exit(0)
}

// Output result
let result: [String: Any] = [
    "uid": event.calendarItemIdentifier,
    "updated_fields": parsed.updatedFields,
]

if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize result to JSON")
}
