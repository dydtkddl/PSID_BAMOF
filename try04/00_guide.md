이제 전체 상황이 명확하게 보입니다. 종합 진단과 가이드를 드리겠습니다.

---

# 🔍 try04 전수조사 결과 & 작전 가이드

## 1. 현재 상태 종합 (뭐가 되어있고, 뭐가 안 되어있는가)

| Phase             | 상태                 | 핵심 산출물                                             |
| ----------------- | -------------------- | ------------------------------------------------------- |
| **A. 환경**       | ✅ 완료              | RTX 5090(32GB), TR PRO 9965WX 24C, 62GB RAM, 9.6TB free |
| **B. 구조**       | ✅ 완료              | 192-atom XYZ 2개, validate/export/distance 스크립트     |
| **C. Docker**     | ✅ 완료              | `keti/cp2k:2025.2-gpu` 동작 확인                        |
| **D. Dry-run**    | ❌ **SCF 수렴 실패** | 103 step 돌고 진동 → 여기가 병목                        |
| **E. 모니터링**   | ❌ 미작성            | monitor.sh, plot_convergence.py 등 0개                  |
| **F. 프로덕션**   | ❌ 시작 불가         | D가 안 되니 시작할 수 없음                              |
| **G. try03 검증** | ❌ 미작성            | extract_try03_energies.py 등 0개                        |
| **H. SI Figure**  | ❌ 미작성            | fig_ediss_comparison.py 등 0개                          |
| **I. Git**        | ⚠️ 부분              | .gitignore 없음, 커밋 안 됨                             |

---

## 2. 삽질의 근본 원인 2가지

### 원인 ①: PowerShell→WSL quoting 지옥

에이전트가 PowerShell에서 `wsl -e bash -lc '...'`로 복잡한 bash를 인라인으로 넘기다가 따옴표/heredoc/변수 치환이 꼬여서 같은 명령을 10~30번 반복했습니다.

**해법: `.sh` 파일을 먼저 쓰고, `wsl -e bash /mnt/d/.../script.sh`로 실행**

이미 `tmp_phase_a.sh`를 파일로 만들었을 때 한 번에 성공한 전례가 있습니다. 앞으로 모든 Phase를 이 패턴으로 통일하면 됩니다.

### 원인 ②: SCF 수렴 실패 (이게 과학적으로 진짜 문제)

dry-run 로그를 분석하면:

```
Step   Energy (Ha)          Change       Convergence
  1    -1892.8052           -1.89E+03    6.005
 10    -1886.3095            7.64E-02    0.109
 50    -1886.3638           -3.63E-02    0.021
103    -1886.3586           -4.13E-03    0.003  ← 여기서 끊김
```

에너지가 **-1886.35 Ha 근처에서 ±0.03 Ha**로 진동하고 있고, convergence가 0.003까지 내려간 뒤 더 이상 떨어지지 않습니다. 200 step 안에 `EPS_SCF 5.0E-7`에 도달할 가능성이 거의 없습니다.

**원인 분석:**

try03 (158 atoms, 1IP) → try04 (192 atoms, 2IP)로 갈 때 달라진 것:

| 파라미터       | try03             | try04          | 문제?                       |
| -------------- | ----------------- | -------------- | --------------------------- |
| 원자 수        | 158               | 192 (+34)      | 전자 수 증가 → SCF 난이도 ↑ |
| ADDED_MOS      | 100               | 170            | 적절히 올림 ✅              |
| ALPHA (mixing) | 0.15              | 0.15           | **여기가 문제**             |
| SCF_GUESS      | RESTART (wfn있음) | ATOMIC (fresh) | **여기가 문제**             |
| MAX_SCF        | 200               | 200            | 부족할 수 있음              |

try03는 **restart 파일(WFN)에서 이어서** 돌렸기 때문에 SCF가 이미 좋은 초기 guess에서 시작했습니다. try04는 ATOMIC guess에서 처음부터 시작하는데, 192-atom metallic system에 ALPHA=0.15 Broyden mixing은 너무 공격적입니다.

---

## 3. SCF 수렴 해결 전략 (3단계)

