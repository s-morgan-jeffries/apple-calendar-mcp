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
    var notes: String?
    var clearNotes = false
    var url: String?
    var clearUrl = false
    var allday: Bool?
    var alertMinutes: [Int] = []
    var clearAlerts = false
    var recurrence: String?
    var clearRecurrence = false
    var availability: String?
    var timezone: String?
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
        case "--notes":
            i += 1; if i < args.count { result.notes = args[i]; result.updatedFields.append("notes") }
        case "--clear-notes":
            result.clearNotes = true; result.updatedFields.append("notes")
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
        case "--recurrence":
            i += 1; if i < args.count { result.recurrence = args[i] }
            if !result.updatedFields.contains("recurrence_rule") { result.updatedFields.append("recurrence_rule") }
        case "--clear-recurrence":
            result.clearRecurrence = true
            if !result.updatedFields.contains("recurrence_rule") { result.updatedFields.append("recurrence_rule") }
        case "--availability":
            i += 1; if i < args.count { result.availability = args[i]; result.updatedFields.append("availability") }
        case "--timezone":
            i += 1; if i < args.count { result.timezone = args[i] }
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
        notes: result.notes, clearNotes: result.clearNotes,
        url: result.url, clearUrl: result.clearUrl,
        allday: result.allday, alertMinutes: result.alertMinutes,
        clearAlerts: result.clearAlerts, recurrence: result.recurrence,
        clearRecurrence: result.clearRecurrence, availability: result.availability,
        timezone: result.timezone,
        occurrenceDate: result.occurrenceDate,
        span: result.span, updatedFields: result.updatedFields
    )
    return result
}

// MARK: - Date Parsing

func parseISO8601(_ str: String, timeZone: TimeZone? = nil) -> Date? {
    let isoFormatter = ISO8601DateFormatter()
    isoFormatter.formatOptions = [.withInternetDateTime]
    if let date = isoFormatter.date(from: str) { return date }

    let df = DateFormatter()
    df.locale = Locale(identifier: "en_US_POSIX")
    if let tz = timeZone { df.timeZone = tz }
    for fmt in ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd"] {
        df.dateFormat = fmt
        if let date = df.date(from: str) { return date }
    }
    return nil
}

// MARK: - Recurrence Rule Parsing (duplicated from create_event.swift — Swift scripts can't share code)

func parseDayOfWeek(_ day: String) -> EKRecurrenceDayOfWeek? {
    let dayMap: [String: EKWeekday] = [
        "SU": .sunday, "MO": .monday, "TU": .tuesday,
        "WE": .wednesday, "TH": .thursday, "FR": .friday, "SA": .saturday
    ]
    let dayStr = String(day)
    let letters = dayStr.suffix(2)
    let prefix = dayStr.dropLast(2)

    guard let weekday = dayMap[String(letters)] else { return nil }

    if prefix.isEmpty {
        return EKRecurrenceDayOfWeek(weekday)
    } else if let weekNumber = Int(prefix) {
        return EKRecurrenceDayOfWeek(weekday, weekNumber: weekNumber)
    }
    return nil
}

func parseUntilDate(_ value: String) -> Date? {
    let df = DateFormatter()
    df.locale = Locale(identifier: "en_US_POSIX")
    for fmt in ["yyyyMMdd'T'HHmmss'Z'", "yyyyMMdd'T'HHmmss", "yyyyMMdd"] {
        df.dateFormat = fmt
        if let date = df.date(from: value) { return date }
    }
    return parseISO8601(value)
}

func parseRecurrenceRule(_ rrule: String) -> EKRecurrenceRule? {
    var frequency: EKRecurrenceFrequency = .daily
    var interval = 1
    var end: EKRecurrenceEnd?
    var daysOfWeek: [EKRecurrenceDayOfWeek]?

    let parts = rrule.split(separator: ";")
    for part in parts {
        let kv = part.split(separator: "=", maxSplits: 1)
        guard kv.count == 2 else { continue }
        let key = String(kv[0])
        let value = String(kv[1])

        switch key {
        case "FREQ":
            switch value {
            case "DAILY": frequency = .daily
            case "WEEKLY": frequency = .weekly
            case "MONTHLY": frequency = .monthly
            case "YEARLY": frequency = .yearly
            default: break
            }
        case "INTERVAL":
            interval = Int(value) ?? 1
        case "COUNT":
            if let n = Int(value) { end = EKRecurrenceEnd(occurrenceCount: n) }
        case "UNTIL":
            if let date = parseUntilDate(value) { end = EKRecurrenceEnd(end: date) }
        case "BYDAY":
            daysOfWeek = value.split(separator: ",").compactMap { parseDayOfWeek(String($0)) }
        default:
            break
        }
    }

    return EKRecurrenceRule(
        recurrenceWith: frequency,
        interval: interval,
        daysOfTheWeek: daysOfWeek,
        daysOfTheMonth: nil,
        monthsOfTheYear: nil,
        weeksOfTheYear: nil,
        daysOfTheYear: nil,
        setPositions: nil,
        end: end
    )
}

