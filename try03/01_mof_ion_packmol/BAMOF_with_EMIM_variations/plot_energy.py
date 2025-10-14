import pandas as pd
import matplotlib.pyplot as plt

# CSV 파일 불러오기 (줄바꿈 문자 제거 포함)
df = pd.read_csv('final_energies.csv')
df['Folder'] = df['Folder'].str.replace('/', '', regex=False)
df['Total_Energy_Hartree'] = df['Total_Energy_Hartree'].astype(str).str.replace('\r', '', regex=True).astype(float)

# 플롯 설정
plt.figure(figsize=(12, 4))  # 가로로 긴 플롯
plt.plot(df['Folder'], df['Total_Energy_Hartree'], marker='o', linestyle='-', color='navy')

# 라벨/제목 등
plt.xlabel("EMIM Variants")
plt.ylabel("Total Energy [Hartree]")
plt.title("Total DFT Energy of Each EMIM Variation")
plt.xticks(rotation=45)
plt.grid(True)

# 저장 및 출력
plt.tight_layout()
plt.savefig("total_energy_plot.png", dpi=300)
plt.show()