### 전략 A: ALPHA를 줄이고 OUTER_SCF 추가 (가장 안전)

```
&SCF
  MAX_SCF 300           ← 200 → 300
  EPS_SCF 5.0E-7
  SCF_GUESS ATOMIC
  ADDED_MOS 170
  &DIAGONALIZATION T
    ALGORITHM STANDARD
  &END DIAGONALIZATION
  &SMEAR T
    METHOD FERMI_DIRAC
    ELECTRONIC_TEMPERATURE 300
  &END SMEAR
  &MIXING T
    METHOD BROYDEN_MIXING
    ALPHA 0.05           ← 0.15 → 0.05 (핵심 변경!)
    NBUFFER 8            ← 추가: Broyden history 확대
  &END MIXING
  &OUTER_SCF T           ← 추가: 외부 루프
    MAX_SCF 10
    EPS_SCF 5.0E-7
  &END OUTER_SCF
  &PRINT
    &RESTART ON
    &END RESTART
  &END PRINT
&END SCF
```

**왜 이렇게 바꾸는가:**

- `ALPHA 0.05`: Broyden mixing의 damping을 강하게 걸어서 진동을 억제합니다. Ti d-orbital이 포함된 metallic MOF에서 ALPHA=0.15는 과도한 mixing입니다.
- `NBUFFER 8`: Broyden 히스토리를 늘려서 수렴 안정성을 높입니다.
- `OUTER_SCF`: 내부 SCF가 300 step에서 못 수렴해도, 밀도를 리셋하고 재시도합니다. GEO_OPT이 SCF 실패로 중단되는 것을 방지합니다.

### 전략 B: OT(Orbital Transformation)로 전환 (수렴 보장, 단 SMEAR 불가)

만약 전략 A가 안 되면:

```
&SCF
  MAX_SCF 300
  EPS_SCF 5.0E-7
  SCF_GUESS ATOMIC
  ADDED_MOS 0            ← OT에서는 0
  &OT T                  ← 대각화 대신 OT
    MINIMIZER DIIS
    PRECONDITIONER FULL_ALL
    ENERGY_GAP 0.01
  &END OT
  &OUTER_SCF T
    MAX_SCF 10
    EPS_SCF 5.0E-7
  &END OUTER_SCF
&END SCF
```

주의: OT는 SMEAR/FERMI_DIRAC과 호환 안 됨 → metallic system에서는 gap이 작으면 문제될 수 있음. try03가 SMEAR를 쓴 이유가 Ti d-orbital 때문이므로, **전략 A를 먼저 시도**하는 게 맞습니다.

### 전략 C: 전자 온도를 올려서 SMEAR 강화

전략 A에 추가로:

```
ELECTRONIC_TEMPERATURE 600    ← 300 → 600 (K)
```

Ti 3d의 부분 점유를 더 넓게 퍼뜨려서 SCF 수렴을 도울 수 있습니다.

**권장 순서: A → (A 실패 시) A+C → (그래도 실패 시) B**

---

## 4. 나머지 Phase E~I 해결: "파일 먼저, 실행 나중" 패턴

남은 스크립트는 모두 **Python 파일을 PowerShell `Set-Content`로 생성** → **`wsl -e bash -c "python3 /mnt/d/.../script.py"`로 실행**하면 quoting 문제 없이 깔끔합니다.

생성해야 할 파일 목록:

```
02_calculations/monitor.sh                    ← Phase E-1
03_postprocessing/plot_convergence.py          ← Phase E-2
03_postprocessing/track_ion_distance.py        ← Phase E-3
03_postprocessing/export_final.py              ← Phase E-4
00_reference_structures/extract_try03_energies.py  ← Phase G-1
00_reference_structures/extract_try03_structures.py ← Phase G-2
03_postprocessing/fig_ediss_comparison.py       ← Phase H-1
03_postprocessing/vesta_guide.md               ← Phase H-2
03_postprocessing/final_report.py              ← Phase H-3
.gitignore                                     ← Phase I-1
```

이건 SCF 문제와 독립적이니까, input.inp 수정과 병렬로 진행 가능합니다.

---

## 5. 즉시 실행 액션 플랜

