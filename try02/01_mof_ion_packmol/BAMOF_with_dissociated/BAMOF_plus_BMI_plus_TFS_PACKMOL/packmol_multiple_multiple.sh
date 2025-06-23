#!/usr/bin/env bash
# 출력 최상위 디렉터리
OUTPUT_ROOT="packmol_output"
INPUT_ROOT="packmol_input"

# base_inputs 디렉터리 확인
if [ ! -d "base_inputs" ]; then
  echo "Error: base_inputs 디렉터리가 없습니다."
  exit 1
fi

# 출력 루트 생성
mkdir -p "$OUTPUT_ROOT"
mkdir -p "$INPUT_ROOT"

# 각 .inp 파일마다 반복
for BASEINP in base_inputs/*_wrapped.inp; do
  # 파일명에서 확장자 제거
  NAME=$(basename "$BASEINP" .inp)
  
  # 케이스별 작업 폴더 생성
  WORKDIR="$OUTPUT_ROOT/$NAME"
  mkdir -p "$WORKDIR"
  
  # 입력 파일을 작업 폴더로 복사
  cp "$BASEINP" "$WORKDIR/"
  
  echo "Running packmol in $WORKDIR"
  (
    cd "$WORKDIR" || exit 1
    python /mnt/d/PSID_SIMULATION_TOOLS/packmol/packmol_multiple.py \
      --baseinput "$(basename "$BASEINP")" \
      --output "." \
      --inputdir "." \
      --ncases 5 \
      --verbose
  )
done

echo "모든 작업 완료."
