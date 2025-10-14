#!/usr/bin/env python3
import os
import re
import csv

# 파싱할 키와 대응되는 regex 패턴
METRICS = {
    "Unitcell_volume":    r"Unitcell_volume:\s*([\d\.]+)",
    "Density":            r"Density:\s*([\d\.]+)",
    "ASA_A2":             r"ASA_A\^2:\s*([\d\.]+)",
    "ASA_m2_per_cm3":     r"ASA_m\^2/cm\^3:\s*([\d\.]+)",
    "ASA_m2_per_g":       r"ASA_m\^2/g:\s*([\d\.]+)",
    "NASA_A2":            r"NASA_A\^2:\s*([\d\.]+)",
    "NASA_m2_per_cm3":    r"NASA_m\^2/cm\^3:\s*([\d\.]+)",
    "NASA_m2_per_g":      r"NASA_m\^2/g:\s*([\d\.]+)",
    "Number_of_channels": r"Number_of_channels:\s*([\d]+)",
    "Channel_surf_A2":    r"Channel_surface_area_A\^2:\s*([\d\.]+)",
    "Number_of_pockets":  r"Number_of_pockets:\s*([\d]+)",
    "Pocket_surf_A2":     r"Pocket_surface_area_A\^2:\s*([\d\.]+)"
}

# 결과 저장 리스트
rows = []

for fname in os.listdir("."):
    if not fname.endswith(".sa"): 
        continue

    # 파일명에서 구조 이름과 probe 반경 추출
    m = re.match(r"(BAMOF|MIL125)_sa_(\d+\.\d+)\.sa", fname)
    if not m:
        continue
    structure, radius = m.groups()

    # 파일 내용 읽기
    text = open(fname, encoding="utf-8").read().replace("\n", " ")

    # 한 행 데이터 생성
    row = {
        "structure": structure,
        "radius": radius,
    }
    # 각 메트릭 파싱
    for key, pattern in METRICS.items():
        mo = re.search(pattern, text)
        row[key] = mo.group(1) if mo else ""

    rows.append(row)

# CSV 쓰기
csv_cols = ["structure", "radius"] + list(METRICS.keys())
with open("asa_summary.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=csv_cols)
    writer.writeheader()
    for r in sorted(rows, key=lambda x: (x["structure"], float(x["radius"]))):
        writer.writerow(r)

print("asa_summary.csv 생성 완료")