**Step 1 (지금 바로):** input.inp 수정

PowerShell에서:

```powershell
# cluster
$inp = Get-Content D:\PSID_BAMOF\try04\02_calculations\BAMOF_2IP_cluster\input.inp -Raw
$inp = $inp -replace 'ALPHA 0.15', "ALPHA 0.05`n        NBUFFER 8"
$inp = $inp -replace 'MAX_SCF 200', 'MAX_SCF 300'
# OUTER_SCF 블록을 &PRINT 바로 앞에 삽입
$inp = $inp -replace '(\s+&PRINT\s+\n\s+&RESTART ON)', "    &OUTER_SCF T`n      MAX_SCF 10`n      EPS_SCF 5.0E-7`n    &END OUTER_SCF`n`$1"
Set-Content -Path D:\PSID_BAMOF\try04\02_calculations\BAMOF_2IP_cluster\input.inp -Value $inp
# dissociate에도 동일 적용
Copy-Item D:\PSID_BAMOF\try04\02_calculations\BAMOF_2IP_cluster\input.inp D:\PSID_BAMOF\try04\02_calculations\BAMOF_2IP_dissociate\input.inp
```

(또는 에디터에서 직접 3군데만 고치면 됩니다)

**Step 2:** dry-run 재실행 (수정된 input으로)

```powershell
# test script 파일로 만들어서 실행
$test = @'
#!/bin/bash
set -e
cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster
cp input.inp input_test.inp
perl -i -pe 's/MAX_ITER 600/MAX_ITER 2/' input_test.inp
timeout 600s docker run --rm --gpus=all \
  -v "$(pwd)":/work:Z -w /work \
  keti/cp2k:2025.2-gpu \
  mpirun -n 4 -x OMP_NUM_THREADS=2 cp2k.psmp \
  -i input_test.inp -o test_output.out > test.log 2>&1
echo "EXIT:$?"
grep "SCF run converged" test_output.out && echo "SCF OK" || echo "SCF FAILED"
grep "ENERGY| Total" test_output.out | tail -3
'@
Set-Content -Path D:\PSID_BAMOF\try04\dry_run_test.sh -Value $test -Encoding ASCII
wsl -e bash /mnt/d/PSID_BAMOF/try04/dry_run_test.sh
```

**Step 3:** SCF 수렴 확인되면 → Phase E~I 스크립트 일괄 생성 → 프로덕션 시작

---

## 6. 추가 주의사항

**try03 에너지 크로스체크:**

- try03 cluster: **-1613.7984 Ha** (158 atoms)
- try03 dissociate: **-1613.7849 Ha** (158 atoms)
- E_diss = (-1613.7849) - (-1613.7984) = **+0.01356 Ha = +8.51 kcal/mol ≈ 35.6 kJ/mol**

이건 논문에서 말한 17.77 kJ/mol과 다를 수 있습니다. gas-phase 에너지가 빠져있거나 단위 변환이 다를 수 있으니 Phase G에서 꼭 검증해야 합니다.

**Docker 실행 팁:**

- `keti/cp2k:2025.2-gpu` 이미지 안에 `/opt/cp2k/data/`가 이미 있으므로 `~/cp2k/data` 마운트가 없어도 됩니다.
- `run_cp2k_gpu.sh`의 `DATA_DIR` fallback이 이미 이 케이스를 커버합니다.
- MPI 프로세스: RTX 5090 + 24-core CPU면 **`-n 4 -x OMP_NUM_THREADS=4`** (총 16 thread) 정도가 적당합니다.

**PROGRESS.md에 `\r` 파일 문제:**
Git에 `PROGRESS.md\r`이라는 이름의 파일이 올라가 있습니다. Windows 줄바꿈이 파일명에 섞인 것이니 `git rm "try04/PROGRESS.md\r"` 로 제거하세요.

---

요약하면: **지금 막혀있는 건 SCF 하나뿐**이고, `ALPHA 0.15 → 0.05` + `NBUFFER 8` + `OUTER_SCF` 추가로 해결될 가능성이 높습니다. 나머지는 전부 파일 생성 작업이라 SCF 고치는 동안 병렬로 진행 가능합니다.
