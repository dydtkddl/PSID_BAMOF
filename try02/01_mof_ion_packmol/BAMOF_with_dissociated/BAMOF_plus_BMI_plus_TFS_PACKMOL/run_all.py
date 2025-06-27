

import os 

files =[ "001/" + x for  x in os.listdir("001") ] 

for i in files:
    os.system(f"python packmol_filter_ver3.py   simulation.cif {i} TFS_FINAL_COORDINATE.xyz BAMOF_plus_BMI_plus_TFS_makesense/1") 

files =[ "002/" + x for  x in os.listdir("002") ] 

for i in files:
    os.system(f"python packmol_filter_ver3.py   simulation.cif {i} TFS_FINAL_COORDINATE.xyz BAMOF_plus_BMI_plus_TFS_makesense/2") 


files =[ "003/" + x for  x in os.listdir("003") ] 

for i in files:
    os.system(f"python packmol_filter_ver3.py   simulation.cif {i} TFS_FINAL_COORDINATE.xyz BAMOF_plus_BMI_plus_TFS_makesense/3") 


