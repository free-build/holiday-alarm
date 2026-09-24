#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
build_dir="$project_dir/build"
source_file="$project_dir/src/智能节假日闹钟_v4.4.cherri"
compiler="${CHERRI_BIN:-$project_dir/.tools/cherri}"
mode="${1:---check}"
if [[ "$mode" != "--check" && "$mode" != "--sign" ]]; then
  echo "用法: ./build.sh [--check|--sign]" >&2
  exit 2
fi
if [[ ! -x "$compiler" || "$("$compiler" -v)" != *"v2.3.0"* ]]; then
  echo "需要 Cherri v2.3.0；可设置 CHERRI_BIN。" >&2
  exit 1
fi
mkdir -p "$build_dir"
cp "$source_file" "$build_dir/智能节假日闹钟_v4.4.cherri"
cd "$build_dir"
"$compiler" "智能节假日闹钟_v4.4.cherri" --debug --skip-sign --no-ansi > compile.log 2>&1
plist="智能节假日闹钟 v4.4.plist"
python3 "$project_dir/tools/fix_calendar_filter.py" "$plist"
python3 "$project_dir/tools/check_plist.py" "$plist"
cp "$plist" "智能节假日闹钟_v4.4_unsigned.shortcut"
rm -f "智能节假日闹钟 v4.4_unsigned.shortcut"
if [[ "$mode" == "--sign" ]]; then
  python3 "$project_dir/tools/sign.py" "$plist" "智能节假日闹钟_v4.4.shortcut"
fi
echo "构建完成: $build_dir"
