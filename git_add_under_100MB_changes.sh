#!/bin/bash

MAX_SIZE=104857600       # 100MB (단일 파일 최대 허용 크기)
MAX_TOTAL=1073741824     # 1GB (누적 최대 허용 크기)

total_size=0             # 누적 크기 초기화

# tracked + untracked 변경 파일 모두 포함
changed_files=$(git status --porcelain | grep -E '^(A|M|\?\?)' | awk '{print $2}')

echo "🔍 Checking changed, added, and untracked files for size limit..."

for file in $changed_files; do
    echo "$file"
    if [ -e "$file" ]; then
        filesize=$(stat -c%s "$file" 2>/dev/null)

        if [[ "$filesize" =~ ^[0-9]+$ ]]; then
            if [ "$filesize" -le "$MAX_SIZE" ]; then
                # 누적 크기 계산
                total_size=$((total_size + filesize))

                if [ "$total_size" -gt "$MAX_TOTAL" ]; then
                    echo "⚠️ Total added file size exceeded 1GB limit."
                    echo "💡 Please commit your changes before adding more files."
                    exit 1
                fi

                git add "$file"
                echo "✅ Added: $file ($(($filesize / 1048576))MB), Total: $(($total_size / 1048576))MB"
            else
                echo "⚠️ Skipped (too large): $file ($(($filesize / 1048576))MB)"
            fi
        else
            echo "❌ Could not determine size: $file"
        fi
    else
        echo "❌ File not found: $file"
    fi
done

