#!/usr/bin/env python3
"""Submit the audited plist to the same HubSign endpoint used by Cherri."""
import json
import pathlib
import sys
import urllib.request

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
request = urllib.request.Request(
    'https://hubsign.routinehub.services/sign',
    data=json.dumps({'shortcutName': '智能节假日闹钟 v4.3', 'shortcut': source.read_text(encoding='utf-8')}).encode(),
    headers={'Content-Type': 'application/json', 'User-Agent': 'cherri/v2.3.0'},
    method='POST',
)
with urllib.request.urlopen(request, timeout=30) as response:
    signed = response.read()
if not signed.startswith(b'AEA1'):
    raise SystemExit('HubSign did not return a signed shortcut')
target.write_bytes(signed)
print(f'已签名: {target}')
