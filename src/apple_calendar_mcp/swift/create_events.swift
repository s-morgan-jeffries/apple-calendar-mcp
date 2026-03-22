import EventKit
import Foundation

// MARK: - Argument Parsing

func parseArgs() -> String? {
    let args = CommandLine.arguments
    var calendar: String?

    var i = 1
    while i < args.count {
        if args[i] == "--calendar" {
            i += 1; if i < args.count { calendar = args[i] }
        }
        i += 1
    }
    return calendar
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

// MARK: - Recurrence Rule Parsing

func parseDayOfWeek(_ day: String) -> EKRecurrenceDayOfWeek? {
    let dayMap: [String: EKWeekday] = [
        "SU": .sunday, "MO": .monday, "TU": .tuesday,
        "WE": .wednesday, "TH": .thursday, "FR": .friday, "SA": .saturday
    ]
    let letters = day.suffix(2)
    let prefix = day.dropLast(2)
    guard let weekday = dayMap[String(letters)] else { return nil }
    if prefix.isEmpty { return EKRecurrenceDayOfWeek(weekday) }
    if let n = Int(prefix) { return EKRecurrenceDayOfWeek(weekday, weekNumber: n) }
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

    for part in rrule.split(separator: ";") {
        let kv = part.split(separator: "=", maxSplits: 1)
        guard kv.count == 2 else { continue }
        let key = String(kv[0]), value = String(kv[1])
        switch key {
        case "FREQ":
            switch value {
            case "DAILY": frequency = .daily
            case "WEEKLY": frequency = .weekly
            case "MONTHLY": frequency = .monthly
            case "YEARLY": frequency = .yearly
            default: break
            }
        case "INTERVAL": interval = Int(value) ?? 1
        case "COUNT": if let n = Int(value) { end = EKRecurrenceEnd(occurrenceCount: n) }
        case "UNTIL": if let d = parseUntilDate(value) { end = EKRecurrenceEnd(end: d) }
        case "BYDAY": daysOfWeek = value.split(separator: ",").compactMap { parseDayOfWeek(String($0)) }
        default: break
        }
    }
    return EKRecurrenceRule(recurrenceWith: frequency, interval: interval,
        daysOfTheWeek: daysOfWeek, daysOfTheMonth: nil, monthsOfTheYear: nil,
        weeksOfTheYear: nil, daysOfTheYear: nil, setPositions: nil, end: end)
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
       let str = String(data: data, encoding: .utf8) { print(str) }
}

// MARK: - Main

let calendarName = parseArgs() ?? ""

// Read JSON from stdin
let stdinData = FileHandle.standardInput.readDataToEndOfFile()
guard let eventsJson = try? JSONSerialization.jsonObject(with: stdinData) as? [[String: Any]] else {
    outputError("invalid_input", "Expected JSON array of event objects on stdin")
    exit(1)
}

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
var accessGranted = false
store.requestFullAccessToEvents { granted, _ in
    accessGranted = granted
    semaphore.signal()
}
semaphore.wait()

if !accessGranted {
    outputError("calendar_access_denied", "Calendar access denied.")
    exit(1)
}

store.refreshSourcesIfNecessary()

let calendar: EKCalendar
if calendarName.isEmpty {
    guard let defaultCal = store.defaultCalendarForNewEvents else {
        outputError("no_default_calendar", "No default calendar configured.")
        exit(1)
    }
    calendar = defaultCal
} else {
    guard let found = store.calendars(for: .event).first(where: { $0.title == calendarName }) else {
        let available = store.calendars(for: .event).map { $0.title }.joined(separator: ", ")
        outputError("calendar_not_found", "Calendar '\(calendarName)' not found. Available: \(available)")
        exit(1)
    }
    calendar = found
}

// Create events
var created: [[String: String]] = []
var errors: [[String: Any]] = []

for (index, eventData) in eventsJson.enumerated() {
    guard let summary = eventData["summary"] as? String,
          let startStr = eventData["start"] as? String,
          let endStr = eventData["end"] as? String else {
        errors.append(["index": index, "summary": eventData["summary"] as? String ?? "unknown", "error": "Missing required fields: summary, start, end"])
        continue
    }

    let tzName = eventData["timezone"] as? String
    let tz: TimeZone? = tzName.flatMap { TimeZone(identifier: $0) }

    guard let startDate = parseISO8601(startStr, timeZone: tz) else {
        errors.append(["index": index, "summary": summary, "error": "Invalid start date: \(startStr)"])
        continue
    }
    guard let endDate = parseISO8601(endStr, timeZone: tz) else {
        errors.append(["index": index, "summary": summary, "error": "Invalid end date: \(endStr)"])
        continue
    }

    let event = EKEvent(eventStore: store)
    event.calendar = calendar
    event.title = summary
    event.startDate = startDate
    event.endDate = endDate
    event.isAllDay = eventData["allday"] as? Bool ?? false

    if let location = eventData["location"] as? String { event.location = location }
    if let notes = eventData["notes"] as? String { event.notes = notes }
    if let urlStr = eventData["url"] as? String, let url = URL(string: urlStr) { event.url = url }
    if let rrule = eventData["recurrence"] as? String, let rule = parseRecurrenceRule(rrule) {
        event.addRecurrenceRule(rule)
    }
    if let alerts = eventData["alerts"] as? [Int] {
        for mins in alerts {
            event.addAlarm(EKAlarm(relativeOffset: TimeInterval(-mins * 60)))
        }
    }
    if let avail = eventData["availability"] as? String {
        event.availability = parseAvailability(avail)
    }

    do {
        try store.save(event, span: .thisEvent, commit: false)
        created.append(["uid": event.calendarItemIdentifier, "summary": summary])
    } catch {
        errors.append(["index": index, "summary": summary, "error": error.localizedDescription])
    }
}

// Batch commit
if !created.isEmpty {
    do {
        try store.commit()
    } catch {
        outputError("commit_failed", "Failed to commit batch: \(error.localizedDescription)")
        exit(1)
    }
}

// Output result
let result: [String: Any] = ["created": created, "errors": errors]
if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize result")
}
