#!/usr/bin/env python3
import glob, os, random

# --- 설정 ---
template_path = "base_gen.inp"
out_dir = "base_inputs"
structure_glob = "../BAMOF_plus_BMI_makesense/*wrapped*.xyz"

# 출력 디렉터리 생성
os.makedirs(out_dir, exist_ok=True)

# 템플릿 읽기
with open(template_path, 'r') as f:
    template = f.read()

# 파일별로 입력 파일 생성
for idx, struct_path in enumerate(sorted(glob.glob(structure_glob)), start=1):
    struct_name = os.path.basename(struct_path)
    # case index, seed 예시: 랜덤 1~1e6 사이
    seed = random.randint(1, 1_000_000)
    # 출력 파일명
    out_name = f"base_{os.path.splitext(struct_name)[0]}.inp"
    out_path = os.path.join(out_dir, out_name)
    # 템플릿 치환
    content = template.format(
        index=idx,
        structure=struct_name,
        seed=seed
    )
    # 파일에 저장
    with open(out_path, 'w') as fo:
        fo.write(content)
    print(f"Written: {out_path}")
