import EventKit
import Foundation

// MARK: - Argument Parsing

struct CreateEventArgs {
    let calendar: String
    let summary: String
    let start: String
    let end: String
    var location: String?
    var description: String?
    var url: String?
    var allday: Bool = false
    var recurrence: String?
    var alertMinutes: [Int] = []
}

func parseArgs() -> CreateEventArgs? {
    let args = CommandLine.arguments
    var calendar: String?
    var summary: String?
    var start: String?
    var end: String?
    var location: String?
    var description: String?
    var url: String?
    var allday = false
    var recurrence: String?
    var alertMinutes: [Int] = []

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar":
            i += 1; if i < args.count { calendar = args[i] }
        case "--summary":
            i += 1; if i < args.count { summary = args[i] }
        case "--start":
            i += 1; if i < args.count { start = args[i] }
        case "--end":
            i += 1; if i < args.count { end = args[i] }
        case "--location":
            i += 1; if i < args.count { location = args[i] }
        case "--description":
            i += 1; if i < args.count { description = args[i] }
        case "--url":
            i += 1; if i < args.count { url = args[i] }
        case "--allday":
            allday = true
        case "--recurrence":
            i += 1; if i < args.count { recurrence = args[i] }
        case "--alert":
            i += 1; if i < args.count, let mins = Int(args[i]) { alertMinutes.append(mins) }
        default:
            break
        }
        i += 1
    }

    guard let cal = calendar, let sum = summary, let s = start, let e = end else {
        return nil
    }
    var result = CreateEventArgs(calendar: cal, summary: sum, start: s, end: e)
    result.location = location
    result.description = description
    result.url = url
    result.allday = allday
    result.recurrence = recurrence
    result.alertMinutes = alertMinutes
    return result
}

// MARK: - Date Parsing

func parseISO8601(_ str: String) -> Date? {
    // Try with timezone (e.g., "2026-03-15T14:00:00Z")
    let isoFormatter = ISO8601DateFormatter()
    isoFormatter.formatOptions = [.withInternetDateTime]
    if let date = isoFormatter.date(from: str) { return date }

    // Try without timezone — interpret as local time
    let df = DateFormatter()
    df.locale = Locale(identifier: "en_US_POSIX")
    for fmt in ["yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd"] {
        df.dateFormat = fmt
        if let date = df.date(from: str) { return date }
    }
    return nil
}

// MARK: - Recurrence Rule Parsing

func parseDayOfWeek(_ day: String) -> EKRecurrenceDayOfWeek? {
    let dayMap: [String: EKWeekday] = [
        "SU": .sunday, "MO": .monday, "TU": .tuesday,
        "WE": .wednesday, "TH": .thursday, "FR": .friday, "SA": .saturday
    ]
    // Parse optional numeric prefix: "4MO" → weekNumber=4, day="MO"
    // "-1FR" → weekNumber=-1, day="FR"
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

func parseUntilDate(_ value: String) -> Date? {
    // Try formats: "20280322T000000Z", "20280322T000000", "20280322"
    let df = DateFormatter()
    df.locale = Locale(identifier: "en_US_POSIX")
    for fmt in ["yyyyMMdd'T'HHmmss'Z'", "yyyyMMdd'T'HHmmss", "yyyyMMdd"] {
        df.dateFormat = fmt
        if let date = df.date(from: value) { return date }
    }
    // Also try ISO 8601 format
    return parseISO8601(value)
}

// MARK: - JSON Output

func outputError(_ error: String, _ message: String) {
    let obj: [String: String] = ["error": error, "message": message]
    if let data = try? JSONSerialization.data(withJSONObject: obj),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

func outputSuccess(_ uid: String) {
    let obj: [String: String] = ["uid": uid]
    if let data = try? JSONSerialization.data(withJSONObject: obj),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

// MARK: - Main

guard let parsed = parseArgs() else {
    outputError("invalid_args", "Required: --calendar <name> --summary <text> --start <ISO8601> --end <ISO8601>")
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

// Create the event
let event = EKEvent(eventStore: store)
event.calendar = calendar
event.title = parsed.summary
event.startDate = startDate
event.endDate = endDate
event.isAllDay = parsed.allday

if let location = parsed.location {
    event.location = location
}
if let description = parsed.description {
    event.notes = description
}
if let urlStr = parsed.url, let url = URL(string: urlStr) {
    event.url = url
}
if let rrule = parsed.recurrence, let rule = parseRecurrenceRule(rrule) {
    event.addRecurrenceRule(rule)
}
for mins in parsed.alertMinutes {
    event.addAlarm(EKAlarm(relativeOffset: TimeInterval(-mins * 60)))
}

do {
    try store.save(event, span: .thisEvent)
    outputSuccess(event.calendarItemIdentifier)
} catch {
    outputError("save_failed", "Failed to save event: \(error.localizedDescription)")
}
