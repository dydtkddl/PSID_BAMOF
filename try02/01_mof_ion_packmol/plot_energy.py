import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FormatStrFormatter
import re

# 상수
HARTREE_TO_KJMOL = 2625.4996
REFERENCE_ENERGY = -1376.074334  # 기준 에너지

# 스타일
sns.set_style("whitegrid")

# 데이터 로딩
df = pd.read_csv('bmi_final_energies.csv')
df['Folder'] = df['Folder'].str.replace('/', '', regex=False)
df['Total_Energy_Hartree'] = df['Total_Energy_Hartree'].astype(str).str.replace('\r', '', regex=True).astype(float)

# 📌 숫자 인덱스 추출하여 정렬 기준 열 만들기
df['Index'] = df['Folder'].apply(lambda x: int(re.findall(r'\d+', x)[0]))

# 정렬
df = df.sort_values('Index')

# 흡착 에너지 계산
df['E_ads_Hartree'] = df['Total_Energy_Hartree'] - REFERENCE_ENERGY
df['E_ads_kJmol'] = df['E_ads_Hartree'] * HARTREE_TO_KJMOL

# 플롯
plt.figure(figsize=(12, 5))
bars = plt.bar(df['Folder'], df['E_ads_kJmol'],
               color='#7FB77E', edgecolor='black')  # 초록 계열

# y축 범위 설정
ymin = df['E_ads_kJmol'].min() - 5
ymax = df['E_ads_kJmol'].max() + 5
plt.ylim(ymin, ymax)

# 라벨 및 제목
plt.xlabel("BAMOF + BMI Variant", fontsize=13)
plt.ylabel("Adsorption Energy [kJ/mol]", fontsize=13)
plt.title("Adsorption Energy of BAMOF + BMI Variants", fontsize=14, weight='bold')
plt.xticks(rotation=45, fontsize=11)
plt.yticks(fontsize=11)

# 막대 위 값 표시
for bar, val in zip(bars, df['E_ads_kJmol']):
    plt.text(bar.get_x() + bar.get_width()/2, val + 1, f"{val:.1f}",
             ha='center', va='bottom', fontsize=10)

# y축 숫자 형식
plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%.2f'))

# 저장 및 출력
plt.tight_layout()
plt.savefig("bmi_adsorption_energy_sorted.png", dpi=300)
plt.show()
