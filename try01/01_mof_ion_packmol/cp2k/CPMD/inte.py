import os
import glob

def merge_pos_xyz(output_filename='inte.xyz'):
    # 결과 파일을 쓰기 모드로 엽니다. 기존에 있으면 덮어씁니다.
    with open(output_filename, 'w') as outfile:
        # try01 ~ try07 폴더 반복
        for i in range(1, 8):
            folder = f'try{str(i).zfill(2)}'
            # 폴더가 존재하는지 확인
            if not os.path.isdir(folder):
                print(f"Warning: '{folder}' 폴더가 없습니다. 건너뜁니다.")
                continue
            # *pos*.xyz 파일 찾기
            pattern = os.path.join(folder, '*pos*.xyz')
            files = sorted(glob.glob(pattern))
            if not files:
                print(f"Warning: '{folder}'에 매칭되는 파일이 없습니다.")
                continue
            # 각 파일 내용 이어쓰기
            for filepath in files:
                with open(filepath, 'r') as infile:
                    outfile.write(infile.read())
    print(f"모든 파일을 병합하여 '{output_filename}' 생성 완료.")

if __name__ == '__main__':
    merge_pos_xyz()

