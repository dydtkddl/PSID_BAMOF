# try04 Progress

## Run started
- date: 2026-04-03
- Working note: OT SCF 마이그레이션 적용 후 수동 dry-run을 진행 중. dissociate도 OT 입력 동기화 완료.

## Phase A: 환경
- OS: Windows 11 / WSL2 Linux
- python3: available in WSL
- conda: manual setup/check pending
- numpy: 확인 후 필요 시 설치 예정
- docker: keti/cp2k:2025.2-gpu 사용 가능
- GPU: NVIDIA RTX 5090 (드라이버/SMI 확인 완료)
- CPU/Memory/Disk: 점검 완료 (요약된 값 반영)

## Phase B: 구조
- build_structures: PASS (192-atom 클러스터/디소시어티 2개 생성)
- validate_all.py: PASS (원자 수/거리/입력 파일 일치성 등 기본 검증)
- distance_report.py: generated
- visualization export: generated (`*_visual.xyz`, 셀 정보)

## Phase C: Docker
- image check: PASS (`keti/cp2k:2025.2-gpu`)
- CP2K 실행 환경 확인: 진행 중/완료된 실행 로그로 갱신 예정

## Phase D: SCF dry-run
- Last attempt (Broyden): FAILED (energy oscillation)
- 2IP 입력 파일 OT 마이그레이션 완료:
  - `02_calculations/BAMOF_2IP_cluster/input.inp`
  - `02_calculations/BAMOF_2IP_dissociate/input.inp`
- 적용 설정:
  - `MAX_SCF 300`, `EPS_SCF 5.0E-7`
  - `SCF_GUESS ATOMIC`
  - `&OT T` + `MINIMIZER DIIS`, `PRECONDITIONER FULL_ALL`, `ENERGY_GAP 0.01`
  - `&OUTER_SCF T` + `MAX_SCF 20`, `EPS_SCF 5.0E-7`
- 현재 상태: cluster OT dry-run 수동 실행 중, 최종 수렴 판정은 실행 종료 후 기록.

## Phase E: 모니터링 인프라
- monitor.sh: prepared (5분 폴링, 단계/에너지/force/SCF 실패 횟수/ETA/디스크 점검)
- `monitor.log`: append 기반 기록 포맷 정의

## Phase F: production
- run 준비 상태: OT 입력 동기화 완료, `run_cp2k_gpu.sh`는 dry-run PASS 이후 즉시 실행 가능
- run 시작 여부: pending

## Phase G: try03 교차검증
- extract_try03_energies.py: prepared
- extract_try03_structures.py: prepared (경로 정합성 수정 반영)
- structure comparison report: 생성 로직 준비(`structure_comparison.txt`)

## Phase H: SI Figure / 정리
- fig_ediss_comparison.py: prepared
- vesta_guide.md: prepared
- final_report.py: prepared
- `FINAL_REPORT.md`: 생성은 final_report.py 실행 후 반영

## Phase I: Git/문서
- .gitignore: prepared
- malformed `PROGRESS.md\\r` 정리: 사용자 실행 환경에서 확인 후 처리
- commit: dry-run 및 산출물 상태 확정 후 수행 예정

- 2026-04-03: OT ���� ���� ���� ���� ��Ʈ ���� �Ϸ� (���� ����, ���� ����)
  - 02_calculations/scripts: plan_a_ot_to_production.sh / plan_b_bootstrap.sh / plan_c_hybrid.sh / monitor_scf.sh / check_ot_status.sh ����
  - 02_calculations/BAMOF_2IP_dissociate/input_ot.inp ���� (OT dry-run ���ø� ���, MAX_ITER=2)
  - 03_postprocessing: plot_convergence.py / track_ion_distance.py / compute_ediss.py / export_final_structures.py �߰�/����
  - scripts/update_progress.sh �߰�
  - .gitignore ���� �߰�: *.log, *-pos-1.xyz, .worktmp_*
- ���� ��ġ: ����ڰ� OT ����� ���� Plan A/B/C �� 1�� ���� ��, �ش� ���� ���⹰���� `run` �غ� �ܰ�� ����
