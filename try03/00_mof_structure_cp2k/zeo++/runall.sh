#!/usr/bin/env bash
# generate ASA (-sa) for probe radii from 1.2 to 2.5 Å in 0.1 Å steps
# for both MIL-125-NH2 and BA-MOF structures

# CIF filenames
MIL_CIF="MIL125-1.cif"
BAMOF_CIF="BAMOF_cp2k_opt-1.cif"

# Loop over probe radii
r=1.2
while (( $(echo "$r <= 2.5" | bc -l) )); do
  # format to one decimal place
  radius=$(printf "%.1f" "$r")

  # output filenames
  MIL_OUT="MIL125_sa_${radius}.sa"
  BAMOF_OUT="BAMOF_sa_${radius}.sa"

  echo "Running ASA for probe radius = ${radius} Å..."

  # MIL-125
  network -ha -sa "${radius}" "${radius}" 2000 "${MIL_OUT}" "${MIL_CIF}"

  # BA-MOF
  network -ha -sa "${radius}" "${radius}" 2000 "${BAMOF_OUT}" "${BAMOF_CIF}"

  # increment radius by 0.1
  r=$(echo "$r + 0.025" | bc -l)
done

