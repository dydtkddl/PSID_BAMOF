import subprocess
from pathlib import Path
import argparse

def run_command(command, cwd):
    print(f"[▶] {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"[✗] 명령 실패: {command}")
        raise SystemExit(1)  # 실패 시 예외 발생

def run_simulation(sim_path, sim_name, nt):

    cmds = [
"gmx dump -f coords.xtc > coords_xtc_dump.txt"

            ]

    for cmd in cmds:
        try:
            run_command(cmd, cwd=sim_path)
        except SystemExit:
            print(f"[!] {sim_name}에서 명령어 실패로 시뮬레이션 중단, 다음 시뮬레이션으로 넘어갑니다.")
            break  # 해당 시뮬레이션 중단, 다음 시뮬레이션 진행

def main(sim_dir, start, end, nt):
    sim_dir = Path(sim_dir).resolve()

    for idx in range(start, end + 1):
        sim_name = f"IONIC_LIQUID{idx:04d}"
        sim_path = sim_dir / sim_name

        if not sim_path.exists():
            print(f"[!] 경고: {sim_path} 존재하지 않음. 건너뜀.")
            continue

        print(f"\n==============================")
        print(f"[🚀] 시작: {sim_name}")
        print(f"==============================")
        run_simulation(sim_path, sim_name, nt)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run GROMACS simulations in batch.")
    parser.add_argument("--sim_dir", required=True, help="Path to directory containing simulation subfolders")
    parser.add_argument("--start", type=int, required=True, help="Start index (e.g., 1)")
    parser.add_argument("--end", type=int, required=True, help="End index (e.g., 187)")
    parser.add_argument("--nt", type=int, default=8, help="Number of threads for mdrun")

    args = parser.parse_args()
    main(args.sim_dir, args.start, args.end, args.nt)