func parseAvailability(_ str: String) -> EKEventAvailability {
    switch str.lowercased() {
    case "free": return .free
    case "busy": return .busy
    case "tentative": return .tentative
    case "unavailable": return .unavailable
    default: return .busy
    }
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
var event: EKEvent?

if let occDateStr = parsed.occurrenceDate, let occDate = parseISO8601(occDateStr) {
    // For specific occurrences: use date predicate (calendarItems only returns base event)
    let cal = store.calendars(for: .event).first { $0.title == parsed.calendar }
    if let cal = cal {
        let dayBefore = occDate.addingTimeInterval(-86400)
        let dayAfter = occDate.addingTimeInterval(86400)
        let pred = store.predicateForEvents(withStart: dayBefore, end: dayAfter, calendars: [cal])
        let tolerance: TimeInterval = 60
        event = store.events(matching: pred)
            .filter { $0.calendarItemIdentifier == parsed.uid }
            .first { abs($0.occurrenceDate.timeIntervalSince(occDate)) < tolerance }
    }
} else {
    // No occurrence date: use calendarItems lookup (works for non-recurring)
    let items = store.calendarItems(withExternalIdentifier: parsed.uid)
    event = items.compactMap { $0 as? EKEvent }.first { $0.calendar.title == parsed.calendar }
}

guard let event = event else {
    outputError("event_not_found", "Event not found: \(parsed.uid)")
    exit(0)
}

// Resolve timezone for date parsing
let eventTimeZone: TimeZone? = parsed.timezone.flatMap { TimeZone(identifier: $0) }

// Apply updates
if let summary = parsed.summary {
    event.title = summary
}
if let startStr = parsed.start, let startDate = parseISO8601(startStr, timeZone: eventTimeZone) {
    event.startDate = startDate
} else if parsed.start != nil {
    outputError("invalid_date", "Cannot parse start date: \(parsed.start!)")
    exit(0)
}
if let endStr = parsed.end, let endDate = parseISO8601(endStr, timeZone: eventTimeZone) {
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
if let notes = parsed.notes {
    event.notes = notes
} else if parsed.clearNotes {
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
if parsed.clearRecurrence {
    if let rules = event.recurrenceRules {
        for rule in rules { event.removeRecurrenceRule(rule) }
    }
} else if let rruleStr = parsed.recurrence, let rule = parseRecurrenceRule(rruleStr) {
    // Replace existing rules
    if let rules = event.recurrenceRules {
        for r in rules { event.removeRecurrenceRule(r) }
    }
    event.addRecurrenceRule(rule)
}
if let avail = parsed.availability {
    event.availability = parseAvailability(avail)
}

// Determine if this is a date change on a recurring event with .thisEvent
let isDateChange = parsed.start != nil || parsed.end != nil
let isRecurringThisEvent = event.hasRecurrenceRules && parsed.span == .thisEvent && parsed.occurrenceDate != nil

if isDateChange && isRecurringThisEvent {
    // Emulate Calendar.app: remove occurrence from series, create standalone event at new time
    let newTitle = parsed.summary ?? event.title ?? ""
    let newStart = (parsed.start != nil ? parseISO8601(parsed.start!, timeZone: eventTimeZone) : nil) ?? event.startDate!
    let newEnd = (parsed.end != nil ? parseISO8601(parsed.end!, timeZone: eventTimeZone) : nil) ?? event.endDate!
    let newLocation = parsed.clearLocation ? nil : (parsed.location ?? event.location)
    let newNotes = parsed.clearNotes ? nil : (parsed.notes ?? event.notes)
    let newUrl = parsed.clearUrl ? nil : (parsed.url.flatMap { URL(string: $0) } ?? event.url)
    let newAllDay = parsed.allday ?? event.isAllDay
    let newAlarms = event.alarms

    // Remove the occurrence from the series
    do {
        try store.remove(event, span: .thisEvent)
    } catch {
        outputError("remove_failed", "Failed to remove occurrence: \(error.localizedDescription)")
        exit(0)
    }

    // Create standalone event with same properties at new time
    let newEvent = EKEvent(eventStore: store)
    newEvent.calendar = event.calendar
    newEvent.title = newTitle
    newEvent.startDate = newStart
    newEvent.endDate = newEnd
    newEvent.isAllDay = newAllDay
    newEvent.location = newLocation
    newEvent.notes = newNotes
    newEvent.url = newUrl
    if let alarms = newAlarms {
        for alarm in alarms { newEvent.addAlarm(EKAlarm(relativeOffset: alarm.relativeOffset)) }
    }

    do {
        try store.save(newEvent, span: .thisEvent)
    } catch {
        outputError("save_failed", "Failed to create rescheduled event: \(error.localizedDescription)")
        exit(0)
    }

    let result: [String: Any] = [
        "uid": newEvent.calendarItemIdentifier,
        "updated_fields": parsed.updatedFields,
        "rescheduled": true,
    ]
    if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
    exit(0)
}

// Normal save path
let saveSpan: EKSpan = (parsed.recurrence != nil || parsed.clearRecurrence) ? .futureEvents : parsed.span
do {
    try store.save(event, span: saveSpan)
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
