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
assert ids.count('is.workflow.actions.filter.calendarevents') == 2
assert not any('geturl' in item or 'rawaction' in item for item in ids)
assert ids.count('is.workflow.actions.downloadurl') == 0
queries = [
    action for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.filter.calendarevents'
]
queries = {
    action['WFWorkflowActionParameters']['CustomOutputName']: action
    for action in queries
}
assert set(queries) == {'testCalendarEvents', 'currentCalendarEvents'}
query = queries['currentCalendarEvents']
params = query['WFWorkflowActionParameters']
assert params['WFContentItemLimitEnabled'] is False
filt = params['WFContentItemFilter']
assert filt['WFSerializationType'] == 'WFContentPredicateTableTemplate'
templates = filt['Value']['WFActionParameterFilterTemplates']
assert len(templates) == 3
assert [(t['Property'], t['Operator']) for t in templates] == [
    ('Start Date', 1001),
    ('Calendar', 4),
    ('End Date', 2),
]
assert templates[0]['Bounded'] is True
assert templates[0]['Removable'] is False
assert templates[0]['Values'] == {'Number': '10', 'Unit': 16}
assert templates[1]['Values']['Enumeration']['Value'] == '中国大陆节假日'
assert templates[2]['Values']['Date']['Value']['Type'] == 'CurrentDate'
assert 'WFContentItemLimitNumber' not in params
assert 'WFDictionaryFieldValueItems' not in str(filt)

test_params = queries['testCalendarEvents']['WFWorkflowActionParameters']
assert test_params['WFContentItemLimitEnabled'] is False
test_templates = test_params['WFContentItemFilter']['Value'][
    'WFActionParameterFilterTemplates'
]
assert [(t['Property'], t['Operator']) for t in test_templates] == [
    ('Start Date', 1003),
    ('Calendar', 4),
]
assert test_templates[0]['Values']['Date']['Value']['OutputName'] == 'testQueryStartDate'
assert test_templates[0]['Values']['AnotherDate']['Value']['OutputName'] == 'testQueryEndDate'
assert test_templates[1]['Values']['Enumeration']['Value'] == '中国大陆节假日'
assert 'WFContentItemLimitNumber' not in test_params
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
mobiletimer_expectations = {
    'com.apple.mobiletimer-framework.MobileTimerIntents.MTToggleAlarmIntent':
        ('ToggleAlarmIntent', 4),
    'com.apple.mobiletimer-framework.MobileTimerIntents.MTCreateAlarmIntent':
        ('CreateAlarmIntent', 1),
}
for identifier, (intent, expected_count) in mobiletimer_expectations.items():
    matching = [action for action in actions if action['WFWorkflowActionIdentifier'] == identifier]
    assert len(matching) == expected_count
    for action in matching:
        descriptor = action['WFWorkflowActionParameters']['AppIntentDescriptor']
        assert descriptor == {
            'TeamIdentifier': '0000000000',
            'BundleIdentifier': 'com.apple.mobiletimer',
            'Name': '时钟',
            'AppIntentIdentifier': intent,
        }
sleep_alarm_actions = [
    action for action in actions
    if action['WFWorkflowActionIdentifier']
    == 'com.apple.mobiletimer.EditSleepAlarmIntent'
]
assert len(sleep_alarm_actions) == 3
assert {
    action['WFWorkflowActionParameters']['operation']
    for action in sleep_alarm_actions
} == {'toggle', 'skip', 'unskip'}
for action in sleep_alarm_actions:
    assert action['WFWorkflowActionParameters']['AppIntentDescriptor'] == {
        'TeamIdentifier': '0000000000',
        'BundleIdentifier': 'com.apple.mobiletimer',
        'Name': '时钟',
        'AppIntentIdentifier': 'EditSleepAlarmIntent',
    }
delete_actions = [
    action for action in actions
    if action['WFWorkflowActionIdentifier'] == 'com.apple.clock.DeleteAlarmIntent'
]
assert len(delete_actions) == 1
assert delete_actions[0]['WFWorkflowActionParameters']['AppIntentDescriptor'] == {
    'TeamIdentifier': '0000000000',
    'BundleIdentifier': 'com.apple.clock',
    'Name': 'Clock',
    'AppIntentIdentifier': 'DeleteAlarmIntent',
}
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
# Cherri v2.3.0 silently drops the second operator in a compound numeric
# condition. v4.5 uses two nested single conditions and rejects any incomplete
# serialized condition so iOS never receives an unconfigured “If” action.
assert all('WFCondition' in item or 'WFConditions' in item for item in comparisons)
for item in comparisons:
    if 'WFConditions' in item:
        templates = item['WFConditions']['Value']['WFActionParameterFilterTemplates']
        assert all('WFCondition' in template for template in templates)

date_formats = [
    action['WFWorkflowActionParameters'].get('WFDateFormat')
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.format.date'
]
assert 'yyyyMMddHHmmss' not in date_formats, date_formats
name_patterns = [
    action['WFWorkflowActionParameters']['WFMatchTextPattern']
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.text.match'
    and action['WFWorkflowActionParameters'].get('CustomOutputName', '').startswith('same')
]
assert name_patterns == [
    r'(?s)^(.+)\n\1$',
    r'(?s)^(.+)\n\1$',
]
patterns_by_name = {
    action['WFWorkflowActionParameters'].get('CustomOutputName'): action[
        'WFWorkflowActionParameters'
    ]['WFMatchTextPattern']
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.text.match'
}
assert patterns_by_name['testDateLine'] == r'^([0-9]{6})(\|测试日期)?$'
assert patterns_by_name['alarmLine'] == r'^(?:[01]\d|2[0-3]):[0-5]\d\|.+$'
assert patterns_by_name['workdayMark'] == '班'
assert patterns_by_name['restdayMark'] == '休'
config_texts = [
    action['WFWorkflowActionParameters'].get('WFTextActionText')
    for action in actions
    if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.gettext'
]
assert any(text and text.endswith('\n|测试日期') for text in config_texts)
alarm_configs = [
    item for item in config_texts
    if isinstance(item, str)
    and item.startswith('08:00|起床\n')
    and item.endswith('\n|测试日期')
]
assert len(alarm_configs) == 1
assert '\n调试日志|关\n' in alarm_configs[0]
assert '\n调试日志|开\n' not in alarm_configs[0]
project_info = '作者：GetFreedomPro\nGitHub：https://github.com/free-build/holiday-alarm'
assert config_texts.count(project_info) == 1
assert project_info not in alarm_configs[0]
text = path.read_text(encoding='utf-8')
assert 'sawSpecial' not in text
assert 'calendars.icloud.com' not in text
assert 'holidays-2026' not in text
assert ids.count('is.workflow.actions.setclipboard') == 1
assert ids.count('is.workflow.actions.showresult') == 1
clipboard_index = ids.index('is.workflow.actions.setclipboard')
show_index = ids.index('is.workflow.actions.showresult')
assert clipboard_index < show_index
assert 'iot-ipv6.dynv6.net' not in text
assert 'REMOTE_LOG_PLACEHOLDER' not in text
print(f'已校验 {len(actions)} 个动作；条件动作无空白动态比较值；节假日仅从苹果日历读取。')
