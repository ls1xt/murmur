#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="$HOME/.config/murmur"
CONFIG_FILE="$CONFIG_DIR/config.json"

read -rsp "AssemblyAI API key: " api_key
echo

mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    # Update existing file's api_key field
    tmp=$(mktemp)
    python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    data = json.load(f)
data.setdefault('transcriber', {})['api_key'] = sys.argv[1]
print(json.dumps(data, indent=2))
" "$api_key" > "$tmp"
    mv "$tmp" "$CONFIG_FILE"
else
    printf '{\n  "transcriber": {\n    "api_key": "%s"\n  }\n}\n' "$api_key" > "$CONFIG_FILE"
fi

chmod 600 "$CONFIG_FILE"
echo "Key saved to $CONFIG_FILE"
