# CODEX 자율 작업 지시 프롬프트: try04 2-IP DFT 시뮬레이션 전체 셋업 및 검증

## 프로젝트 위치
```
/mnt/d/PSID_BAMOF/try04/
```

## 배경
나는 계산화학 연구자다. MOF(Metal-Organic Framework) 안에 이온쌍(ionic liquid)을 넣고 DFT로 해리 에너지를 계산하는 연구를 하고 있다. 리뷰어가 "기존 계산은 이온쌍 1개(dilute limit)인데 실험은 ~200 wt%다. 고농도에서도 결론이 유효한가?"라고 지적했다. 이에 대응하여 이온쌍 2개를 넣은 추가 시뮬레이션을 준비하고 있다.

기존 프로젝트(try03)는 `/mnt/d/PSID_BAMOF/try03/`에 있다. try04가 현재 작업 대상이다.

## 현재 상태
- `build_structures.py`가 192-atom XYZ 파일 2개를 생성함 (cluster + dissociate)
- `input.inp` 2개가 CP2K fresh input으로 준비됨
- `run_cp2k_gpu.sh` 실행 스크립트 준비됨
- `analyze.py` 후처리 스크립트 준비됨
- **아직 CP2K 계산은 시작하지 않음**
- **구조 검증, Docker 빌드, 테스트 런, 모니터링 인프라가 아직 없음**

## 너의 역할
아래 Phase를 순서대로 수행하라. 각 Phase가 끝날 때마다 `try04/PROGRESS.md`에 진행 상황을 기록하라. 에러 발생 시 멈추지 말고 에러를 기록하고 다음 가능한 단계로 넘어가라. 모든 작업은 `try04/` 디렉토리 안에서 수행하라.

---

## Phase A: 환경 확인 및 사전 준비 (15분)

### A-1. 시스템 환경 조사
```bash
# 다음을 확인하고 결과를 try04/PROGRESS.md에 기록
uname -a
python3 --version
pip3 list | grep -i numpy
docker --version
docker images | grep cp2k
nvidia-smi  # GPU 유무 확인
cat /proc/cpuinfo | grep "model name" | head -1
free -h
df -h /mnt/d/
```

### A-2. try03 기존 프로젝트 확인
```bash
# try03에서 필요한 파일들이 있는지 확인
ls -la /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/
ls -la /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/
ls -la /mnt/d/PSID_BAMOF/try03/00_ionic_structure_cp2k/Cluster01/

# try03 결과 에너지 확인 (E_diss 역산용)
# simulation.input.out에서 final energy 추출
grep "ENERGY| Total FORCE_EVAL" /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/simulation.input.out | tail -1
grep "ENERGY| Total FORCE_EVAL" /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/simulation.input.out | tail -1
```

### A-3. numpy 설치 확인
```bash
pip3 install numpy  # 없으면 설치
```

---

## Phase B: 초기 구조 생성 및 검증 (30분)

### B-1. build_structures.py 실행
```bash
cd /mnt/d/PSID_BAMOF/try04/01_structure_preparation
python3 build_structures.py
```
결과로 다음 파일이 생성되어야 한다:
- `../02_calculations/BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz` (192 atoms)
- `../02_calculations/BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz` (192 atoms)

### B-2. 구조 검증 스크립트 작성 및 실행
`01_structure_preparation/validate_all.py`를 새로 작성하라:

```python
"""
validate_all.py — 생성된 2-IP 구조의 물리적 타당성을 종합 검증
검증 항목:
1. 원자 수 = 192
2. 원소별 개수 정합성
3. 전체 원자간 최소 거리 > 0.8 Å (겹침 없음)
4. MOF(1-102) ↔ 2nd IP 최소 거리 > 1.5 Å
5. 1st IP ↔ 2nd IP 최소 거리 > 2.0 Å
6. Cluster: 2nd EMIM-TFSI 최소 거리 < 4.0 Å (associated)
7. Dissociate: 2nd EMIM-TFSI 최소 거리 > 5.0 Å (separated)
8. 모든 원자의 좌표 범위가 셀 크기와 대략 호환
9. input.inp의 COORD_FILE_NAME이 실제 XYZ 파일과 일치
10. input.inp에서 원소 KIND가 XYZ에 있는 원소를 모두 커버
"""
```
위 10개 항목을 전부 체크하고 PASS/FAIL 리포트를 출력하는 스크립트를 작성하라. FAIL이 하나라도 있으면 상세 정보를 출력하라.

