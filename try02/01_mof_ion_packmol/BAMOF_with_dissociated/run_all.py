

import os 
files =[ "BAMOF_plus_BMI_PACKMOL/packmol_outputs/" + x for  x in os.listdir("BAMOF_plus_BMI_PACKMOL/packmol_outputs") ] 

for i in files:
    os.system(f"python packmol_filter_ver3.py  BAMOF_FINAL_CELL_OPT.cif {i} BMI_FINAL_COORDINATE.xyz BAMOF_plus_BMI_makesense") 


