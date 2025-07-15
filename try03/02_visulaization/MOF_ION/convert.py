import subprocess
import pathlib

# 현재 디렉토리에서 .xyz 파일 모두 찾기
xyz_files = list(pathlib.Path('.').glob('*.xyz'))

# obabel 변환 루프
for xyz_file in xyz_files:
    mol2_file = xyz_file.with_suffix('.mol2')
    print(f"Converting: {xyz_file} -> {mol2_file}")

    # obabel 실행
    result = subprocess.run(['obabel', str(xyz_file), '-O', str(mol2_file)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # 결과 출력
    if result.returncode == 0:
        print(f"✅ Success: {mol2_file}")
    else:
        print(f"❌ Failed: {xyz_file}\n{result.stderr}")

