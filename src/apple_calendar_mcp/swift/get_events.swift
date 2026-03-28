import CoreLocation
import EventKit
import Foundation

// MARK: - Argument Parsing

func printUsage() {
    let msg = """
    Usage: get_events.swift [--calendar <name> ...] --start <ISO8601> --end <ISO8601>

    Queries Apple Calendar events using EventKit.
    Multiple --calendar flags can be provided. If none, queries all calendars.
    Outputs JSON array to stdout.
    """
    FileHandle.standardError.write(Data(msg.utf8))
}

func parseArgs() -> (calendars: [String], calendarIds: [String], start: String, end: String, query: String?)? {
    let args = CommandLine.arguments
    var calendars: [String] = []
    var calendarIds: [String] = []
    var start: String?
    var end: String?
    var query: String?

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar":
            i += 1; if i < args.count { calendars.append(args[i]) }
        case "--calendar-id":
            i += 1; if i < args.count { calendarIds.append(args[i]) }
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

    guard let s = start, let e = end else {
        return nil
    }
    return (calendars, calendarIds, s, e, query)
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
    if let sl = event.structuredLocation {
        var slDict: [String: Any] = ["title": sl.title ?? ""]
        if let geo = sl.geoLocation {
            slDict["latitude"] = geo.coordinate.latitude
            slDict["longitude"] = geo.coordinate.longitude
        }
        if sl.radius > 0 {
            slDict["radius"] = sl.radius
        }
        dict["structured_location"] = slDict
    }
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
            dict["recurrence"] = String(ruleStr[range.upperBound...])
        } else {
            dict["recurrence"] = ruleStr
        }

        // Structured recurrence output
        var parsed: [String: Any] = [:]
        switch rule.frequency {
        case .daily: parsed["frequency"] = "daily"
        case .weekly: parsed["frequency"] = "weekly"
        case .monthly: parsed["frequency"] = "monthly"
        case .yearly: parsed["frequency"] = "yearly"
        @unknown default: parsed["frequency"] = "unknown"
        }
        parsed["interval"] = rule.interval
        if let days = rule.daysOfTheWeek {
            parsed["days_of_week"] = days.map { day -> String in
                let dayNames = ["", "SU", "MO", "TU", "WE", "TH", "FR", "SA"]
                let dayStr = dayNames[day.dayOfTheWeek.rawValue]
                if day.weekNumber != 0 {
                    return "\(day.weekNumber)\(dayStr)"
                }
                return dayStr
            }
        }
        if let recEnd = rule.recurrenceEnd {
            if let endDate = recEnd.endDate {
                parsed["until"] = df.string(from: endDate)
            } else if recEnd.occurrenceCount > 0 {
                parsed["count"] = recEnd.occurrenceCount
            }
        }
        dict["recurrence_parsed"] = parsed
    } else {
        dict["recurrence"] = NSNull()
    }

    // Alerts
    dict["alerts"] = (event.alarms ?? []).map { alarm -> [String: Any] in
        if alarm.absoluteDate != nil {
            return ["type": "absolute", "date": df.string(from: alarm.absoluteDate!)]
        } else if alarm.proximity != .none {
            return ["type": "proximity",
                    "proximity": alarm.proximity == .leave ? "leave" : "enter"]
        } else {
            return ["type": "relative", "minutes_before": Int(alarm.relativeOffset / -60)]
        }
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

    // Timezone (preserves scheduling intent for cross-timezone events)
    if let tz = event.timeZone {
        dict["timezone"] = tz.identifier
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
    outputError("invalid_args", "Required: --start <ISO8601> --end <ISO8601> [--calendar <name> ...]")
    exit(1)
}

guard let startDate = parseISO8601(parsed.start) else {
    outputError("invalid_date", "Cannot parse start date: \(parsed.start)")
    exit(1)
}

guard var endDate = parseISO8601(parsed.end) else {
    outputError("invalid_date", "Cannot parse end date: \(parsed.end)")
    exit(1)
}

// Date-only end_date is inclusive: "2026-03-29" means through end of March 29
if !parsed.end.contains("T") {
    endDate = Calendar.current.date(byAdding: .day, value: 1, to: endDate)!
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

// Resolve calendars: nil means all calendars, otherwise look up by ID or name
let allCalendars = store.calendars(for: .event)
let calendarArray: [EKCalendar]?

if !parsed.calendarIds.isEmpty {
    var resolved: [EKCalendar] = []
    for calId in parsed.calendarIds {
        guard let cal = allCalendars.first(where: { $0.calendarIdentifier == calId }) else {
            outputError("calendar_not_found", "Calendar with ID '\(calId)' not found.")
            exit(1)
        }
        resolved.append(cal)
    }
    calendarArray = resolved
} else if !parsed.calendars.isEmpty {
    var resolved: [EKCalendar] = []
    for calName in parsed.calendars {
        guard let cal = allCalendars.first(where: { $0.title == calName }) else {
            outputError("calendar_not_found", "Calendar '\(calName)' not found. Use get_calendars to see available names.")
            exit(1)
        }
        resolved.append(cal)
    }
    calendarArray = resolved
} else {
    calendarArray = nil  // EventKit queries all calendars
}

// Query events
let predicate = store.predicateForEvents(withStart: startDate, end: endDate, calendars: calendarArray)
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
