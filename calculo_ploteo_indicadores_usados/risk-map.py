import os
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.offsetbox import HPacker
import seaborn as sns

def graficar_alf_vs_lluvia(db_path, marker_size=300):
    if not os.path.exists(db_path):
        print(f"Error: La base de datos '{db_path}' no existe.")
        return

    print("Conectando y ejecutando analisis: Logging (ALF) vs Lluvia...")
    
    conn = sqlite3.connect(db_path)
    query = """
    SELECT
        CAST(strftime('%Y', fecha) AS INT) AS Year,
        UPPER(localidad) AS Locality,
        period AS Period,
        COUNT(*) AS total_clips,
        -- Indicador de Lluvia: % de clips con sonido físico de agua
        ROUND(SUM(CASE WHEN 
            LOWER(yamnet_label_1) LIKE '%water%' OR 
            LOWER(yamnet_label_1) LIKE '%stream%' OR 
            LOWER(yamnet_label_1) LIKE '%waterfall%' 
        THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS Lluvia_pct,
        -- ALF: % de clips con motosierras/herramientas sobre el total
        ROUND(SUM(CASE WHEN LOWER(yamnet_label_1) LIKE '%tool%' OR LOWER(yamnet_label_1) LIKE '%saw%' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS ALF_pct
    FROM clips
    WHERE status != 'ruido_extremo' 
      AND UPPER(localidad) IN ('12 DE ABRIL', 'PAUJIL', 'QUISTOCOCHA', 'SAN LUCAS', 'VARILLAL')
      AND CAST(strftime('%Y', fecha) AS INT) BETWEEN 2023 AND 2026
    GROUP BY Year, Period, Locality
    ORDER BY Year ASC, Locality ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty: return

    df["Locality"] = df["Locality"].astype(str).str.upper()
    df["Year"] = pd.to_numeric(df["Year"])
    
    period_translation = {
        "dia": "Diurnal", 
        "diurnal": "Diurnal", 
        "diurno (coros y actividad)": "Diurnal",
        "day": "Diurnal",
        "noche": "Nocturnal", 
        "nocturnal": "Nocturnal",
        "nocturno (grillos y generadores)": "Nocturnal",
        "night": "Nocturnal"
    }
    df["Period"] = df["Period"].astype(str).str.lower().map(lambda x: period_translation.get(x, x.capitalize()))
    

    df_daily = df.groupby(['Year', 'Locality'], as_index=False).agg({
        'Lluvia_pct': 'mean',
        'ALF_pct': 'mean',
        'total_clips': 'sum'
    })
    df_daily['Period'] = 'Daily'
    df = pd.concat([df, df_daily], ignore_index=True)

    period_colors = {"Diurnal": "#F2A467", "Nocturnal": "#104F55", "Daily": "#707070"}

    sns.set_theme(style="whitegrid")

    df_general = df.copy().groupby(['Year', 'Period'], as_index=False).agg({'Lluvia_pct': 'mean', 'ALF_pct': 'mean', 'total_clips': 'sum'})
    df_general['Locality'] = 'GENERAL (ALL)'
    df_combined = pd.concat([df_general, df], ignore_index=True)
    
    unique_localities = ['GENERAL (ALL)'] + sorted(df["Locality"].unique())
    unique_years = sorted(df_combined["Year"].unique())
    min_yr, max_yr = min(unique_years), max(unique_years)

    g = sns.FacetGrid(df_combined, col="Locality", col_order=unique_localities, col_wrap=3, height=5, aspect=1.2, sharex=True, sharey=True)
    
    #Trayectorias
    def draw_trajectories(data, **kwargs):
        for period in data["Period"].unique():
            period_data = data[data["Period"] == period].sort_values("Year")
            if len(period_data) > 1:
                plt.plot(
                    period_data["Lluvia_pct"], 
                    period_data["ALF_pct"], 
                    color=period_colors[period], 
                    linestyle='--', 
                    linewidth=1.8, 
                    alpha=0.5, 
                    zorder=1
                )

    g.map_dataframe(draw_trajectories)

    #Burbujas
    def scatter_with_alpha(data, **kwargs):
        for year in sorted(data["Year"].unique()):
            alpha_val = 0.3 + 0.7 * ((year - min_yr) / (max_yr - min_yr)) if max_yr != min_yr else 1.0
            year_data = data[data["Year"] == year]
            sns.scatterplot(data=year_data, x="Lluvia_pct", y="ALF_pct", hue="Period", palette=period_colors, s=marker_size, alpha=alpha_val, ec="white", legend=False, zorder=3)
            
    g.map_dataframe(scatter_with_alpha, linewidth=1.2)

    for ax in g.axes.flat:
        ax.set_title(ax.get_title().split(" = ")[-1], fontsize=13, fontweight='bold', pad=14, color='#222222')
        ax.set_xlabel("Hydrological Index (Rain %)", fontsize=11, fontweight='bold', labelpad=10)
        ax.set_ylabel("Logging Activity Index (ALF %)", fontsize=11, fontweight='bold', labelpad=10)
        ax.grid(True, linestyle=':', alpha=0.6)


    g.fig.subplots_adjust(top=0.80, left=0.08, right=0.95, bottom=0.1, hspace=0.4, wspace=0.25)
    
    year_labels = [str(int(y)) for y in unique_years]
    legend_configs = [
        ("Nocturnal", 0.28),
        ("Diurnal", 0.50),
        ("Daily", 0.72)
    ]

    for period, x_pos in legend_configs:
        handles = []
        for year in unique_years:
            alpha_val = 0.3 + 0.7 * ((year - min_yr) / (max_yr - min_yr)) if max_yr != min_yr else 1.0
            handles.append(Line2D([0], [0], marker='o', color='none', markerfacecolor=period_colors[period], 
                                  markeredgecolor='white', markersize=np.sqrt(marker_size)*0.65, alpha=alpha_val))
        
        leg = g.fig.legend(handles=handles, labels=year_labels, loc='upper center', bbox_to_anchor=(x_pos, 0.96),
                           ncol=len(unique_years), title=period, title_fontproperties={'weight': 'bold', 'size': 11},
                           columnspacing=1.4, handletextpad=-0.5, frameon=False)
        
        for text in leg.get_texts():
            text.set_fontsize(9)
            text.set_color('#555555')
            text.set_transform(text.get_transform() + plt.matplotlib.transforms.ScaledTranslation(0, -18/72, g.fig.dpi_scale_trans))
            text.set_ha('center')

        box = leg.get_children()[0]
        title_box = box.get_children()[0]
        title_box.get_children()[0].set_color('#222222')
        handle_box = box.get_children()[1]
        box.get_children().clear()
        box.get_children().append(HPacker(children=[handle_box, title_box], align="center", pad=0, sep=8))
    
    g.fig.suptitle("Ecoacoustic Environmental Correlation: Logging (ALF) vs Hydrological Index\n", fontsize=15, fontweight='bold', color='#111111')

    os.makedirs('output_fta', exist_ok=True)
    df_combined.to_csv('output_fta/data_correlation_alf_vs_rain.csv', index=False, encoding='utf-8-sig')

    plt.savefig('output_fta/burbujas_alf_vs_lluvia.png', dpi=300, bbox_inches='tight')
    print("✔️ ¡Gráfico ALF vs Lluvia guardado!")
    plt.show()

if __name__ == "__main__":
    graficar_alf_vs_lluvia(r'E:\audiomoth_2_discos - copia (2).sqlite', marker_size=300)
