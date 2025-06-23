import os
import shutil
import argparse

def main(pdbs_dir, basefile_dir, output_dir):
    # 모든 pdb 파일 순회
    for filename in sorted(os.listdir(pdbs_dir)):
        if filename.endswith(".pdb"):
            pdb_path = os.path.join(pdbs_dir, filename)
            pdb_basename = os.path.splitext(filename)[0]
            target_dir = os.path.join(output_dir, pdb_basename)

            # 하위 디렉토리 생성
            os.makedirs(target_dir, exist_ok=True)

            # pdb 파일 복사
            shutil.copy(pdb_path, target_dir)

            # basefile_dir의 모든 파일 복사
            for basefile in os.listdir(basefile_dir):
                basefile_path = os.path.join(basefile_dir, basefile)
                shutil.copy(basefile_path, target_dir)

            print(f"[✔] {filename} → {target_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy and organize PDB systems with base input files")
    parser.add_argument("--pdbs_dir", required=True, help="Directory containing PDB files")
    parser.add_argument("--basefile_dir", required=True, help="Directory containing base input files")
    parser.add_argument("--output_dir", required=True, help="Directory to save organized folders")

    args = parser.parse_args()
    main(args.pdbs_dir, args.basefile_dir, args.output_dir)

