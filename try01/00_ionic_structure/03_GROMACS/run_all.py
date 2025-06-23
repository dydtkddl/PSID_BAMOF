import os
import argparse
import subprocess
from pathlib import Path

def run_command(command, cwd):
    print(f"[▶] {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"[✗] 명령 실패: {command}")
        exit(1)

def run_simulation(sim_path, sim_name, nt):
    pdb_file = f"{sim_name}.pdb"
    gro_file = f"{sim_name}.gro"

    cmds = [
        f"gmx editconf -f {pdb_file} -o {gro_file} -box 10 10 10",
        f"gmx grompp -f em.mdp -c {gro_file} -p topol.top -o em.tpr -v",
        f"gmx mdrun -deffnm em",
        f"gmx grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt",
        f"gmx mdrun -deffnm nvt -nt {nt}",
        f"gmx grompp -f npt.mdp -c nvt.gro -r nvt.gro -t nvt.cpt -p topol.top -o npt.tpr -maxwarn 1",
        f"gmx mdrun -deffnm npt -nt {nt}",
        f"gmx grompp -f md.mdp -c npt.gro -r npt.gro -t npt.cpt -p topol.top -o md.tpr -maxwarn 2",
        f"gmx mdrun -deffnm md -v -nt {nt}",
        f"echo 0 | gmx traj -f md.trr -s md.tpr -oxt coords.xtc"
    ]

    for cmd in cmds:
        run_command(cmd, cwd=sim_path)

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

