

import os 
files =[ "packmol_outputs/" + x for  x in os.listdir("packmol_outputs") ] 

for i in files:
    os.system(f"python packmol_filter_ver3.py BAMOF_cp2k_opt-1_102.cif {i} TFS.xyz dc")


