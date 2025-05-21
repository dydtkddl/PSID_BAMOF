#!/bin/bash

TARGET_DIR=${1:-.}
MAX_SIZE=104857600  # 100MB

echo "📂 Scanning '$TARGET_DIR' for files under 100MB..."

find "$TARGET_DIR" -type f ! -path "*/.git/*" | while read -r file; do
    if [ -e "$file" ]; then
        filesize=$(stat -c%s "$file" 2>/dev/null)

        # filesize가 비어있지 않고 정수일 경우만 진행
        if [[ "$filesize" =~ ^[0-9]+$ ]]; then
            if [ "$filesize" -le "$MAX_SIZE" ]; then
                echo "✅ Adding: $file ($(($filesize / 1048576))MB)"
                git add "$file"
            else
                echo "⚠️ Skipped (too large): $file ($(($filesize / 1048576))MB)"
            fi
        else
            echo "❌ Could not determine file size: $file"
        fi
    else
        echo "❌ File not found or unreadable: $file"
    fi
done

