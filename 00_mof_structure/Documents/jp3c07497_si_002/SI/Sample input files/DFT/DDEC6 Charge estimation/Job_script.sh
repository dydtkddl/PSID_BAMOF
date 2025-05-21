#!/bin/sh
#SBATCH --job-name=FSR_Defects_Charge
#SBATCH -A gts-dsholl3-joe
#SBATCH -qembers
#SBATCH -N10
#SBATCH --ntasks-per-node=8
#SBATCH --time=8:00:00                     # Time limit hrs:min:sec
#SBATCH --mem-per-cpu=8G
#SBATCH --output=out
#SBATCH -pcpu-small
ulimit -s unlimited
echo $SLURM_SUBMIT_DIR
cd $SLURM_SUBMIT_DIR
module purge
module load intel/20.0.4
module load mvapich2/2.3.6-z2duuy
module load vasp/5.4.4
srun -n 80 /usr/local/pace-apps/manual/packages/vasp/5.4.4/mvapich2-2.3.6-z2duuy/intel-20.0.4/bin/vasp
