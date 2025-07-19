#!/bin/bash

# 대상 디렉토리 목록
for dir in EMIM02 EMIM03; do
  echo "▶ Entering $dir"
  cd "$dir" || { echo "❌ Failed to enter $dir"; exit 1; }

  restart_file="${dir}-1.restart"
  echo "🚀 Running: sh run_cp2k.sh $restart_file 200000"
  sh run_cp2k.sh "$restart_file" 200000

  cd ..
done

