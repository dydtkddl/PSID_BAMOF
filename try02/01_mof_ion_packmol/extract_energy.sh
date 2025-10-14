#!/bin/bash

output="bmi_final_energies.csv"
echo "Folder,Total_Energy_Hartree" > "$output"

# BAMOF_with_BMI_* 폴더만 순회
for dir in BAMOF_with_BMI_*; do
    file="$dir/simulation.input.out"

    if [[ -f "$file" ]]; then
        # 마지막 에너지 라인 추출
        energy=$(grep "ENERGY| Total FORCE_EVAL ( QS ) energy" "$file" | tail -n 1 | awk '{print $NF}')
        echo "$dir,$energy" >> "$output"
    else
        echo "$dir,FILE_NOT_FOUND" >> "$output"
    fi
done

echo "✅ Saved to $output"

