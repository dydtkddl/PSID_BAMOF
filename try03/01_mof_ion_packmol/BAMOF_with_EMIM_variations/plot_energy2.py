import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FormatStrFormatter

# 스타일 설정
sns.set_style("whitegrid")

# 상수
HARTREE_TO_KJMOL = 2625.4996

# 데이터 로드
df = pd.read_csv('final_energies.csv')
df['Folder'] = df['Folder'].str.replace('/', '', regex=False)
df['Total_Energy_Hartree'] = df['Total_Energy_Hartree'].astype(str).str.replace('\r', '', regex=True).astype(float)

# 흡착 에너지 계산 (기준 에너지: -1362.308602 Hartree)
df['E_ads_kJmol'] = (df['Total_Energy_Hartree'] + 1362.308602) * HARTREE_TO_KJMOL

# 플롯
plt.figure(figsize=(12, 5))

# 노란색 계열 hex 코드: #EFCB68 (밝은 머스타드)
bars = plt.bar(
    df['Folder'],
    df['E_ads_kJmol'],
    color='#EFCB68',
    edgecolor='black'
)

# y축 범위 자동 설정
ymin = df['E_ads_kJmol'].min() - 5
ymax = df['E_ads_kJmol'].max() + 5
plt.ylim(ymin, ymax)

# 축 및 제목
plt.xlabel("EMIM Variants", fontsize=13)
plt.ylabel("Adsorption Energy [kJ/mol]", fontsize=13)
plt.title("Adsorption Energy of EMIM Variants on BAMOF", fontsize=14, weight='bold')
plt.xticks(rotation=45, fontsize=11)
plt.yticks(fontsize=11)

# 막대 위에 값 표시
for bar, val in zip(bars, df['E_ads_kJmol']):
    plt.text(bar.get_x() + bar.get_width()/2, val + 1, f"{val:.1f}",
             ha='center', va='bottom', fontsize=10)

# y축 숫자 포맷 고정
plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%.2f'))

# 레이아웃 조정 및 저장
plt.tight_layout()
plt.savefig("adsorption_energy_yellow.png", dpi=300)
plt.show()
