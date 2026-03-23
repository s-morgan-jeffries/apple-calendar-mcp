import CoreLocation
import EventKit
import Foundation

// MARK: - Argument Parsing

struct UpdateEventsArgs {
    var calendar: String = ""
    var source: String = ""
}

func parseArgs() -> UpdateEventsArgs {
    var result = UpdateEventsArgs()
    let args = CommandLine.arguments
    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar":
            i += 1; if i < args.count { result.calendar = args[i] }
        case "--source":
            i += 1; if i < args.count { result.source = args[i] }
        default:
            break
        }
        i += 1
    }
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

func parseStructuredRecurrence(_ dict: [String: Any]) -> EKRecurrenceRule? {
    guard let freqStr = dict["frequency"] as? String else { return nil }

    var frequency: EKRecurrenceFrequency
    switch freqStr.lowercased() {
    case "daily": frequency = .daily
    case "weekly": frequency = .weekly
    case "monthly": frequency = .monthly
    case "yearly": frequency = .yearly
    default: return nil
    }

    let interval = dict["interval"] as? Int ?? 1

    var daysOfWeek: [EKRecurrenceDayOfWeek]?
    if let days = dict["days_of_week"] as? [String] {
        daysOfWeek = days.compactMap { parseDayOfWeek($0) }
    }

    var end: EKRecurrenceEnd?
    if let count = dict["count"] as? Int {
        end = EKRecurrenceEnd(occurrenceCount: count)
    } else if let untilStr = dict["until"] as? String, let untilDate = parseISO8601(untilStr) ?? parseUntilDate(untilStr) {
        end = EKRecurrenceEnd(end: untilDate)
    }

    return EKRecurrenceRule(recurrenceWith: frequency, interval: interval,
        daysOfTheWeek: daysOfWeek, daysOfTheMonth: nil, monthsOfTheYear: nil,
        weeksOfTheYear: nil, daysOfTheYear: nil, setPositions: nil, end: end)
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

let parsed = parseArgs()
let calendarName = parsed.calendar
let sourceName = parsed.source

guard !calendarName.isEmpty else {
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

let calMatches = store.calendars(for: .event).filter { $0.title == calendarName && (sourceName.isEmpty || $0.source.title == sourceName) }
if calMatches.count > 1 && sourceName.isEmpty {
    outputError("ambiguous_calendar", "Multiple calendars named '\(calendarName)' found. Specify calendar_source to disambiguate.")
    exit(1)
}
guard let calendar = calMatches.first else {
    let displayName = sourceName.isEmpty ? calendarName : "\(calendarName) (\(sourceName))"
    outputError("calendar_not_found", "Calendar '\(displayName)' not found. Use get_calendars to see available names.")
    exit(1)
}

var updated: [[String: Any]] = []
var errors: [[String: Any]] = []

for (index, updateData) in updatesJson.enumerated() {
    guard let uid = updateData["uid"] as? String else {
        errors.append(["index": index, "uid": "unknown", "error": "Missing required 'uid' field"])
        continue
    }

    // Parse optional occurrence_date and span
    let occDateStr = updateData["occurrence_date"] as? String
    let occDate: Date? = occDateStr.flatMap { parseISO8601($0) }
    let spanStr = updateData["span"] as? String ?? "this_event"
    let span: EKSpan = spanStr == "future_events" ? .futureEvents : .thisEvent

    // Dual-path event lookup
    var event: EKEvent?
    if let occDate = occDate {
        // Predicate-based search: ±1 day around occurrence_date, filter by UID, 60s tolerance
        let dayBefore = occDate.addingTimeInterval(-86400)
        let dayAfter = occDate.addingTimeInterval(86400)
        let pred = store.predicateForEvents(withStart: dayBefore, end: dayAfter, calendars: [calendar])
        let tolerance: TimeInterval = 60
        event = store.events(matching: pred)
            .filter { $0.calendarItemIdentifier == uid }
            .first { abs($0.occurrenceDate.timeIntervalSince(occDate)) < tolerance }
    } else {
        // Standard lookup
        let items = store.calendarItems(withExternalIdentifier: uid)
        event = items.compactMap { $0 as? EKEvent }.first { $0.calendar.title == calendarName }
    }

    guard let event = event else {
        errors.append(["index": index, "uid": uid, "error": "Event not found"])
        continue
    }

    let tzName = updateData["timezone"] as? String
    let tz: TimeZone? = tzName.flatMap { TimeZone(identifier: $0) }
    var updatedFields: [String] = []

    // Parse new start/end before applying
    let newStartStr = updateData["start_date"] as? String
    let newEndStr = updateData["end_date"] as? String
    let newStart: Date? = newStartStr.flatMap { parseISO8601($0, timeZone: tz) }
    let newEnd: Date? = newEndStr.flatMap { parseISO8601($0, timeZone: tz) }

    // Check if this is a date change on a recurring event with .thisEvent
    let isDateChange = newStart != nil || newEnd != nil
    let isRecurringThisEvent = event.hasRecurrenceRules && span == .thisEvent && occDate != nil

    if isDateChange && isRecurringThisEvent {
        // Reschedule flow: remove occurrence from series, create standalone event at new time
        let eventTitle = (updateData["summary"] as? String) ?? event.title ?? ""
        let eventStart = newStart ?? event.startDate!
        let eventEnd = newEnd ?? event.endDate!
        let clearLocation = updateData["clear_location"] as? Bool == true
        let clearNotes = updateData["clear_notes"] as? Bool == true
        let clearUrl = updateData["clear_url"] as? Bool == true
        let eventLocation = clearLocation ? nil : ((updateData["location"] as? String) ?? event.location)
        let eventNotes = clearNotes ? nil : ((updateData["notes"] as? String) ?? event.notes)
        let eventUrlStr = updateData["url"] as? String
        let eventUrl = clearUrl ? nil : (eventUrlStr.flatMap { URL(string: $0) } ?? event.url)
        let eventAllDay = (updateData["allday"] as? Bool) ?? event.isAllDay
        let eventAlarms = event.alarms

        // Build updatedFields for reschedule
        if updateData["summary"] != nil { updatedFields.append("summary") }
        if newStart != nil { updatedFields.append("start_date") }
        if newEnd != nil { updatedFields.append("end_date") }
        if updateData["location"] != nil || clearLocation { updatedFields.append("location") }
        if updateData["notes"] != nil || clearNotes { updatedFields.append("notes") }
        if updateData["url"] != nil || clearUrl { updatedFields.append("url") }
        if updateData["allday"] != nil { updatedFields.append("allday_event") }
        if updateData["availability"] != nil { updatedFields.append("availability") }
        if updateData["clear_alerts"] as? Bool == true || updateData["alerts"] != nil { updatedFields.append("alerts") }

        // Remove the occurrence from the series
        do {
            try store.remove(event, span: .thisEvent, commit: false)
        } catch {
            errors.append(["index": index, "uid": uid, "error": "Failed to remove occurrence: \(error.localizedDescription)"])
            continue
        }

        // Create standalone event with same properties at new time
        let newEvent = EKEvent(eventStore: store)
        newEvent.calendar = calendar
        newEvent.title = eventTitle
        newEvent.startDate = eventStart
        newEvent.endDate = eventEnd
        newEvent.isAllDay = eventAllDay
        newEvent.location = eventLocation
        // Copy or set structured location
        if let slData = updateData["structured_location"] as? [String: Any] {
            let sl = EKStructuredLocation(title: slData["title"] as? String ?? "")
            if let lat = slData["latitude"] as? Double, let lon = slData["longitude"] as? Double {
                sl.geoLocation = CLLocation(latitude: lat, longitude: lon)
            }
            if let radius = slData["radius"] as? Double { sl.radius = radius }
            newEvent.structuredLocation = sl
            updatedFields.append("structured_location")
        } else if let existingSL = event.structuredLocation {
            newEvent.structuredLocation = existingSL
        }
        newEvent.notes = eventNotes
        newEvent.url = eventUrl
        if let alarms = eventAlarms {
            for alarm in alarms { newEvent.addAlarm(EKAlarm(relativeOffset: alarm.relativeOffset)) }
        }
        // Apply new alerts if provided
        if updateData["clear_alerts"] as? Bool == true || updateData["alerts"] != nil {
            newEvent.alarms = nil
            if let alerts = updateData["alerts"] as? [Any] {
                for alert in alerts {
                    if let mins = alert as? Int {
                        newEvent.addAlarm(EKAlarm(relativeOffset: TimeInterval(-mins * 60)))
                    } else if let dict = alert as? [String: Any], let type = dict["type"] as? String {
                        switch type {
                        case "absolute":
                            if let dateStr = dict["date"] as? String, let date = parseISO8601(dateStr) {
                                newEvent.addAlarm(EKAlarm(absoluteDate: date))
                            }
                        case "proximity":
                            if let proxStr = dict["proximity"] as? String, let sl = newEvent.structuredLocation {
                                let alarm = EKAlarm()
                                alarm.structuredLocation = sl
                                alarm.proximity = proxStr == "leave" ? .leave : .enter
                                newEvent.addAlarm(alarm)
                            }
                        default: break
                        }
                    }
                }
            }
        }
        if let avail = updateData["availability"] as? String {
            newEvent.availability = parseAvailability(avail)
        }

        do {
            try store.save(newEvent, span: .thisEvent, commit: false)
            updated.append(["uid": newEvent.calendarItemIdentifier, "summary": newEvent.title ?? "",
                            "updated_fields": updatedFields, "rescheduled": true])
        } catch {
            errors.append(["index": index, "uid": uid, "error": "Failed to create rescheduled event: \(error.localizedDescription)"])
        }
        continue
    }

    // Normal update path: apply field changes
    if let summary = updateData["summary"] as? String {
        event.title = summary; updatedFields.append("summary")
    }
    if let startDate = newStart {
        event.startDate = startDate; updatedFields.append("start_date")
    }
    if let endDate = newEnd {
        event.endDate = endDate; updatedFields.append("end_date")
    }
    if let location = updateData["location"] as? String {
        event.location = location; updatedFields.append("location")
    } else if updateData["clear_location"] as? Bool == true {
        event.location = nil; updatedFields.append("location")
    }
    if let slData = updateData["structured_location"] as? [String: Any] {
        let sl = EKStructuredLocation(title: slData["title"] as? String ?? "")
        if let lat = slData["latitude"] as? Double, let lon = slData["longitude"] as? Double {
            sl.geoLocation = CLLocation(latitude: lat, longitude: lon)
        }
        if let radius = slData["radius"] as? Double { sl.radius = radius }
        event.structuredLocation = sl
        if event.location == nil || event.location?.isEmpty == true { event.location = sl.title }
        updatedFields.append("structured_location")
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
        if let alerts = updateData["alerts"] as? [Any] {
            for alert in alerts {
                if let mins = alert as? Int {
                    event.addAlarm(EKAlarm(relativeOffset: TimeInterval(-mins * 60)))
                } else if let dict = alert as? [String: Any], let type = dict["type"] as? String {
                    switch type {
                    case "absolute":
                        if let dateStr = dict["date"] as? String, let date = parseISO8601(dateStr) {
                            event.addAlarm(EKAlarm(absoluteDate: date))
                        }
                    case "proximity":
                        if let proxStr = dict["proximity"] as? String, let sl = event.structuredLocation {
                            let alarm = EKAlarm()
                            alarm.structuredLocation = sl
                            alarm.proximity = proxStr == "leave" ? .leave : .enter
                            event.addAlarm(alarm)
                        }
                    default: break
                    }
                }
            }
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
    } else if let recDict = updateData["recurrence"] as? [String: Any], let rule = parseStructuredRecurrence(recDict) {
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

    // Determine save span: force futureEvents for recurrence changes
    let isRecurrenceChange = updateData["recurrence"] != nil || updateData["clear_recurrence"] as? Bool == true
    let saveSpan: EKSpan = isRecurrenceChange ? .futureEvents : span

    do {
        try store.save(event, span: saveSpan, commit: false)
        updated.append(["uid": uid, "summary": event.title ?? "", "updated_fields": updatedFields])
    } catch {
        errors.append(["index": index, "uid": uid, "error": error.localizedDescription])
    }
}

if !updated.isEmpty || errors.isEmpty {
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
