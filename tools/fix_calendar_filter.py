#!/usr/bin/env python3
"""Repair native Calendar and Clock metadata lost by Cherri v2.3.0."""

import pathlib
import plistlib
import sys


def main() -> None:
    path = pathlib.Path(sys.argv[1])
    shortcut = plistlib.loads(path.read_bytes())
    actions = shortcut["WFWorkflowActions"]
    matches = [a for a in actions if a["WFWorkflowActionIdentifier"] == "is.workflow.actions.filter.calendarevents"]
    if len(matches) != 2:
        raise SystemExit(f"Expected two Find Calendar Events actions, found {len(matches)}")
    by_output = {
        action["WFWorkflowActionParameters"].get("CustomOutputName"): action
        for action in matches
    }
    if set(by_output) != {"testCalendarEvents", "currentCalendarEvents"}:
        raise SystemExit(f"Unexpected calendar outputs: {sorted(by_output)}")
    params = by_output["currentCalendarEvents"]["WFWorkflowActionParameters"]
    # Reproduce the native Find Calendar Events predicates from the user's
    # working iCloud shortcut. This asks EventKit for a currently active
    # special-day event instead of fetching an unbounded calendar and trying
    # to reproduce EventKit's all-day end-date semantics ourselves.
    params["WFContentItemFilter"] = {
        "Value": {
            "WFActionParameterFilterPrefix": 1,
            "WFActionParameterFilterTemplates": [
                {
                    "Bounded": True,
                    "Property": "Start Date",
                    "Operator": 1001,
                    "Values": {"Number": "10", "Unit": 16},
                    "Removable": False,
                },
                {
                    "Property": "Calendar",
                    "Operator": 4,
                    "Values": {
                        "Enumeration": {
                            "Value": "中国大陆节假日",
                            "WFSerializationType": "WFStringSubstitutableState",
                        }
                    },
                    "Removable": True,
                },
                {
                    "Property": "End Date",
                    "Operator": 2,
                    "Values": {
                        "Date": {
                            "Value": {"Type": "CurrentDate"},
                            "WFSerializationType": "WFTextTokenAttachment",
                        }
                    },
                    "Removable": True,
                },
            ],
            "WFContentPredicateBoundedDate": False,
        },
        "WFSerializationType": "WFContentPredicateTableTemplate",
    }
    params.pop("WFContentItemLimitNumber", None)
    params["WFContentItemLimitEnabled"] = False

    test_params = by_output["testCalendarEvents"]["WFWorkflowActionParameters"]

    def action_output(name: str) -> dict:
        action = next(
            (
                item
                for item in actions
                if item.get("WFWorkflowActionParameters", {}).get("CustomOutputName")
                == name
            ),
            None,
        )
        if action is None:
            raise SystemExit(f"Missing action output: {name}")
        output_uuid = action["WFWorkflowActionParameters"].get("UUID")
        if not output_uuid:
            raise SystemExit(f"Missing UUID for action output: {name}")
        return {
            "Value": {
                "OutputName": name,
                "OutputUUID": output_uuid,
                "Type": "ActionOutput",
            },
            "WFSerializationType": "WFTextTokenAttachment",
        }

    test_params["WFContentItemFilter"] = {
        "Value": {
            "WFActionParameterFilterPrefix": 1,
            "WFActionParameterFilterTemplates": [
                {
                    "Property": "Start Date",
                    "Operator": 1003,
                    "Values": {
                        "Date": action_output("testQueryStartDate"),
                        "AnotherDate": action_output("testQueryEndDate"),
                    },
                    "Removable": True,
                },
                {
                    "Property": "Calendar",
                    "Operator": 4,
                    "Values": {
                        "Enumeration": {
                            "Value": "中国大陆节假日",
                            "WFSerializationType": "WFStringSubstitutableState",
                        }
                    },
                    "Removable": True,
                },
            ],
            "WFContentPredicateBoundedDate": False,
        },
        "WFSerializationType": "WFContentPredicateTableTemplate",
    }
    test_params.pop("WFContentItemLimitNumber", None)
    test_params["WFContentItemLimitEnabled"] = False

    # Apple-created Find Alarms actions carry this descriptor. Without it the
    # action may import but fail to return the alarm entities on iPhone.
    alarm_getters = [
        action for action in actions
        if action["WFWorkflowActionIdentifier"]
        == "com.apple.mobiletimer-framework.MobileTimerIntents.MTGetAlarmsIntent"
    ]
    if len(alarm_getters) != 1:
        raise SystemExit(f"Expected one Find Alarms action, found {len(alarm_getters)}")
    alarm_getters[0]["WFWorkflowActionParameters"]["AppIntentDescriptor"] = {
        "TeamIdentifier": "0000000000",
        "BundleIdentifier": "com.apple.mobiletimer",
        "Name": "Clock",
        "AppIntentIdentifier": "AlarmEntity",
        "ActionRequiresAppInstallation": True,
    }

    # Cherri v2.3.0 points MobileTimer framework actions at com.apple.clock.
    # Native actions from the user's working shortcut point at the actual
    # provider, com.apple.mobiletimer. A mismatched provider imports as
    # “Unknown Action”, even though the action identifier itself is correct.
    mobiletimer_intents = {
        "com.apple.mobiletimer-framework.MobileTimerIntents.MTToggleAlarmIntent":
            "ToggleAlarmIntent",
        "com.apple.mobiletimer-framework.MobileTimerIntents.MTCreateAlarmIntent":
            "CreateAlarmIntent",
    }
    repaired_mobiletimer_actions = 0
    for action in actions:
        intent = mobiletimer_intents.get(action["WFWorkflowActionIdentifier"])
        if intent is None:
            continue
        action["WFWorkflowActionParameters"]["AppIntentDescriptor"] = {
            "TeamIdentifier": "0000000000",
            "BundleIdentifier": "com.apple.mobiletimer",
            "Name": "时钟",
            "AppIntentIdentifier": intent,
        }
        repaired_mobiletimer_actions += 1
    if repaired_mobiletimer_actions != 5:
        raise SystemExit(
            "Expected four toggle actions and one create action, found "
            f"{repaired_mobiletimer_actions}"
        )

    # Delete Alarm is provided by the newer com.apple.clock action namespace,
    # so its identifier and descriptor must remain paired with that provider.
    delete_actions = [
        action for action in actions
        if action["WFWorkflowActionIdentifier"] == "com.apple.clock.DeleteAlarmIntent"
    ]
    if len(delete_actions) != 1:
        raise SystemExit(f"Expected one Delete Alarm action, found {len(delete_actions)}")
    delete_actions[0]["WFWorkflowActionParameters"]["AppIntentDescriptor"] = {
        "TeamIdentifier": "0000000000",
        "BundleIdentifier": "com.apple.clock",
        "Name": "Clock",
        "AppIntentIdentifier": "DeleteAlarmIntent",
    }

    label_reads = 0
    for action in actions:
        for value in action.get("WFWorkflowActionParameters", {}).values():
            if not isinstance(value, dict) or not isinstance(value.get("Value"), dict):
                continue
            for item in value["Value"].get("Aggrandizements", []):
                if item.get("Type") != "WFPropertyVariableAggrandizement" or item.get("PropertyName") != "label":
                    continue
                item["PropertyUserInfo"] = {
                    "WFLinkEntityContentPropertyUserInfoPropertyIdentifier": "label"
                }
                label_reads += 1
    if label_reads != 2:
        raise SystemExit(f"Expected two alarm label reads, found {label_reads}")

    path.write_bytes(plistlib.dumps(shortcut, fmt=plistlib.FMT_XML, sort_keys=False))


if __name__ == "__main__":
    main()