### B-3. 구조 시각화용 파일 생성
`01_structure_preparation/export_visualization.py`를 작성하라:
- cluster와 dissociate 구조 각각에 대해:
  - MOF 프레임워크(atoms 1-124)를 하나의 색으로
  - 1st IP(atoms 125-158)를 다른 색으로
  - 2nd IP(atoms 159-192)를 또 다른 색으로
  - 구분할 수 있는 .xyz 파일(코멘트 라인에 색상 정보) 생성
- OVITO/VESTA에서 열 수 있는 형식
- 셀 벡터 정보를 별도 파일로 출력 (VESTA POSCAR 형식 또는 .cell 파일)

### B-4. 거리 분석 리포트 생성
`01_structure_preparation/distance_report.py`를 작성하라:
- 2nd IP의 각 원자에 대해 가장 가까운 기존 원자(MOF/1st IP)까지의 거리 출력
- 2nd EMIM의 각 원자에서 가장 가까운 Ti 원자까지의 거리 (흡착 사이트 근접성)
- 2nd TFSI의 각 원자에서 가장 가까운 2nd EMIM 원자까지의 거리
- cluster vs dissociate 비교 테이블
- 결과를 `01_structure_preparation/distance_report.txt`에 저장

---

## Phase C: Docker 환경 구축 (20분)

### C-1. Docker 이미지 확인/빌드
```bash
# 기존 이미지 확인
docker images | grep cp2k

# 이미지가 없으면 pull
docker pull cp2k/cp2k:latest  # CPU 이미지 (fallback)

# GPU 이미지 빌드 (GPU 있는 경우만)
# nvidia-smi가 동작하면:
cd /mnt/d/PSID_BAMOF/try04/docker
docker build -t cp2k-try04:2024.3-gpu .
```

GPU가 없으면 `cp2k/cp2k:latest`를 사용한다. `run_cp2k_gpu.sh`가 자동 감지한다.

### C-2. CP2K 데이터 파일 확인
```bash
# try03에서 사용한 데이터 디렉토리 확인
ls ~/cp2k/data/BASIS_MOLOPT
ls ~/cp2k/data/GTH_POTENTIALS
ls ~/cp2k/data/dftd3.dat
```
없으면 Docker 컨테이너에서 추출:
```bash
docker run --rm cp2k/cp2k:latest ls /opt/cp2k/data/ | head -20
# 필요 파일이 이미지 안에 있는지 확인
docker run --rm cp2k/cp2k:latest cat /opt/cp2k/data/BASIS_MOLOPT | head -5
```

### C-3. CP2K 버전 확인
```bash
docker run --rm cp2k/cp2k:latest cp2k --version
```
버전 정보를 PROGRESS.md에 기록.

---

## Phase D: CP2K Dry-Run 테스트 (40분)

**이 Phase가 가장 중요하다. 실제 계산(수일)을 시작하기 전에 인풋이 올바른지 확인한다.**

### D-1. 단일 SCF 테스트 (cluster)
`input.inp`을 복사하여 `input_test.inp`을 만들고 MAX_ITER를 2로 변경:
```bash
cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster
cp input.inp input_test.inp
# MAX_ITER 600 → 2 로 변경 (GEO_OPT 2 step만 실행)
sed -i 's/MAX_ITER 600/MAX_ITER 2/' input_test.inp
```

Docker로 테스트 실행:
```bash
docker run --rm \
  -v "${HOME}/cp2k/data":/opt/cp2k/data:Z \
  -v "$(pwd)":/work:Z \
  -w /work \
  cp2k/cp2k:latest \
  mpirun -n 2 -genv OMP_NUM_THREADS=2 \
    cp2k -i input_test.inp -o test_output.out \
  > test.log 2>&1
```

