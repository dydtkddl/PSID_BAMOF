import sys
import os

def extract_frames(trj_path):
    """트라젝토리 파일에서 모든 프레임을 리스트로 추출"""
    with open(trj_path, 'r') as f:
        lines = f.readlines()

    frames = []
    i = 0
    while i < len(lines):
        if lines[i].strip().isdigit():
            atom_count = int(lines[i].strip())
            frame_lines = lines[i:i + atom_count + 2]
            frames.append(frame_lines)
            i += atom_count + 2
        else:
            i += 1
    return frames

def remove_atoms_from_frame(frame_lines, num_remove):
    """frame에서 앞에서부터 num_remove개의 원자를 제거하고, 원자 수 갱신"""
    atom_count = int(frame_lines[0].strip())
    new_atom_count = atom_count - num_remove
    if new_atom_count < 0:
        raise ValueError("삭제하려는 원자 수가 전체 원자 수보다 많습니다.")
    
    # 헤더 수정
    new_frame = [f"{new_atom_count}\n"] + frame_lines[1:2]  # comment line 유지
    # 원자 라인 중 일부 제거
    new_frame += frame_lines[2 + num_remove:]
    return new_frame

def save_xyz(frame_lines, path):
    """xyz 형식 파일 저장"""
    with open(path, 'w') as f:
        f.writelines(frame_lines)

def run_external_script(python_script, cif_path, xyz_path, output):
    """os.system으로 외부 파이썬 스크립트 실행"""
    cmd = f"python {python_script} {cif_path} {xyz_path} {output} 2 2 2"
    print(f"Running: {cmd}")
    os.system(cmd)

def main():
    if len(sys.argv) != 6:
        print("Usage: python process_trj.py <trj_file> <num_remove> <prefix> <python_script> <cif_file>")
        sys.exit(1)

    trj_file = sys.argv[1]
    num_remove = int(sys.argv[2])
    prefix = sys.argv[3]
    python_script = sys.argv[4]
    cif_file = sys.argv[5]

    # Step 1: 프레임 추출
    frames = extract_frames(trj_file)
    if len(frames) < 2:
        print("Error: 프레임이 2개 이상 필요합니다.")
        sys.exit(1)

    # Step 2: 첫 프레임 저장 (수정 없음)
    start_frame = remove_atoms_from_frame(frames[0], num_remove)

    # Step 3: 마지막 프레임에서 앞의 원자 제거
    final_frame = remove_atoms_from_frame(frames[-1], num_remove)

    # Step 4: 파일 저장
    start_path = f"{prefix}_start.xyz"
    final_path = f"{prefix}_final.xyz"
    start_path2 = f"{prefix}_start_2x2x2.xyz"
    final_path2 = f"{prefix}_final_2x2x2.xyz"
    save_xyz(start_frame, start_path)
    save_xyz(final_frame, final_path)

    # Step 5: 외부 파이썬 프로그램 실행
    run_external_script(python_script, cif_file, start_path,start_path2)
    run_external_script(python_script, cif_file, final_path,final_path2)

if __name__ == "__main__":
    main()
