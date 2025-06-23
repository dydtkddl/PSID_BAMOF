import os
import argparse
import itertools
import shutil

def parse_args():
    parser = argparse.ArgumentParser(
        description="Sweep EPS_SCF, CUTOFF, REL_CUTOFF in CP2K simulation.input template and run each case."
    )
    parser.add_argument(
        "--template", type=str, default="simulation.input",
        help="Path to the simulation.input template with {EPS_SCF}, {CUTOFF}, {REL_CUTOFF} placeholders."
    )
    parser.add_argument(
        "--eps-scf", type=str, required=True,
        help="Comma-separated list of EPS_SCF values to test, e.g. 1e-5,1e-4"
    )
    parser.add_argument(
        "--cutoff", type=str, required=True,
        help="Comma-separated list of MGRID CUTOFF values to test, e.g. 300,350,400"
    )
    parser.add_argument(
        "--rel-cutoff", type=str, required=True,
        help="Comma-separated list of MGRID REL_CUTOFF values to test, e.g. 30,40"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    # parse the lists
    eps_list = [s.strip() for s in args.eps_scf.split(',')]
    cutoff_list = [s.strip() for s in args.cutoff.split(',')]
    rel_cutoff_list = [s.strip() for s in args.rel_cutoff.split(',')]
    # parse other variables
 

    # read template
    with open(args.template) as f:
        template = f.read()

    # iterate combinations
    for eps, co, rco in itertools.product(eps_list, cutoff_list, rel_cutoff_list):
        dirname = f"run_eps{eps}_c{co}_r{rco}"
        if os.path.exists(dirname):
            shutil.rmtree(dirname)
        os.makedirs(dirname)
        # prepare input
        input_content = template.format(EPS_SCF=eps, CUTOFF=co, REL_CUTOFF=rco, )
        inp_path = os.path.join(dirname, "simulation.input")
        with open(inp_path, "w") as f:
            f.write(input_content)
        # run CP2K in container
        cmd = (
            "mkdir -p cp2k_scratch && echo '9582' | sudo -S podman run --rm "
            "-v \"$HOME/cp2k/data\":/opt/cp2k/data:Z "
            f"-v \"{os.path.abspath(dirname)}\":/work:Z -w /work "
            "docker.io/cp2k/cp2k:latest "
            "mpirun -n 7 -genv OMP_NUM_THREADS=4 "
            "cp2k -i simulation.input "
            "-o simulation.input.out "
            "> simulation.input.log 2>&1"
        )
        print(f"Running in {dirname}:")
        os.system(f"cd {dirname} && {cmd}")

if __name__ == "__main__":
    main()