### D-2. 테스트 결과 분석
```bash
# 성공 확인
grep "ENERGY| Total FORCE_EVAL" test_output.out
# SCF 수렴 확인  
grep "SCF run converged" test_output.out
grep "SCF run NOT converged" test_output.out
# 에러 확인
grep -i "error\|abort\|fatal" test_output.out test.log
```

**테스트가 실패하면:**
1. 에러 메시지를 분석
2. 가능한 원인: XYZ 파일 형식, KIND 누락, pseudopotential 호환성, 메모리 부족
3. 수정 후 재실행
4. 모든 시도와 결과를 PROGRESS.md에 기록

### D-3. 단일 SCF 테스트 (dissociate)
cluster와 동일하게 dissociate도 테스트:
```bash
cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate
cp input.inp input_test.inp
sed -i 's/MAX_ITER 600/MAX_ITER 2/' input_test.inp
# 동일한 docker run 명령으로 테스트
```

### D-4. try03 결과 재현 검증 (선택)
시간이 허락하면, try03의 1-IP cluster 계산을 동일한 Docker 환경에서 1-step 테스트해보라.
```bash
cd /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/
# restart 파일로 1 step만 실행하여 에너지가 비슷한지 확인
```
이렇게 하면 try03과 try04의 DFT 레벨이 동일한지 cross-check 가능.

### D-5. 테스트 파일 정리
테스트 성공 후:
```bash
cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster
rm -f input_test.inp test_output.out test.log *.restart *.wfn *.Hessian *-pos-*.xyz
cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate
rm -f input_test.inp test_output.out test.log *.restart *.wfn *.Hessian *-pos-*.xyz
```

---

## Phase E: 모니터링 인프라 구축 (30분)

### E-1. 실시간 모니터링 스크립트
`02_calculations/monitor.sh`를 작성하라:
```
기능:
- 5분마다 각 계산 디렉토리의 simulation.input.out을 체크
- 현재 GEO_OPT step 수, 최근 에너지, max force 출력
- SCF 수렴 실패 횟수 카운트
- ETA 추정 (평균 step 시간 × 남은 step)
- 디스크 사용량 체크 (wfn 파일이 크므로)
- 결과를 02_calculations/monitor.log에 append
- Ctrl+C로 종료 가능
```

### E-2. 에너지 수렴 플롯 스크립트
`03_postprocessing/plot_convergence.py`를 작성하라:
```
기능:
- simulation.input.out에서 step별 에너지와 max_force 파싱
- matplotlib로 에너지 vs step, max_force vs step 플롯
- 수렴 기준선(4.5E-4) 표시
- PNG 저장
- cluster와 dissociate를 나란히 비교하는 2-panel 플롯
```

### E-3. 자동 이온 거리 추적 스크립트
`03_postprocessing/track_ion_distance.py`를 작성하라:
```
기능:
- *-pos-1.xyz trajectory 파일에서 매 frame의:
  - 2nd EMIM COM - 2nd TFSI COM 거리
  - 2nd EMIM - 2nd TFSI 최소 원자간 거리
  - 1st IP - 2nd IP 최소 원자간 거리
- step별 거리 변화 테이블 출력
- matplotlib 플롯 생성
- dissociate에서 이온이 재결합하면 WARNING 출력
- cluster에서 이온이 분리되면 WARNING 출력
```

### E-4. 최종 구조 export 스크립트
`03_postprocessing/export_final.py`를 작성하라:
```
기능:
- *-pos-1.xyz에서 마지막 프레임 추출
- XYZ, CIF, POSCAR 형식으로 변환 (셀 벡터 포함)
- bond detection 기반 MOL2 형식 출력
- 논문 SI용 Table 생성:
  | Atom | Element | x | y | z | Role |
  - Role: MOF-fixed, MOF-unfixed, IP1-EMIM, IP1-TFSI, IP2-EMIM, IP2-TFSI
```

---

## Phase F: 프로덕션 계산 시작 (20분)

### F-1. run_cp2k_gpu.sh 실행 권한 확인
```bash
chmod +x /mnt/d/PSID_BAMOF/try04/02_calculations/run_cp2k_gpu.sh
```

