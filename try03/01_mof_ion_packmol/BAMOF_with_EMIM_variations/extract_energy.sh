#!/bin/bash

# 출력 파일 초기화
output_file="final_energies.csv"
echo "Folder,Total_Energy_Hartree" > "$output_file"

# 현재 디렉토리 내 EMIM* 폴더 순회
for dir in EMIM*/; do
    file="${dir}simulation.input.out"

    if [[ -f "$file" ]]; then
        # 마지막 Total Energy 라인을 추출
        energy=$(grep "ENERGY| Total FORCE_EVAL ( QS ) energy" "$file" | tail -n 1 | awk '{print $NF}')
        echo "${dir%,},$energy" >> "$output_file"
    else
        echo "${dir%,},FILE_NOT_FOUND" >> "$output_file"
    fi
done

echo "✅ Extracted energies saved to $output_file"

