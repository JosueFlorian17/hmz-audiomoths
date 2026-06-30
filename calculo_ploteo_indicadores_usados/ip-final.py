import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import json
import os


CAT_TRANS = {
    "Antropogénico": "Anthropogenic", 
    "Anfibio": "Amphibian", "Insecto": "Insect", "Ave": "Bird"
}
PERIOD_TRANS = {
    "Amanecer Crítico": "Dawn", 
    "Anochecer Crítico": "Dusk"
}


try:
    with open('ip-final-final.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    df_iph = pd.DataFrame(data['rows'])
except FileNotFoundError:
    print("Error: No se encontró el archivo 'ip-final-final.json'. Verifica la ruta.")
    exit()


df_iph = df_iph[df_iph['categoria'].notna()]
df_iph = df_iph[~df_iph['categoria'].str.strip().str.lower().isin(['ruido ambiental', 'silencio'])]


df_iph = df_iph[~df_iph['categoria'].str.strip().str.lower().isin(['mamífero', 'mammal'])]
COLORS_STACK_NO_MAMMAL = ["#d44a23", "#eab876", "#8ecbb8", "#14595d"] 


df_iph['comunidad'] = df_iph['comunidad'].astype(str).str.strip().str.upper()


comunidades_validas = ['12 DE ABRIL', 'PAUJIL', 'QUISTOCOCHA', 'SAN LUCAS', 'VARILLAL']
df_iph = df_iph[df_iph['comunidad'].isin(comunidades_validas)]

df_iph['temporada_base'] = pd.to_numeric(df_iph['temporada_base'], errors='coerce')


df_iph = df_iph[df_iph['temporada_base'].isin([2024, 2025])]

# Aplicar traducciones asegurando que si no encuentra, mantenga el original
df_iph['categoria'] = df_iph['categoria'].map(CAT_TRANS).fillna(df_iph['categoria'])
df_iph['periodo_analisis'] = df_iph['periodo_analisis'].map(PERIOD_TRANS).fillna(df_iph['periodo_analisis'])


seasons = ["Creciente", "Vaciante"]
periods = ['Dawn', 'Dusk']


years_to_plot = ['General', 2025, 2024]


categorias_orden = [cat for cat in CAT_TRANS.values() if cat in df_iph['categoria'].unique()]
if not categorias_orden:
    categorias_orden = list(df_iph['categoria'].unique())

output_dir = "seasonal_plots"
os.makedirs(output_dir, exist_ok=True)

for season in seasons:
    df_season = df_iph[df_iph['ciclo_hidrologico'] == season]
    if df_season.empty:
        print(f"No hay datos en absoluto para la temporada: {season}")
        continue

    n_rows = len(years_to_plot)
    n_cols = len(periods)
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 5 * n_rows), squeeze=False, sharey=True)
    handles, labels = [], []
    
    for i, row_key in enumerate(years_to_plot):
        for k, period in enumerate(periods):
            ax = axes[i, k]
            

            if row_key == 'General':
                # Consolida 2024 y 2025 (2023 ya quedó fuera en el filtro inicial)
                data_plot = df_season[df_season['periodo_analisis'] == period]
                title_label = f"General (2024-2025) {season} - {period}"
            else:
                # Filtra el año específico (2024 o 2025)
                data_plot = df_season[
                    (df_season['temporada_base'] == row_key) & 
                    (df_season['periodo_analisis'] == period)
                ]
                title_label = f"{row_key} {season} - {period}"

            if data_plot.empty:
                ax.text(0.5, 0.5, f"No Data\n{title_label}", ha='center', va='center')
                ax.set_title(title_label, fontsize=12, fontweight='bold')
                continue


            sns.barplot(
                data=data_plot, 
                x='categoria', 
                y='porcentaje_promedio', 
                hue='comunidad',
                hue_order=comunidades_validas,
                order=categorias_orden,
                palette=COLORS_STACK_NO_MAMMAL, 
                ax=ax,
                edgecolor="black",
                errorbar=None 
            )

            if not handles:
                handles, labels = ax.get_legend_handles_labels()


            ax.set_title(title_label, fontsize=12, fontweight='bold')
            ax.set_xlabel("")
            ax.set_ylabel("% Penetration" if k == 0 else "")
            
            if ax.get_legend():
                ax.get_legend().remove()


    if handles:
        fig.legend(handles, labels, title="Comunidades", loc='center right', bbox_to_anchor=(0.98, 0.5), fontsize=12, title_fontsize=14)
    
    plt.tight_layout(rect=[0, 0, 0.86, 1])
    
    df_season.to_csv(os.path.join(output_dir, f"data_penetration_{season.lower()}.csv"), index=False, encoding='utf-8-sig')

    save_path = os.path.join(output_dir, f"biodiversity_{season.lower()}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {save_path}")