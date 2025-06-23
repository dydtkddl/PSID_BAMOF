import os 
dirs = [ 
        "03_ecut500",
        "02_ecut400",
        ]
import time

for dir in dirs:
    start = time.time()
    print("############# move to  %s ###########"%dir)
    print("Simulation Start!!!!!!!!!!!!!!!!!!!!!!")
    os.system("pwd && cd %s && mpirun -np 31 pw.x < input.in > input.out  && cd ../"%dir)
    print("Simulation Complete on %s"%(time.time() - start) )

