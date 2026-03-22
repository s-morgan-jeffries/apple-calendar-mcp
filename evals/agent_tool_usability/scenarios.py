"""Blind agent eval scenarios for Apple Calendar MCP tool usability.

Each scenario tests whether an agent can correctly plan tool calls
based ONLY on tool descriptions (no codebase, no external knowledge).
"""

SCENARIOS = [
    # =========================================================================
    # Category 1: Calendar Discovery
    # =========================================================================
    {
        "id": 1,
        "category": "Calendar Discovery",
        "name": "List all calendars",
        "prompt": "What calendars do I have?",
        "expected": {
            "tools": ["get_calendars"],
            "key_params": {
                "get_calendars": {}
            },
        },
        "scoring_notes": (
            "PASS: Calls get_calendars() with no arguments and presents results. "
            "FAIL: Calls get_events or another tool instead."
        ),
        "safety_critical": False,
    },
    {
        "id": 2,
        "category": "Calendar Discovery",
        "name": "Find writable calendars",
        "prompt": "Which calendars can I add events to?",
        "expected": {
            "tools": ["get_calendars"],
            "key_params": {
                "get_calendars": {}
            },
        },
        "scoring_notes": (
            "PASS: Calls get_calendars() and filters results by writable/read-write status. "
            "PARTIAL: Calls get_calendars but doesn't filter for writable. "
            "FAIL: Doesn't call get_calendars."
        ),
        "safety_critical": False,
    },
    {
        "id": 3,
        "category": "Calendar Discovery",
        "name": "Disambiguate duplicate calendar names",
        "prompt": "I have two calendars called 'Family'. Which is which?",
        "expected": {
            "tools": ["get_calendars"],
            "key_params": {
                "get_calendars": {}
            },
        },
        "scoring_notes": (
            "PASS: Calls get_calendars() and uses account or notes fields to distinguish. "
            "FAIL: Doesn't reference distinguishing information or picks one blindly."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 2: Event Queries
    # =========================================================================
    {
        "id": 4,
        "category": "Event Queries",
        "name": "Basic daily schedule query",
        "prompt": "What's on my Work calendar today?",
        "expected": {
            "tools": ["get_calendars", "get_events"],
            "key_params": {
                "get_events": {
                    "calendar_names": "Work",
                    "start_date": "2026-03-20T00:00:00",
                    "end_date": "2026-03-21T00:00:00",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses correct ISO 8601 dates for a single day, queries Work calendar. "
            "PARTIAL: Correct tool but date range too wide (week/month). "
            "FAIL: Doesn't call get_events or uses wrong calendar name."
        ),
        "safety_critical": False,
    },
    {
        "id": 5,
        "category": "Event Queries",
        "name": "Multi-day range query",
        "prompt": "Show me my Personal events for next week, March 23 through 29.",
        "expected": {
            "tools": ["get_events"],
            "key_params": {
                "get_events": {
                    "calendar_names": "Personal",
                    "start_date": "2026-03-23T00:00:00",
                    "end_date": "2026-03-30T00:00:00",
                }
            },
        },
        "scoring_notes": (
            "PASS: end_date is day AFTER the last requested day (March 30, exclusive end). "
            "PARTIAL: end_date is March 29 (misses events on the last day). "
            "FAIL: Wrong calendar or wildly wrong dates."
        ),
        "safety_critical": False,
    },
    {
        "id": 6,
        "category": "Event Queries",
        "name": "Disambiguating calendars before query",
        "prompt": "Do I have anything on my Family calendar this weekend?",
        "expected": {
            "tools": ["get_calendars", "get_events"],
            "key_params": {
                "get_events": {
                    "calendar_names": "Family",
                }
            },
        },
        "scoring_notes": (
            "PASS: Calls get_calendars, discovers two 'Family' calendars, asks for "
            "clarification or uses notes/account info to disambiguate. "
            "PARTIAL: Calls get_events on 'Family' without checking for duplicates. "
            "FAIL: Doesn't call get_calendars first."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 3: Event Creation
    # =========================================================================
    {
        "id": 7,
        "category": "Event Creation",
        "name": "Create a basic timed event",
        "prompt": (
            "Add a meeting called 'Team Standup' tomorrow at 10am for 30 minutes "
            "on my Work calendar."
        ),
        "expected": {
            "tools": ["get_calendars", "create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with a 1-element array containing correct summary, "
            "ISO 8601 dates, and 30min duration. "
            "PARTIAL: Correct but missing get_calendars verification. "
            "FAIL: Wrong duration or missing required fields."
        ),
        "safety_critical": False,
    },
    {
        "id": 8,
        "category": "Event Creation",
        "name": "Create an all-day event",
        "prompt": "Block off next Friday March 27 as a holiday on my Personal calendar.",
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Personal",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with allday=true, date-only format. "
            "PARTIAL: allday=true but end date same as start. "
            "FAIL: Doesn't set allday=true."
        ),
        "safety_critical": False,
    },
    {
        "id": 9,
        "category": "Event Creation",
        "name": "Create event with all optional fields",
        "prompt": (
            "Create a lunch meeting on my Work calendar next Tuesday March 24 at noon "
            "for an hour at 'Cafe Roma', with a note 'Discuss Q3 roadmap' and link to "
            "https://docs.example.com/q3."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with all optional fields — location, notes, and url. "
            "PARTIAL: Missing one optional field. "
            "FAIL: Missing two or more optional fields or uses 'description' instead of 'notes'."
        ),
        "safety_critical": False,
    },
    {
        "id": 10,
        "category": "Event Creation",
        "name": "Create event on ambiguous calendar",
        "prompt": "Add a birthday party on Saturday to my Family calendar.",
        "expected": {
            "tools": ["get_calendars", "create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Family",
                }
            },
        },
        "scoring_notes": (
            "PASS: Calls get_calendars first, detects duplicate 'Family' names, asks for "
            "clarification or uses notes/account to disambiguate. "
            "PARTIAL: Creates event but warns about possible duplicates. "
            "FAIL: Blindly picks one without checking."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 4: Recurrence
    # =========================================================================
    {
        "id": 11,
        "category": "Recurrence",
        "name": "Weekly recurring with BYDAY",
        "prompt": (
            "Set up a recurring meeting called 'Sprint Planning' every Monday and "
            "Wednesday at 2pm for an hour on my Work calendar."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with valid RRULE containing FREQ=WEEKLY and BYDAY=MO,WE. "
            "PARTIAL: RRULE has FREQ=WEEKLY but missing one day. "
            "FAIL: No recurrence or wrong frequency."
        ),
        "safety_critical": False,
    },
    {
        "id": 12,
        "category": "Recurrence",
        "name": "Monthly nth weekday recurrence",
        "prompt": (
            "Create a recurring event called 'Board Meeting' on the 4th Tuesday of every "
            "month at 3pm for 2 hours on my Work calendar."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with RRULE containing FREQ=MONTHLY and BYDAY=4TU. "
            "PARTIAL: Correct frequency but wrong BYDAY syntax. "
            "FAIL: No recurrence or wrong frequency."
        ),
        "safety_critical": False,
    },
    {
        "id": 13,
        "category": "Recurrence",
        "name": "Weekly with UNTIL date",
        "prompt": (
            "I need a weekly team lunch every Friday starting this week until Christmas "
            "on my Work calendar. 12pm to 1pm."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with RRULE containing FREQ=WEEKLY, BYDAY=FR, and UNTIL near Dec 25 2026. "
            "PARTIAL: Missing UNTIL or wrong date format. "
            "FAIL: Wrong frequency or day."
        ),
        "safety_critical": False,
    },
    {
        "id": 14,
        "category": "Recurrence",
        "name": "Last weekday of month",
        "prompt": (
            "Schedule 'Month-End Review' on the last Friday of every month at 4pm for "
            "1 hour on Work, for the next 6 months."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with RRULE containing BYDAY=-1FR and COUNT=6 or appropriate UNTIL. "
            "PARTIAL: Correct BYDAY but missing COUNT/UNTIL. "
            "FAIL: Wrong BYDAY syntax (e.g., 4FR instead of -1FR)."
        ),
        "safety_critical": False,
    },
    {
        "id": 15,
        "category": "Recurrence",
        "name": "Every N months (quarterly)",
        "prompt": (
            "Set up a quarterly planning session — every 3 months on the 2nd Wednesday, "
            "starting next month, for 3 hours. Put it on Work."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with RRULE containing FREQ=MONTHLY, INTERVAL=3, BYDAY=2WE. "
            "PARTIAL: Missing INTERVAL or wrong nth weekday. "
            "FAIL: Uses FREQ=YEARLY or no recurrence."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 5: Batch Operations
    # =========================================================================
    {
        "id": 16,
        "category": "Batch Operations",
        "name": "Batch create multiple events",
        "prompt": (
            "Add three meetings to my Work calendar next week: Team Standup Monday "
            "March 23 at 9-9:30am, Design Review Monday at 2-3pm, and Sprint Planning "
            "Tuesday March 24 at 10-11am."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events (batch) with 3 events, correct summaries and times. "
            "PARTIAL: Uses three separate create_event calls instead. "
            "FAIL: Missing events or wrong times."
        ),
        "safety_critical": False,
    },
    {
        "id": 17,
        "category": "Batch Operations",
        "name": "Single event uses create_events",
        "prompt": "Add a dentist appointment to my Personal calendar on Friday at 2pm for an hour.",
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Personal",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with a 1-element array. "
            "FAIL: Tries to call a non-existent create_event tool."
        ),
        "safety_critical": False,
    },
    {
        "id": 18,
        "category": "Batch Operations",
        "name": "Conference schedule with mixed fields",
        "prompt": (
            "Here's a conference schedule for Thursday March 26. Add all to Work: "
            "Opening Keynote 9-10am, Workshop A 10:15-11:45am at Room 101, "
            "Lunch 12-1pm (mark as free), Workshop B 1:15-2:45pm at Room 203, "
            "Closing Panel 3-4pm."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with 5 events, locations on workshops, "
            "availability='free' on lunch. "
            "PARTIAL: Correct batch but missing locations or availability. "
            "FAIL: Uses individual create_event calls or missing events."
        ),
        "safety_critical": False,
    },
    {
        "id": 19,
        "category": "Batch Operations",
        "name": "Batch with mixed event types",
        "prompt": (
            "Add to my Work calendar: Weekly Team Sync every Monday 10-11am recurring "
            "weekly, a one-time Project Kickoff on Wednesday March 25 at 2-4pm with a "
            "30-minute alert, and an All-Day Planning Day on Friday March 27."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Batch with recurrence RRULE on first event, alerts=[30] on second, "
            "allday=true on third. "
            "PARTIAL: Correct batch but missing one feature (recurrence, alert, or allday). "
            "FAIL: Uses individual calls or missing events."
        ),
        "safety_critical": False,
    },
    {
        "id": 20,
        "category": "Batch Operations",
        "name": "Timezone-specific batch create",
        "prompt": (
            "I'm scheduling meetings with our West Coast team. Add these to Work — "
            "all times are Pacific: Sync Call Monday March 23 at 9am-10am, "
            "Follow-Up Tuesday March 24 at 2pm-3pm."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                    "timezone": "America/Los_Angeles",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with timezone='America/Los_Angeles' or similar Pacific TZ. "
            "PARTIAL: Correct batch but converts times manually instead of using timezone param. "
            "FAIL: Ignores timezone entirely."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 6: Event Updates
    # =========================================================================
    {
        "id": 21,
        "category": "Event Updates",
        "name": "Simple field update (rename)",
        "prompt": "Change the title of my 2pm meeting today to 'Project Review'.",
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {
                    "summary": "Project Review",
                }
            },
        },
        "scoring_notes": (
            "PASS: Calls get_events to find UID, then update_events with only summary changed. "
            "PARTIAL: Correct tools but modifies extra fields unnecessarily. "
            "FAIL: Fabricates a UID or uses delete+create."
        ),
        "safety_critical": False,
    },
    {
        "id": 22,
        "category": "Event Updates",
        "name": "Update location (not time)",
        "prompt": "Move my 'Team Standup' event to Conference Room B.",
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {
                    "location": "Conference Room B",
                }
            },
        },
        "scoring_notes": (
            "PASS: Interprets 'move' as location change, updates only location field. "
            "FAIL: Modifies start_date/end_date (misinterprets 'move' as reschedule)."
        ),
        "safety_critical": False,
    },
    {
        "id": 23,
        "category": "Event Updates",
        "name": "Clear a field",
        "prompt": "Remove the location from my dentist appointment.",
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {}
            },
        },
        "scoring_notes": (
            "PASS: Uses clear_location=true or passes location='' (empty string) to clear. "
            "FAIL: Omits location param (doesn't clear) or uses None."
        ),
        "safety_critical": False,
    },
    {
        "id": 24,
        "category": "Event Updates",
        "name": "Reschedule preserving duration",
        "prompt": "Move my 10am meeting to 3pm today.",
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {
                    "start_date": "2026-03-20T15:00:00",
                    "end_date": "2026-03-20T16:00:00",
                }
            },
        },
        "scoring_notes": (
            "PASS: Updates BOTH start_date and end_date, preserves original duration. "
            "PARTIAL: Updates start_date only (end_date not adjusted). "
            "FAIL: Uses delete+create instead of update_events."
        ),
        "safety_critical": False,
    },
    {
        "id": 25,
        "category": "Event Updates",
        "name": "Make event recurring",
        "prompt": "Make my 'Team Sync' event on Monday repeat every week.",
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {
                    "recurrence_rule": "FREQ=WEEKLY",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses recurrence_rule param with valid RRULE (FREQ=WEEKLY or FREQ=WEEKLY;BYDAY=MO). "
            "FAIL: Tries delete+recreate instead of update, or no recurrence_rule."
        ),
        "safety_critical": False,
    },
    {
        "id": 26,
        "category": "Event Updates",
        "name": "Change recurrence interval",
        "prompt": (
            "My 'Status Update' meeting currently repeats weekly. Change it to every "
            "two weeks instead."
        ),
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {
                    "recurrence_rule": "FREQ=WEEKLY;INTERVAL=2",
                }
            },
        },
        "scoring_notes": (
            "PASS: RRULE includes FREQ=WEEKLY and INTERVAL=2. "
            "PARTIAL: Correct approach but wrong INTERVAL. "
            "FAIL: Tries delete+recreate."
        ),
        "safety_critical": False,
    },
    {
        "id": 27,
        "category": "Event Updates",
        "name": "Remove recurrence",
        "prompt": "Stop my 'Daily Standup' from repeating. Just keep the next occurrence.",
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {}
            },
        },
        "scoring_notes": (
            "PASS: Uses clear_recurrence=true or passes recurrence='' (empty string) to clear. "
            "FAIL: Omits recurrence param (doesn't clear) or tries delete+recreate."
        ),
        "safety_critical": False,
    },
    {
        "id": 28,
        "category": "Event Updates",
        "name": "Add complex recurrence to existing event",
        "prompt": (
            "Make my 'Quarterly Review' event repeat every 3 months on the 2nd Thursday "
            "until the end of 2027."
        ),
        "expected": {
            "tools": ["get_events", "update_events"],
            "key_params": {
                "update_events": {
                    "recurrence_rule": "FREQ=MONTHLY;INTERVAL=3;BYDAY=2TH;UNTIL=20271231",
                }
            },
        },
        "scoring_notes": (
            "PASS: RRULE has FREQ=MONTHLY, INTERVAL=3, BYDAY=2TH, and UNTIL near end of 2027. "
            "PARTIAL: Missing one RRULE component. "
            "FAIL: Wrong frequency or tries delete+recreate."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 7: Event Deletion
    # =========================================================================
    {
        "id": 29,
        "category": "Event Deletion",
        "name": "Delete single event by UID",
        "prompt": "Delete the event with UID ABC-123 from my Work calendar.",
        "expected": {
            "tools": ["delete_events"],
            "key_params": {
                "delete_events": {
                    "calendar_name": "Work",
                    "event_uids": "ABC-123",
                }
            },
        },
        "scoring_notes": (
            "PASS: Passes UID as string with correct calendar_name. "
            "FAIL: Wrong calendar or fabricated UID."
        ),
        "safety_critical": True,
    },
    {
        "id": 30,
        "category": "Event Deletion",
        "name": "Delete multiple events in batch",
        "prompt": (
            "Delete all three of my test events from Work: ABC-123, DEF-456, GHI-789."
        ),
        "expected": {
            "tools": ["delete_events"],
            "key_params": {
                "delete_events": {
                    "calendar_name": "Work",
                    "event_uids": ["ABC-123", "DEF-456", "GHI-789"],
                }
            },
        },
        "scoring_notes": (
            "PASS: Single call with list of UIDs. "
            "PARTIAL: Three separate delete_events calls. "
            "FAIL: Missing UIDs or wrong calendar."
        ),
        "safety_critical": True,
    },
    {
        "id": 31,
        "category": "Event Deletion",
        "name": "Find and delete by name",
        "prompt": "Cancel my dentist appointment next Tuesday.",
        "expected": {
            "tools": ["get_events", "delete_events"],
            "key_params": {
                "delete_events": {
                    "event_uids": "<discovered_uid>",
                }
            },
        },
        "scoring_notes": (
            "PASS: Calls get_events first to find UID, then delete_events with discovered UID. "
            "FAIL: Fabricates a UID without searching first."
        ),
        "safety_critical": True,
    },
    {
        "id": 32,
        "category": "Event Deletion",
        "name": "Handle partial delete failure",
        "prompt": "Delete events ABC-123 and DEF-456 from my Work calendar.",
        "expected": {
            "tools": ["delete_events"],
            "key_params": {
                "delete_events": {
                    "calendar_name": "Work",
                    "event_uids": ["ABC-123", "DEF-456"],
                }
            },
        },
        "scoring_notes": (
            "PASS: Single call with list of UIDs; reports partial success clearly if some fail. "
            "FAIL: Retries not-found UIDs or doesn't inform user of partial failure."
        ),
        "safety_critical": True,
    },

    # =========================================================================
    # Category 8: Multi-Step Workflows
    # =========================================================================
    {
        "id": 33,
        "category": "Multi-Step Workflows",
        "name": "Weekly calendar batch with mixed operations",
        "prompt": (
            "Here's my week: cancel Monday's standup, move Tuesday's 1:1 to 3pm, "
            "add a Wednesday lunch with Sarah at noon on my Work calendar, and delete "
            "Thursday's 'TBD' placeholder."
        ),
        "expected": {
            "tools": [
                "get_events", "delete_events", "update_events",
                "create_events", "delete_events",
            ],
            "key_params": {
                "update_events": {
                    "start_date": "2026-03-24T15:00:00",
                },
                "create_events": {
                    "calendar_name": "Work",
                },
            },
        },
        "scoring_notes": (
            "PASS: Calls get_events first to find UIDs, then uses correct tools for each "
            "operation (delete, update, create_events, delete). "
            "PARTIAL: Correct tools but skips get_events (guesses UIDs). "
            "FAIL: Tries to create/update without finding UIDs first."
        ),
        "safety_critical": True,
    },
    {
        "id": 34,
        "category": "Multi-Step Workflows",
        "name": "Availability negotiation",
        "prompt": (
            "I need to find a 90-minute slot this week for a planning session. Check my "
            "Work and Personal calendars, but only during business hours 9-5."
        ),
        "expected": {
            "tools": ["get_availability"],
            "key_params": {
                "get_availability": {
                    "calendar_names": ["Work", "Personal"],
                    "min_duration_minutes": 90,
                    "working_hours_start": "09:00",
                    "working_hours_end": "17:00",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses get_availability with both calendars and all filters "
            "(min_duration, working_hours_start, working_hours_end). "
            "PARTIAL: Missing one filter (e.g., only one calendar or no min_duration). "
            "FAIL: Uses get_events instead of get_availability."
        ),
        "safety_critical": False,
    },
    {
        "id": 35,
        "category": "Multi-Step Workflows",
        "name": "Mid-stream corrections",
        "prompt": (
            "Create a team dinner event next Friday at 7pm... actually make that 7:30pm, "
            "and add it to Personal not Work."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Personal",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with corrected time (19:30) and calendar (Personal). "
            "PARTIAL: Correct calendar but wrong time, or vice versa. "
            "FAIL: Uses initial values (19:00 or Work)."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 9: Batch Operations (new)
    # =========================================================================
    {
        "id": 36,
        "category": "Batch Operations",
        "name": "Conference import with locations and durations",
        "prompt": (
            "Add these conference sessions to my Work calendar for next Monday March 23: "
            "9am Keynote (1h, Main Hall), 10:30am 'API Design' (45min, Room B), "
            "1pm 'Testing Strategies' (1h, Room A), 3pm Panel Discussion (1.5h, Main Hall)."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events (batch) with 4 events, correct durations "
            "(1h, 45min, 1h, 1.5h) and locations (Main Hall, Room B, Room A, Main Hall). "
            "PARTIAL: Uses individual create_event calls. "
            "FAIL: Wrong durations or missing locations."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 10: Recurrence (new)
    # =========================================================================
    {
        "id": 37,
        "category": "Recurrence",
        "name": "Natural language to biweekly RRULE",
        "prompt": (
            "Set up a team sync every other Wednesday at 2pm for 30 minutes, starting "
            "next week, for 12 weeks."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with RRULE containing all 4 components: "
            "FREQ=WEEKLY, INTERVAL=2, BYDAY=WE, COUNT=6 (6 occurrences over 12 weeks). "
            "PARTIAL: Missing COUNT or INTERVAL, or uses COUNT=12 (wrong math). "
            "FAIL: Wrong frequency or wrong day."
        ),
        "safety_critical": False,
    },

    # =========================================================================
    # Category 11: Parameter Usage
    # =========================================================================
    {
        "id": 38,
        "category": "Parameter Usage",
        "name": "Timezone handling for remote office",
        "prompt": (
            "Schedule a call with the Tokyo office at 9am their time next Tuesday. "
            "I'm in US Pacific."
        ),
        "expected": {
            "tools": ["create_events"],
            "key_params": {
                "create_events": {
                    "calendar_name": "Work",
                }
            },
        },
        "scoring_notes": (
            "PASS: Uses create_events with timezone='Asia/Tokyo' and 09:00 start. "
            "PARTIAL: Converts to local Pacific time manually (e.g., 4pm or 5pm PT). "
            "FAIL: Ignores timezone entirely or uses wrong timezone identifier."
        ),
        "safety_critical": False,
    },
]
