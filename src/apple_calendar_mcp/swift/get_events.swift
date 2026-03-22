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

func parseArgs() -> (calendar: String, start: String, end: String, query: String?)? {
    let args = CommandLine.arguments
    var calendar: String?
    var start: String?
    var end: String?
    var query: String?

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar":
            i += 1; if i < args.count { calendar = args[i] }
        case "--start":
            i += 1; if i < args.count { start = args[i] }
        case "--end":
            i += 1; if i < args.count { end = args[i] }
        case "--query":
            i += 1; if i < args.count { query = args[i] }
        default:
            break
        }
        i += 1
    }

    guard let cal = calendar, let s = start, let e = end else {
        return nil
    }
    return (cal, s, e, query)
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
    // Use local time (no Z suffix) so returned timestamps match query parameter conventions.
    // This ensures round-trips work: read a timestamp, use it to query again.
    let df = DateFormatter()
    df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
    df.locale = Locale(identifier: "en_US_POSIX")

    var dict: [String: Any] = [
        "uid": event.calendarItemIdentifier,
        "summary": event.title ?? "",
        "start_date": df.string(from: event.startDate),
        "end_date": df.string(from: event.endDate),
        "allday_event": event.isAllDay,
        "calendar_name": event.calendar.title,
    ]

    dict["location"] = event.location ?? ""
    dict["notes"] = event.notes ?? ""
    dict["url"] = event.url?.absoluteString ?? ""

    switch event.status {
    case .none: dict["status"] = "none"
    case .confirmed: dict["status"] = "confirmed"
    case .tentative: dict["status"] = "tentative"
    case .canceled: dict["status"] = "cancelled"
    @unknown default: dict["status"] = "unknown"
    }

    // Recurrence fields
    dict["is_recurring"] = event.hasRecurrenceRules
    dict["is_detached"] = event.isDetached
    dict["occurrence_date"] = df.string(from: event.occurrenceDate)

    if let rules = event.recurrenceRules, let rule = rules.first {
        // Extract RRULE string from EKRecurrenceRule description
        let ruleStr = "\(rule)"
        if let range = ruleStr.range(of: "RRULE ") {
            dict["recurrence_rule"] = String(ruleStr[range.upperBound...])
        } else {
            dict["recurrence_rule"] = ruleStr
        }
    } else {
        dict["recurrence_rule"] = NSNull()
    }

    // Alerts
    dict["alerts"] = (event.alarms ?? []).map { alarm in
        ["minutes_before": Int(alarm.relativeOffset / -60)] as [String: Int]
    }

    // Attendees (read-only — EventKit cannot add attendees programmatically)
    dict["attendees"] = (event.attendees ?? []).map { att in
        [
            "name": att.name ?? "",
            "email": att.url.absoluteString.replacingOccurrences(of: "mailto:", with: ""),
            "role": participantRoleString(att.participantRole),
            "status": participantStatusString(att.participantStatus),
        ] as [String: String]
    }

    // Editability
    let isOrganizer = event.organizer?.isCurrentUser ?? true
    dict["is_organizer"] = isOrganizer
    dict["is_editable"] = event.calendar.allowsContentModifications && isOrganizer

    // Availability
    dict["availability"] = availabilityString(event.availability)

    // Organizer details
    if let organizer = event.organizer {
        dict["organizer_name"] = organizer.name ?? ""
        dict["organizer_email"] = organizer.url.absoluteString.replacingOccurrences(of: "mailto:", with: "")
        dict["organizer_status"] = participantStatusString(organizer.participantStatus)
    }

    // Timestamps
    if let created = event.creationDate {
        dict["created_date"] = df.string(from: created)
    }
    if let modified = event.lastModifiedDate {
        dict["modified_date"] = df.string(from: modified)
    }

    return dict
}

func availabilityString(_ availability: EKEventAvailability) -> String {
    switch availability {
    case .notSupported: return "not_supported"
    case .busy: return "busy"
    case .free: return "free"
    case .tentative: return "tentative"
    case .unavailable: return "unavailable"
    @unknown default: return "busy"
    }
}

func participantRoleString(_ role: EKParticipantRole) -> String {
    switch role {
    case .unknown: return "unknown"
    case .required: return "required"
    case .optional: return "optional"
    case .chair: return "chair"
    case .nonParticipant: return "non_participant"
    @unknown default: return "unknown"
    }
}

func participantStatusString(_ status: EKParticipantStatus) -> String {
    switch status {
    case .unknown: return "unknown"
    case .pending: return "pending"
    case .accepted: return "accepted"
    case .declined: return "declined"
    case .tentative: return "tentative"
    case .delegated: return "delegated"
    case .completed: return "completed"
    case .inProcess: return "in_process"
    @unknown default: return "unknown"
    }
}

// MARK: - Main

guard let parsed = parseArgs() else {
    outputError("invalid_args", "Required: --calendar <name> --start <ISO8601> --end <ISO8601>")
    exit(1)
}

guard let startDate = parseISO8601(parsed.start) else {
    outputError("invalid_date", "Cannot parse start date: \(parsed.start)")
    exit(1)
}

guard let endDate = parseISO8601(parsed.end) else {
    outputError("invalid_date", "Cannot parse end date: \(parsed.end)")
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
    let msg = accessError?.localizedDescription ?? "Calendar access denied. Grant permission in System Settings > Privacy & Security > Calendars."
    outputError("calendar_access_denied", msg)
    exit(1)
}

// Refresh sources to pick up recently-created events
store.refreshSourcesIfNecessary()

// Find the calendar by name
let allCalendars = store.calendars(for: .event)
guard let calendar = allCalendars.first(where: { $0.title == parsed.calendar }) else {
    let available = allCalendars.map { $0.title }.joined(separator: ", ")
    outputError("calendar_not_found", "Calendar '\(parsed.calendar)' not found. Available: \(available)")
    exit(1)
}

// Query events
let predicate = store.predicateForEvents(withStart: startDate, end: endDate, calendars: [calendar])
var events = store.events(matching: predicate)

// Filter by query text (case-insensitive match on title, notes, location)
if let query = parsed.query {
    let q = query.lowercased()
    events = events.filter { event in
        (event.title ?? "").lowercased().contains(q) ||
        (event.notes ?? "").lowercased().contains(q) ||
        (event.location ?? "").lowercased().contains(q)
    }
}

// Build JSON output
let eventDicts = events.map { eventToDict($0) }

if let data = try? JSONSerialization.data(withJSONObject: eventDicts, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize events to JSON")
}
