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
    if len(matches) != 1:
        raise SystemExit(f"Expected one Find Calendar Events action, found {len(matches)}")
    params = matches[0]["WFWorkflowActionParameters"]
    params["WFContentItemFilter"] = {
        "Value": {
            "WFActionParameterFilterPrefix": 1,
            "WFActionParameterFilterTemplates": [
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
                }
            ],
            "WFContentPredicateBoundedDate": False,
        },
        "WFSerializationType": "WFContentPredicateTableTemplate",
    }
    params.pop("WFContentItemLimitNumber", None)
    params["WFContentItemLimitEnabled"] = False

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
