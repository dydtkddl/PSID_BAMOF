

import os 
files =[ "packmol_outputs/" + x for  x in os.listdir("packmol_outputs") ] 

for i in files:
    os.system(f"python packmol_filter_ver3.py  BAMOF_BMI_GEOOPT-1.cif {i} TFS_FINAL_COORDINATE.xyz makesense") 


