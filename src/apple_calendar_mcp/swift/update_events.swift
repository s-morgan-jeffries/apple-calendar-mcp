import EventKit
import Foundation

// MARK: - Argument Parsing

func parseArgs() -> String? {
    let args = CommandLine.arguments
    var calendar: String?
    var i = 1
    while i < args.count {
        if args[i] == "--calendar" { i += 1; if i < args.count { calendar = args[i] } }
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

guard let calendarName = parseArgs() else {
    outputError("invalid_args", "Required: --calendar <name>. Update data is read from stdin as JSON array.")
    exit(1)
}

let stdinData = FileHandle.standardInput.readDataToEndOfFile()
guard let updatesJson = try? JSONSerialization.jsonObject(with: stdinData) as? [[String: Any]] else {
    outputError("invalid_input", "Expected JSON array of update objects on stdin")
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

guard let calendar = store.calendars(for: .event).first(where: { $0.title == calendarName }) else {
    let available = store.calendars(for: .event).map { $0.title }.joined(separator: ", ")
    outputError("calendar_not_found", "Calendar '\(calendarName)' not found. Available: \(available)")
    exit(1)
}

var updated: [[String: Any]] = []
var errors: [[String: Any]] = []

for (index, updateData) in updatesJson.enumerated() {
    guard let uid = updateData["uid"] as? String else {
        errors.append(["index": index, "uid": "unknown", "error": "Missing required 'uid' field"])
        continue
    }

    let items = store.calendarItems(withExternalIdentifier: uid)
    guard let event = items.compactMap({ $0 as? EKEvent }).first(where: { $0.calendar.title == calendarName }) else {
        errors.append(["index": index, "uid": uid, "error": "Event not found"])
        continue
    }

    let tzName = updateData["timezone"] as? String
    let tz: TimeZone? = tzName.flatMap { TimeZone(identifier: $0) }
    var updatedFields: [String] = []

    if let summary = updateData["summary"] as? String {
        event.title = summary; updatedFields.append("summary")
    }
    if let startStr = updateData["start"] as? String, let startDate = parseISO8601(startStr, timeZone: tz) {
        event.startDate = startDate; updatedFields.append("start_date")
    }
    if let endStr = updateData["end"] as? String, let endDate = parseISO8601(endStr, timeZone: tz) {
        event.endDate = endDate; updatedFields.append("end_date")
    }
    if let location = updateData["location"] as? String {
        event.location = location; updatedFields.append("location")
    } else if updateData["clear_location"] as? Bool == true {
        event.location = nil; updatedFields.append("location")
    }
    if let notes = updateData["notes"] as? String {
        event.notes = notes; updatedFields.append("notes")
    } else if updateData["clear_notes"] as? Bool == true {
        event.notes = nil; updatedFields.append("notes")
    }
    if let urlStr = updateData["url"] as? String, let url = URL(string: urlStr) {
        event.url = url; updatedFields.append("url")
    } else if updateData["clear_url"] as? Bool == true {
        event.url = nil; updatedFields.append("url")
    }
    if let allday = updateData["allday"] as? Bool {
        event.isAllDay = allday; updatedFields.append("allday_event")
    }
    if let avail = updateData["availability"] as? String {
        event.availability = parseAvailability(avail); updatedFields.append("availability")
    }
    if updateData["clear_alerts"] as? Bool == true || updateData["alerts"] != nil {
        event.alarms = nil
        if let alerts = updateData["alerts"] as? [Int] {
            for mins in alerts { event.addAlarm(EKAlarm(relativeOffset: TimeInterval(-mins * 60))) }
        }
        updatedFields.append("alerts")
    }
    if updateData["clear_recurrence"] as? Bool == true {
        if let rules = event.recurrenceRules {
            for rule in rules { event.removeRecurrenceRule(rule) }
        }
        updatedFields.append("recurrence_rule")
    } else if let rruleStr = updateData["recurrence"] as? String, let rule = parseRecurrenceRule(rruleStr) {
        if let rules = event.recurrenceRules {
            for r in rules { event.removeRecurrenceRule(r) }
        }
        event.addRecurrenceRule(rule)
        updatedFields.append("recurrence_rule")
    }

    if updatedFields.isEmpty {
        errors.append(["index": index, "uid": uid, "error": "No fields to update"])
        continue
    }

    do {
        try store.save(event, span: .thisEvent, commit: false)
        updated.append(["uid": uid, "summary": event.title ?? "", "updated_fields": updatedFields])
    } catch {
        errors.append(["index": index, "uid": uid, "error": error.localizedDescription])
    }
}

if !updated.isEmpty {
    do {
        try store.commit()
    } catch {
        outputError("commit_failed", "Failed to commit batch: \(error.localizedDescription)")
        exit(1)
    }
}

let result: [String: Any] = ["updated": updated, "errors": errors]
if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize result")
}
