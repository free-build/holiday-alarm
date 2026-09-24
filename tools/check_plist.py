#!/usr/bin/env python3
"""Audit the shortcut that will actually be signed."""
import pathlib
import plistlib
import sys

path = pathlib.Path(sys.argv[1])
p = plistlib.loads(path.read_bytes())
actions = p['WFWorkflowActions']
ids = [a['WFWorkflowActionIdentifier'] for a in actions]
assert len(actions) > 100, len(actions)
assert ids.count('is.workflow.actions.filter.calendarevents') == 1
assert not any('downloadurl' in item or 'geturl' in item or 'rawaction' in item for item in ids)
query = actions[ids.index('is.workflow.actions.filter.calendarevents')]
params = query['WFWorkflowActionParameters']
assert params['WFContentItemLimitEnabled'] is False
filt = params['WFContentItemFilter']
assert filt['WFSerializationType'] == 'WFContentPredicateTableTemplate'
templates = filt['Value']['WFActionParameterFilterTemplates']
assert len(templates) == 1
t = templates[0]
assert (t['Property'], t['Operator'], t['Values']['Enumeration']['Value']) == ('Calendar', 4, '中国大陆节假日')
assert 'WFDictionaryFieldValueItems' not in str(filt)

# v4.4 must retain seconds when comparing calendar ranges. EventKit may expose
# an all-day event end as either 23:59:59 on the same day or 00:00:00 on the
# following day; reducing it to yyyyMMdd loses the distinction.
date_formats = [
    action['WFWorkflowActionParameters'].get('WFDateFormat')
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.format.date'
]
assert date_formats.count('yyyyMMddHHmmss') == 2, date_formats
range_conditions = [
    action['WFWorkflowActionParameters']['WFConditions']['Value'][
        'WFActionParameterFilterTemplates'
    ]
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.conditional'
    and 'WFConditions' in action.get('WFWorkflowActionParameters', {})
]
assert len(range_conditions) == 1
range_conditions = range_conditions[0]
assert [item['WFCondition'] for item in range_conditions] == [1, 2]
assert [
    item['WFInput']['Variable']['Value']['VariableName']
    for item in range_conditions
] == ['startN', 'endN']
assert [
    item['WFNumberValue']['Value']['VariableName']
    for item in range_conditions
] == ['todayEndN', 'todayStartN']

def overlaps_today(start: int, end: int, day: int = 20260925) -> bool:
    return start <= int(f'{day}235959') and end > int(f'{day}000000')

assert overlaps_today(20260925000000, 20260925235959)  # modern EventKit
assert overlaps_today(20260925000000, 20260926000000)  # legacy exclusive end
assert not overlaps_today(20260924000000, 20260925000000)
assert not overlaps_today(20260926000000, 20260926235959)
assert ids.count('com.apple.mobiletimer-framework.MobileTimerIntents.MTCreateAlarmIntent') == 1
assert ids.count('com.apple.clock.DeleteAlarmIntent') == 1
get_alarms = [
    action for action in actions
    if action['WFWorkflowActionIdentifier']
    == 'com.apple.mobiletimer-framework.MobileTimerIntents.MTGetAlarmsIntent'
]
assert len(get_alarms) == 1
descriptor = get_alarms[0]['WFWorkflowActionParameters']['AppIntentDescriptor']
assert descriptor['BundleIdentifier'] == 'com.apple.mobiletimer'
assert descriptor['AppIntentIdentifier'] == 'AlarmEntity'
label_reads = [
    value['Value']['Aggrandizements']
    for action in actions
    for value in action.get('WFWorkflowActionParameters', {}).values()
    if isinstance(value, dict)
    and isinstance(value.get('Value'), dict)
    and 'Aggrandizements' in value['Value']
]
assert sum(
    any(
        item.get('PropertyName') == 'label'
        and item.get('PropertyUserInfo', {}).get(
            'WFLinkEntityContentPropertyUserInfoPropertyIdentifier'
        ) == 'label'
        for item in aggrandizements
    )
    for aggrandizements in label_reads
) == 2
comparisons = [
    action['WFWorkflowActionParameters']
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.conditional'
    and action.get('WFWorkflowActionParameters', {}).get('WFControlFlowMode') == 0
]
assert all('WFConditionalActionString' not in item for item in comparisons)
name_patterns = [
    action['WFWorkflowActionParameters']['WFMatchTextPattern']
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.text.match'
    and action['WFWorkflowActionParameters'].get('CustomOutputName', '').startswith('same')
]
assert name_patterns == [r'(?s)^(.+)\n\1$', r'(?s)^(.+)\n\1$']
text = path.read_text(encoding='utf-8')
assert 'calendars.icloud.com' not in text
assert 'holidays-2026' not in text
print(f'已校验 {len(actions)} 个动作；条件动作无空白动态比较值；节假日仅从苹果日历读取。')
