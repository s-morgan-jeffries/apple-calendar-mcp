import EventKit
import Foundation

// MARK: - JSON Output

func outputError(_ error: String, _ message: String) {
    let obj: [String: String] = ["error": error, "message": message]
    if let data = try? JSONSerialization.data(withJSONObject: obj),
       let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

// MARK: - Argument Parsing

struct CreateCalendarArgs {
    var name: String = ""
    var source: String = ""  // optional: source/account name
}

func parseArgs() -> CreateCalendarArgs {
    var result = CreateCalendarArgs()
    let args = CommandLine.arguments
    var i = 1
    while i < args.count {
        switch args[i] {
        case "--name":
            i += 1; if i < args.count { result.name = args[i] }
        case "--source":
            i += 1; if i < args.count { result.source = args[i] }
        default:
            break
        }
        i += 1
    }
    return result
}

// MARK: - Main

let parsed = parseArgs()

guard !parsed.name.isEmpty else {
    outputError("invalid_args", "Required: --name <calendar_name>")
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

// Build list of sources to try
var sourcesToTry: [EKSource] = []

if !parsed.source.isEmpty {
    // User specified a source — try only that one
    guard let source = store.sources.first(where: { $0.title == parsed.source }) else {
        outputError("source_not_found", "Source '\(parsed.source)' not found. Use get_calendars to see available sources.")
        exit(1)
    }
    sourcesToTry = [source]
} else {
    // Auto-select: prefer local, then iCloud, then other CalDAV, then any
    if let local = store.sources.first(where: { $0.sourceType == .local }) {
        sourcesToTry.append(local)
    }
    if let icloud = store.sources.first(where: { $0.title == "iCloud" && $0.sourceType == .calDAV }) {
        sourcesToTry.append(icloud)
    }
    sourcesToTry += store.sources.filter { $0.sourceType == .calDAV && !sourcesToTry.contains($0) }
    sourcesToTry += store.sources.filter { !sourcesToTry.contains($0) }
}

// Try each source until one works
var savedCalendar: EKCalendar?
var lastError: Error?

for source in sourcesToTry {
    let calendar = EKCalendar(for: .event, eventStore: store)
    calendar.title = parsed.name
    calendar.source = source
    do {
        try store.saveCalendar(calendar, commit: true)
        savedCalendar = calendar
        break
    } catch {
        lastError = error
        continue
    }
}

guard let calendar = savedCalendar else {
    let msg = lastError?.localizedDescription ?? "No writable calendar source available."
    outputError("save_failed", "Failed to create calendar: \(msg)")
    exit(1)
}

// Output result
let result: [String: Any] = [
    "calendar_id": calendar.calendarIdentifier,
    "name": calendar.title,
    "source": calendar.source.title,
]

if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
}
