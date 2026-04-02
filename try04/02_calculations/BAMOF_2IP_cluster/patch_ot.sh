#!/bin/bash
FILE="input_test.inp"

# ADDED_MOS 제거 (OT에서는 사용 불가)
sed -i 's/ADDED_MOS.*//g' "$FILE"

# 기존 SMEAR 블록 제거
sed -i '/&SMEAR/,/&END SMEAR/d' "$FILE"

# 기존 MIXING 블록 제거
sed -i '/&MIXING/,/&END MIXING/d' "$FILE"

# 기존 DIAGONALIZATION 블록 제거
sed -i '/&DIAGONALIZATION/,/&END DIAGONALIZATION/d' "$FILE"

# 기존 OUTER_SCF 블록 제거
sed -i '/&OUTER_SCF/,/&END OUTER_SCF/d' "$FILE"

# SCF_GUESS 변경
sed -i 's/SCF_GUESS  ATOMIC/SCF_GUESS  ATOMIC/' "$FILE"

# EPS_SCF 뒤에 OT 블록 삽입
sed -i '/EPS_SCF/a\
    &OT\
      MINIMIZER DIIS\
      PRECONDITIONER FULL_ALL\
      ENERGY_GAP 0.01\
    &END OT\
    &OUTER_SCF\
      MAX_SCF 20\
      EPS_SCF 5.0E-7\
    &END OUTER_SCF' "$FILE"

echo "OT method patch applied."
