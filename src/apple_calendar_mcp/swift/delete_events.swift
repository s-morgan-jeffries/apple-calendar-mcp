import EventKit
import Foundation

// MARK: - Argument Parsing

struct DeleteEventsArgs {
    var calendarId: String = ""
    var uids: [String] = []
    var span: EKSpan = .thisEvent
    var occurrenceDate: String?
}

func parseArgs() -> DeleteEventsArgs? {
    var result = DeleteEventsArgs()
    let args = CommandLine.arguments

    var i = 1
    while i < args.count {
        switch args[i] {
        case "--calendar-id":
            i += 1; if i < args.count { result.calendarId = args[i] }
        case "--uid":
            i += 1; if i < args.count { result.uids.append(args[i]) }
        case "--span":
            i += 1; if i < args.count { result.span = args[i] == "future_events" ? .futureEvents : .thisEvent }
        case "--occurrence-date":
            i += 1; if i < args.count { result.occurrenceDate = args[i] }
        default:
            break
        }
        i += 1
    }

    guard !result.calendarId.isEmpty, !result.uids.isEmpty else {
        return nil
    }
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
    outputError("invalid_args", "Required: --calendar <name> --uid <uid> [--uid <uid> ...]")
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

// Delete events by UID
var deletedUids: [String] = []
var notFoundUids: [String] = []

for uid in parsed.uids {
    var matches: [EKEvent] = []

    // If occurrence_date provided, use predicate-based lookup (for recurring events)
    if let occDateStr = parsed.occurrenceDate, let occDate = parseISO8601(occDateStr) {
        let dayBefore = occDate.addingTimeInterval(-86400)
        let dayAfter = occDate.addingTimeInterval(86400)
        let pred = store.predicateForEvents(withStart: dayBefore, end: dayAfter, calendars: [calendar])
        let tolerance: TimeInterval = 60
        matches = store.events(matching: pred)
            .filter { $0.calendarItemIdentifier == uid && abs($0.occurrenceDate.timeIntervalSince(occDate)) < tolerance }
    } else {
        // No occurrence date: use calendarItems lookup
        let items = store.calendarItems(withExternalIdentifier: uid)
        matches = items.compactMap { $0 as? EKEvent }.filter { $0.calendar.calendarIdentifier == parsed.calendarId }
    }

    if matches.isEmpty {
        notFoundUids.append(uid)
    } else {
        do {
            if parsed.span == .futureEvents {
                try store.remove(matches.first!, span: .futureEvents, commit: false)
            } else {
                for event in matches {
                    try store.remove(event, span: .thisEvent, commit: false)
                }
            }
            deletedUids.append(uid)
        } catch {
            notFoundUids.append(uid)
        }
    }
}

// Commit all deletions at once
if !deletedUids.isEmpty {
    do {
        try store.commit()
    } catch {
        outputError("delete_failed", "Failed to commit deletions: \(error.localizedDescription)")
        exit(1)
    }
}

// Output result
let result: [String: Any] = [
    "deleted_uids": deletedUids,
    "not_found_uids": notFoundUids,
]

if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize result to JSON")
}
