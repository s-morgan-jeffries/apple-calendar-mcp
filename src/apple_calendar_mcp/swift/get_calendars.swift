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

func cgColorToHex(_ cgColor: CGColor?) -> String {
    guard let color = cgColor,
          let components = color.components,
          components.count >= 3 else {
        return "#000000"
    }
    let r = Int(components[0] * 255)
    let g = Int(components[1] * 255)
    let b = Int(components[2] * 255)
    return String(format: "#%02X%02X%02X", r, g, b)
}

// MARK: - Main

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

store.refreshSourcesIfNecessary()

let calendars = store.calendars(for: .event)

func calendarTypeString(_ type: EKCalendarType) -> String {
    switch type {
    case .local: return "local"
    case .calDAV: return "caldav"
    case .exchange: return "exchange"
    case .subscription: return "subscription"
    case .birthday: return "birthday"
    @unknown default: return "unknown"
    }
}

let calendarDicts: [[String: Any]] = calendars.map { cal in
    [
        "name": cal.title,
        "writable": cal.allowsContentModifications,
        "description": (cal as EKCalendar).value(forKey: "notes") as? String ?? "",
        "color": cgColorToHex(cal.cgColor),
        "type": calendarTypeString(cal.type),
        "source": cal.source.title,
    ]
}

if let data = try? JSONSerialization.data(withJSONObject: calendarDicts, options: [.sortedKeys]),
   let str = String(data: data, encoding: .utf8) {
    print(str)
} else {
    outputError("serialization_error", "Failed to serialize calendars to JSON")
}
