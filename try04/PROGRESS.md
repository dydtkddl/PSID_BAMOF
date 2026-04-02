# try04 Progress

## Run started
- date: 2026-04-02T23:08:49+09:00

## Phase A: Environment
- uname: Linux DESKTOP-KACI42S 6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun  5 18:30:46 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux
- python3: Python 3.10.12
- pip3: pip 22.0.2
- docker: Docker version 29.3.0, build 5927d80
- docker images cp2k:
keti/cp2k:2025.2-gpu                   d061199be03b         13GB         4.24GB   U    
nvcr.io/hpc/cp2k:v2024.3               b0abdcbfe014       47.1GB         13.6GB        
- cpu model: AMD Ryzen Threadripper PRO 9965WX 24-Cores
- memory: 62Gi 18Gi 43Gi
- disk /mnt/d: 11T 1.4T 9.6T 13%
- nvidia-smi:
Thu Apr  2 23:08:50 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 595.54                 Driver Version: 595.79         CUDA Version: 13.2     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 5090        On  |   00000000:F1:00.0  On |                  N/A |
| 30%   36C    P1             81W /  575W |    7762MiB /  32607MiB |      3%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|  No running processes found                                                             |
+-----------------------------------------------------------------------------------------+
- conda: NOT_FOUND
- numpy: MISSING

## Phase A-2: try03 references
- directory: /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_Cluster-1/
total 20480
drwxrwxrwx 1 yongsang yongsang    4096 Jul 20  2025 .
drwxrwxrwx 1 yongsang yongsang    4096 Jul 20  2025 ..
- directory: /mnt/d/PSID_BAMOF/try03/01_mof_ion_packmol/BAMOF_EMIM_TFSI_dissociate-1/
total 16852
drwxrwxrwx 1 yongsang yongsang    4096 Jul 20  2025 .
drwxrwxrwx 1 yongsang yongsang    4096 Jul 20  2025 ..
- directory: /mnt/d/PSID_BAMOF/try03/00_ionic_structure_cp2k/Cluster01/
total 6180
drwxrwxrwx 1 yongsang yongsang    4096 Jul 28  2025 .
drwxrwxrwx 1 yongsang yongsang    4096 Jul 15  2025 ..
- try03 cluster final line:  ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]          -1613.798428568382178
- try03 dissociate final line:  ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]          -1613.784873692176006

## Phase A.4: Conda 환경 준비
- conda: NOT_FOUND (attempting miniconda install)
- conda: installed at /tmp/miniconda3/bin/conda

- conda bin: /tmp/miniconda3/bin/conda
- conda version: conda 26.1.1
- conda env: created try04-cp2k
- numpy in try04-cp2k: 2.2.6
## Phase B: 구조 생성/검증
- B-1 build_structures.py 실행: PASS
- 생성 파일:
  - 02_calculations/BAMOF_2IP_cluster/BAMOF_2IP_cluster_init.xyz (192 atoms)
  - 02_calculations/BAMOF_2IP_dissociate/BAMOF_2IP_dissociate_init.xyz (192 atoms)
- B-2 validate_all.py 실행: PASS
  - cluster: PASS
  - dissociate: PASS
  - 2nd EMIM-TFSI 거리(cluster: 2.1546 Å, dissociate: 9.1149 Å)
- B-3 export_visualization.py 실행: PASS
  - *_visual.xyz / *_cell.cif / *_POSCAR.vasp 생성
- B-4 distance_report.py 실행: PASS
  - distance_report.txt 생성
## Phase C: Docker 환경
- docker images cp2k: checked
  - keti/cp2k:2025.2-gpu (exists)
  - nvcr.io/hpc/cp2k:v2024.3 (exists)
  - cp2k/cp2k:latest (pulled success)
  - cp2k-try04:2024.3-gpu (built from local Dockerfile)
- Host cp2k data
  - ~/cp2k/data/BASIS_MOLOPT: MISSING
  - ~/cp2k/data/GTH_POTENTIALS: MISSING
  - ~/cp2k/data/dftd3.dat: MISSING
- cp2k/cp2k:latest container check: /opt/cp2k/data path is absent
- keti/cp2k:2025.2-gpu data path contains /opt/cp2k/data (includes BASIS_MOLOPT, GTH_POTENTIALS, dftd3)
- CP2K version check
  - keti/cp2k:2025.2-gpu with --gpus=all: CP2K version 2024.3 (git 6712648)
  - cp2k-try04:2024.3-gpu and base images may require --gpus=all for version/runtime due libcuda dependency