### F-2. tmux 세션으로 실행
```bash
# Cluster 계산
tmux new-session -d -s cluster
tmux send-keys -t cluster "cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster && bash ../run_cp2k_gpu.sh 2>&1 | tee run.log" Enter

# Dissociate 계산 (서버 리소스가 충분하면)
tmux new-session -d -s dissociate
tmux send-keys -t dissociate "cd /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_dissociate && bash ../run_cp2k_gpu.sh 2>&1 | tee run.log" Enter
```

**리소스 제한 시:** cluster 먼저 끝낸 후 dissociate 실행. run_cp2k_gpu.sh가 watchdog으로 자동 restart하므로 tmux 세션이 유지되는 한 계속 실행된다.

### F-3. 실행 직후 확인 (5분 대기 후)
```bash
sleep 300
# 실행 확인
docker ps  # cp2k 컨테이너가 돌아가는지
tail -20 /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/simulation.input.out
tail -20 /mnt/d/PSID_BAMOF/try04/02_calculations/BAMOF_2IP_cluster/simulation.input.log
```

**에러 발생 시 트러블슈팅:**
1. `Permission denied` → `chmod +x run_cp2k_gpu.sh`
2. `No such file or directory: BAMOF_2IP_cluster_init.xyz` → Phase B에서 XYZ 생성 확인
3. `SCF run NOT converged` → `input.inp`에서 ALPHA를 0.15→0.10으로 변경 후 재시작
4. `OOM` → MPI procs를 줄이거나 (8→4), ADDED_MOS를 170→150으로 줄이기
5. Docker 관련 → `--cpu-only` 플래그 사용

---

## Phase G: try03 결과 정밀 추출 및 교차검증 (30분)

### G-1. try03 에너지 추출 스크립트
`00_reference_structures/extract_try03_energies.py`를 작성하라:

```
기능:
- try03의 모든 계산 디렉토리에서 final energy 추출:
  /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/simulation.input.out
  /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/simulation.input.out
  /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/MIL125_EMIM_TFSI_Cluster-1/simulation.input.out
  /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/MIL125_EMIM_TFSI_dissociate-1/simulation.input.out

- E_diss 계산 및 논문의 수치(17.77, 23.05, 225.06)와 비교
- 불일치 시 WARNING
- try03 GEO_OPT 수렴 여부도 체크
- 결과를 00_reference_structures/try03_energies.json에 저장
```

### G-2. try03 최종 구조 추출
`00_reference_structures/extract_try03_structures.py`를 작성하라:

```
기능:
- try03의 각 trajectory (*-pos-1.xyz)에서 마지막 프레임 추출
- 00_reference_structures/ 에 저장:
  - BAMOF_1IP_cluster_final.xyz
  - BAMOF_1IP_dissociate_final.xyz
  - EMIMTFSI_gasphase_final.xyz (try03/00_ionic_structure_cp2k/Cluster01/)
- try04에서 사용한 base structure (build_structures.py에 하드코딩된 것)와 비교
  - 차이가 있으면 WARNING (restart step vs trajectory 마지막 프레임)
```

### G-3. 구조 비교 리포트
try03 최종 구조와 try04 base 구조를 비교하여:
- 각 원자의 좌표 차이 (RMSD)
- 셀 파라미터 차이
- 결과를 `00_reference_structures/structure_comparison.txt`에 저장

---

## Phase H: SI Figure 생성 인프라 (30분)

### H-1. 비교 bar chart 스크립트
`03_postprocessing/fig_ediss_comparison.py`를 작성하라:
```
기능:
- E_diss 비교 bar chart:
  Gas-phase (225.06) | MOF+1IP (23.05) | BA-MOF+1IP (17.77) | BA-MOF+2IP (??)
- 마지막 bar는 try04 결과가 나오면 자동으로 채워짐
- 결과가 아직 없으면 placeholder로 "TBD" 표시
- 색상: MOF=파랑, BA-MOF=빨강, Gas=회색
- 폰트: Arial/Helvetica, 논문 스타일 (300 dpi)
- PNG + SVG 저장
```

