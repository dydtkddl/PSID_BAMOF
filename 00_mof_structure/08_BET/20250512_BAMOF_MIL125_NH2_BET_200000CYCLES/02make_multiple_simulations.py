import os
import argparse
import subprocess
from joblib import Parallel, delayed
from tqdm import tqdm

# pressure = "0.01"
pressures= [str(x) for x in [0.01,0.03,0.051,0.071,0.101,0.132,0.172,0.202,0.253,0.304]]
temp = "77"
gas = "N2"
base_input = "00base_template.input"
CUTOFFVDW = "14.0"
CUTOFFCHARGECHARGE = "14.0"
CUTOFFCHARGEBONDDIPOLE = "14.0"
CUTOFFBONDDIPOLEBONDDIPOLE = "14.0"


NumberOfCycles = "200000"
NumberOfInitializationCycles = "20000"
PrintEvery = "10000"

def run_simulation(mof,pressure):
    try:
        subprocess.run([
            "python", "01make_simulation.py",
            "--mof", mof,
            "--pressure", pressure,
            "--temp", temp,
            "--gas", gas,
            "--base_input", base_input,
            "--cutoffvdw", CUTOFFVDW,
            "--cutoffchargecharge", CUTOFFCHARGECHARGE,
            "--cutoffchargebonddipole", CUTOFFCHARGEBONDDIPOLE,
            "--cutoffbonddipolebonddipole", CUTOFFBONDDIPOLEBONDDIPOLE,
            "--NumberOfCycles", NumberOfCycles,
            "--NumberOfInitializationCycles", NumberOfInitializationCycles,
            "--PrintEvery", PrintEvery,
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error while executing simulation for {mof}: {e}")
    except Exception as e:
        print(f"Unexpected error for {mof}: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--n_jobs", 
        type=int, 
        default=1,
        help="Number of parallel jobs to run simultaneously (default=1)"
    )
    args = parser.parse_args()

    cif_list_path = "04cif_list.txt"
    with open(cif_list_path, "r") as file:
        cif_list = [line.strip() for line in file if line.strip()]

    print(f"Found {len(cif_list)} CIFs. Starting parallel processing with n_jobs={args.n_jobs} ...")
    Parallel(n_jobs=args.n_jobs)(
        delayed(run_simulation)(mof, pressure)
        for pressure in pressures
        for mof in cif_list
    )

if __name__ == "__main__":
    main()
