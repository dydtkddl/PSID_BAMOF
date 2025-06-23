import os
import argparse
from tqdm import tqdm
import subprocess

'''
사용법 예시:
1) baseinput.inp 파일 작성
2) python packmol_batch.py \
     --baseinput ./baseinput.inp \
     --output ./myoutputs \
     --inputdir ./myinputs \
     --ncases 50 \
     --packmol packmol \
     --verbose
'''
TIMEOUT_THRES = 1
# ---------------------------------------
# 1. 커맨드라인 인자 파싱
# ---------------------------------------
# 목적: 사용자가 base input, 출력 디렉토리, 케이스 수 등을 CLI로 설정 가능하게 함.
parser = argparse.ArgumentParser(description="Generate and run multiple Packmol jobs.")
parser.add_argument('--baseinput', type=str, default='./baseinput.inp',
                    help='Base Packmol input template file path (default: ./baseinput.inp)')
parser.add_argument('--output', type=str, default='packmol_outputs',
                    help='Output directory path (default: ./packmol_outputs)')
parser.add_argument('--inputdir', type=str, default='packmol_inputs',
                    help='Directory to store generated Packmol input files (default: ./packmol_inputs)')
parser.add_argument('--ncases', type=int, default=100,
                    help='Number of cases to generate (default: 100)')
parser.add_argument('--packmol', type=str, default='packmol',
                    help='Packmol executable path (default: packmol)')
parser.add_argument('--verbose', action='store_true',
                    help='Show detailed output per case (default: False)')
args = parser.parse_args()
# 인자 할당
baseinput_path = args.baseinput
output_dir = args.output
input_dir = args.inputdir
n_cases = args.ncases
packmol_path = args.packmol
verbose = args.verbose

# ---------------------------------------
# 2. 템플릿 파일 읽기
# ---------------------------------------
# 목적: 반복 생성할 Packmol input의 base 템플릿 확보
if not os.path.exists(baseinput_path):
    raise FileNotFoundError(f"❌ Base input file not found: {baseinput_path}")

with open(baseinput_path, 'r') as f:
    baseinput = f.read()

template = baseinput  # index 및 seed를 format으로 치환할 예정

# ---------------------------------------
# 3. 출력 및 입력 디렉토리 생성
# ---------------------------------------
# 목적: 자동으로 결과 및 입력 파일을 보관할 디렉토리 생성
os.makedirs(input_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# ---------------------------------------
# 4. Packmol 입력 파일 생성 및 실행
# ---------------------------------------
# 목적: 각 케이스마다 input 파일 생성 + 실행 + 성공/실패/타임아웃 집계
success_count = 0
fail_count = 0
timeout_count = 0

# 비활성화 모드에서는 tqdm 프로그레스 바 사용
progress = tqdm(range(1, n_cases + 1)) if not verbose else range(1, n_cases + 1)

for i in progress:
    index = f"{i:03d}"     # 파일명 001 ~ n 형식
    seed = 1000 + i        # Seed 값 고유하게 설정

    inp_filename = f"packmol_case_{index}.inp"
    inp_path = os.path.join(input_dir, inp_filename)
    output_filename = f"case_{index}.xyz"

    # ▶ 입력 파일 생성 (index, seed 포맷 채우기)
    with open(inp_path, "w") as f:
        f.write(template.format(index=index, seed=seed))

    # ▶ Packmol 실행 명령어 (output 디렉토리에서 실행)
    cmd = f"cd {output_dir} && {packmol_path} < ../{inp_path}"
    if verbose:
        print(f"▶ Running Packmol for case {index}...")

    try:
        # verbose=True인 경우: 로그 출력 유지
        # verbose=False인 경우: stdout/stderr 무시 + 타임아웃 처리
        if verbose:
            result = subprocess.run(cmd, shell=True, timeout=3)
        else:
            result = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=TIMEOUT_THRES)

        if result.returncode == 0:
            success_count += 1
            if verbose:
                print(f"✅ case_{index}.xyz 생성 완료.")
        else:
            fail_count += 1
            if verbose:
                print(f"❌ 오류 발생 (case {index})")

    except subprocess.TimeoutExpired:
        # ▶ 3초 초과 시 subprocess 강제 종료 처리
        timeout_count += 1
        if verbose:
            print(f"⏰ 타임아웃 발생 (case {index}) — 3초 초과")

# ---------------------------------------
# 5. 모든 결과를 integrate.xyz로 병합
# ---------------------------------------
# 목적: 생성된 모든 Packmol 결과물을 하나의 .xyz 파일로 통합
print("\n📦 Packmol 실행 완료. 이제 integrate.xyz 파일 생성 중...")

output_path = "integrate.xyz"
prefix = "case_"
suffix = ".xyz"

with open(output_path, "w") as outfile:
    for i in range(1, n_cases + 1):
        case_filename = f"{prefix}{i:03d}{suffix}"
        full_path = os.path.join(output_dir, case_filename)
        if os.path.isfile(full_path):
            with open(full_path, "r") as infile:
                lines = infile.readlines()
                outfile.writelines(lines)
        else:
            print(f"⚠️ 파일 없음: {case_filename}")

# ---------------------------------------
# 6. 최종 통계 출력
# ---------------------------------------
print(f"\n✅ 모든 케이스가 병합된 integrate.xyz → 현재 디렉토리에 저장 완료!")
print("\n📊 실행 요약:")
print(f"   ⏱️ 타임아웃: {timeout_count}개")
print(f"   ❌ 실패:     {fail_count}개")
print(f"   ✅ 성공:     {success_count}개 / {n_cases}개")