### H-2. 구조 스냅샷 생성 가이드
`03_postprocessing/vesta_guide.md`를 작성하라:
```
VESTA에서 try04 구조를 시각화하는 단계별 가이드:
1. XYZ 파일 열기
2. 셀 벡터 입력 (Edit → Unit Cell)
3. 원자 색상 설정 (MOF: 회색, 1st IP: 파랑, 2nd IP: 빨강)
4. Bond 설정 
5. 카메라 앵글
6. Export 설정 (논문용 해상도)
```

### H-3. 모든 결과 통합 리포트 템플릿
`03_postprocessing/final_report.py`를 작성하라:
```
기능:
- 모든 분석 결과를 하나의 Markdown 리포트로 통합
- 포함 내용:
  1. 계산 환경 (CP2K 버전, Docker 이미지, 하드웨어)
  2. 구조 검증 결과 (거리, 원자 수)
  3. E_diss 비교 테이블
  4. GEO_OPT 수렴 정보
  5. 이온 거리 추적 결과
  6. 최종 구조 좌표 (SI Table용)
  7. 원고 삽입 문구 (자동 숫자 채움)
  8. Rebuttal letter 문구 (자동 숫자 채움)
- 결과가 아직 없는 항목은 "PENDING" 표시
- try04/FINAL_REPORT.md로 저장
```

---

## Phase I: Git 관리 및 문서화 (15분)

### I-1. .gitignore 생성
```
# try04/.gitignore
*.wfn
*.wfn.bak-*
*.Hessian
*-RESTART.wfn*
simulation.input.log
simulation.input.out
test_output.out
test.log
*.pyc
__pycache__/
monitor.log
```

### I-2. Git 커밋
```bash
cd /mnt/d/PSID_BAMOF
git add try04/
git commit -m "try04: 2-IP DFT simulation setup (reviewer 2 comment 3)

- 192-atom structures generated (BA-MOF + 2 [EMIM][TFSI])
- CP2K input files (PBE-D3/DZVP-MOLOPT-SR-GTH, 640 Ry)
- GPU-compatible run scripts with watchdog
- Full validation and post-processing pipeline
- Addresses dilute-limit approximation concern"
```

### I-3. PROGRESS.md 최종 업데이트
모든 Phase의 결과를 요약하여 기록:
```markdown
# try04 Progress

## Phase A: 환경 확인 ✓/✗
- OS: ...
- GPU: ...
- Docker: ...
- CP2K: ...

## Phase B: 구조 생성 ✓/✗
- Cluster: 192 atoms, min_dist=X.XX Å
- Dissociate: 192 atoms, EMIM-TFSI=X.XX Å
- Validation: PASS/FAIL

## Phase C: Docker 환경 ✓/✗
- Image: ...
- Data files: ...

## Phase D: Dry-run 테스트 ✓/✗
- Cluster SCF: converged/failed
- Dissociate SCF: converged/failed
- Energy (1st step): ...

## Phase E: 모니터링 인프라 ✓/✗
- Scripts created: ...

## Phase F: 프로덕션 시작 ✓/✗
- Cluster: running/pending
- Dissociate: running/pending

## Phase G: try03 검증 ✓/✗
- E_diss reproduced: ...

## Phase H: Figure 인프라 ✓/✗
- Scripts created: ...

## Phase I: Git ✓/✗
- Committed: ...
```

---

## 전체 실행 순서 요약

```
A (15min) → B (30min) → C (20min) → D (40min) → E (30min) → F (20min) → G (30min) → H (30min) → I (15min)
```

총 예상: ~3.5시간. 나머지 시간은 Phase D에서 에러가 나면 디버깅, Phase F 이후 모니터링에 할당.

## 핵심 원칙
1. **멈추지 마라.** 에러가 나면 기록하고 다음 Phase로 넘어가라.
2. **기록하라.** 모든 명령어 출력, 에러, 결정을 PROGRESS.md에 남겨라.
3. **검증하라.** Phase D의 dry-run이 성공해야만 Phase F로 넘어가라.
4. **건드리지 마라.** try03 디렉토리의 파일을 수정하지 마라. 읽기만 해라.
5. **모든 스크립트는 실행 가능해야 한다.** 작성 후 반드시 실행하여 동작을 확인하라.
