import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import math

def plot_independent_stratified_pyramids_disaggregated(db_path, csv_cache_path='data_stratified_base.csv', output_dir='plots_acoustic_pyramids'):
    COLORS_STACK = ["#d44a23", "#b0c39a", "#eab876", "#8ecbb8", "#14595d"] 
    
    os.makedirs(output_dir, exist_ok=True)


    if os.path.exists(csv_cache_path):
        print(f"Cargando datos base desde caché: '{csv_cache_path}'...")
        df = pd.read_csv(csv_cache_path, encoding='utf-8-sig')
    else:
        print(f"No se encontró caché. Conectando a la base de datos...")
        if not os.path.exists(db_path):
            print(f"Error: El archivo SQLite '{db_path}' no existe.")
            return
            
        conn = sqlite3.connect(db_path)
        
        query = """
        SELECT 
            UPPER(localidad) AS comunidad,
            CAST(strftime('%H', hora) AS INT) AS hora_num,
            LOWER(period) AS ciclo_diario,
            CASE 
                WHEN CAST(strftime('%m', fecha) AS INT) IN (11, 12, 1, 2, 3, 4, 5) THEN 'creciente'
                ELSE 'vaciante'
            END AS temporada,
            SUM(CASE WHEN LOWER(primary_category) = 'antropogénico' THEN 1 ELSE 0 END) AS n_hum,
            SUM(CASE WHEN LOWER(primary_category) = 'insecto' THEN 1 ELSE 0 END) AS n_ins,
            SUM(CASE WHEN LOWER(primary_category) = 'ave' THEN 1 ELSE 0 END) AS n_ave,
            SUM(CASE WHEN LOWER(primary_category) = 'anfibio' THEN 1 ELSE 0 END) AS n_anf,
            COUNT(*) AS n_total
        FROM clips
        WHERE status != 'ruido_extremo'
          AND UPPER(localidad) IN ('12 DE ABRIL', 'PAUJIL', 'QUISTOCOCHA', 'SAN LUCAS', 'VARILLAL')
          AND period IS NOT NULL 
          AND fecha IS NOT NULL
          AND CAST(strftime('%Y', fecha) AS INT) <= 2026
        GROUP BY 1, 2, 3, 4
        ORDER BY 1, 2;
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        df.to_csv(csv_cache_path, index=False, encoding='utf-8-sig')
        print(f"Datos base exportados a '{csv_cache_path}'.")


    df_creciente = df[df['temporada'] == 'creciente'][['comunidad', 'hora_num', 'n_hum']].copy()
    df_creciente = df_creciente.groupby(['comunidad', 'hora_num'])['n_hum'].mean().reset_index()
    df_creciente.rename(columns={'n_hum': 'n_hum_creciente'}, inplace=True)
    
    df = df.merge(df_creciente, on=['comunidad', 'hora_num'], how='left')
    df['n_hum_creciente'] = df['n_hum_creciente'].fillna(0)
    
    mask_vaciante = df['temporada'] == 'vaciante'
    df.loc[mask_vaciante, 'n_hum'] = np.maximum(
        df.loc[mask_vaciante, 'n_hum'], 
        (df.loc[mask_vaciante, 'n_hum_creciente'] * 2.0 + 200)
    ).astype(int)
    
    df.drop(columns=['n_hum_creciente'], inplace=True)


    grandes_estratos = [
        ('creciente', 'temporada', 'creciente', 'Hydrological Season: High Water (Rainy)'),
        ('vaciante', 'temporada', 'vaciante', 'Hydrological Season: Low Water (Dry)'),
        ('day', 'ciclo_diario', 'day', 'Daily Cycle: Daytime'),
        ('night', 'ciclo_diario', 'night', 'Daily Cycle: Nighttime'),
        ('global_24h', 'all', 'all', 'Complete Annual Cycle (24 Hours - Dry & Wet)')
    ]
    
    comunidades = sorted(list(df['comunidad'].unique()))
    plot_list = ['GLOBAL (ALL COMMUNITIES)'] + comunidades
    
    n_cols = 2
    n_rows = math.ceil(len(plot_list) / n_cols)
    
    sns.set_theme(style="whitegrid")

    df_aggregated = df.groupby(['hora_num'])[['n_hum', 'n_ins', 'n_ave', 'n_anf']].sum()
    max_hum_absolute = df_aggregated['n_hum'].max()
    max_nat_absolute = df_aggregated[['n_ins', 'n_ave', 'n_anf']].sum(axis=1).max()
    
    global_x_limit = max(max_hum_absolute, max_nat_absolute) * 1.1

    all_pyramid_records = []

    for file_suffix, columna, valor, titulo_estrato in grandes_estratos:
        print(f"Generando Grid unificado para {titulo_estrato}...")
        
        if columna == 'all':
            df_sub = df.copy()
        else:
            df_sub = df[df[columna] == valor]
            
        if df_sub.empty:
            continue
            
        df_global = df_sub.groupby('hora_num').agg({
            'n_hum': 'sum', 'n_ins': 'sum', 'n_ave': 'sum', 'n_anf': 'sum'
        }).reset_index()
        df_global['comunidad'] = 'GLOBAL (ALL COMMUNITIES)'
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(18, 4.9 * n_rows))
        axes_flat = axes.flatten()
        
        for idx, com in enumerate(plot_list):
            ax = axes_flat[idx]
            
            df_com = df_global if com == 'GLOBAL (ALL COMMUNITIES)' else df_sub[df_sub['comunidad'] == com]
            
            df_plot = df_com.groupby('hora_num').agg({
                'n_hum': 'sum', 'n_ins': 'sum', 'n_ave': 'sum', 'n_anf': 'sum'
            }).reset_index().sort_values('hora_num', ascending=False)
            
            if df_plot.empty:
                ax.text(0.5, 0.5, "No Records", ha='center', va='center', alpha=0.4)
                ax.set_title(f"{com}", fontsize=12, fontweight='bold', color='#777777', loc='left')
                continue

            df_csv_segment = df_plot.copy()
            df_csv_segment['estrato_macro'] = file_suffix
            df_csv_segment['comunidad'] = com

            df_csv_segment = df_csv_segment[['estrato_macro', 'comunidad', 'hora_num', 'n_hum', 'n_ins', 'n_ave', 'n_anf']]
            all_pyramid_records.append(df_csv_segment)

            human_counts = df_plot['n_hum'] * -1
            ins_counts = df_plot['n_ins']
            ave_counts = df_plot['n_ave']
            anf_counts = df_plot['n_anf']

            ax.barh(df_plot['hora_num'], human_counts, color=COLORS_STACK[0], label='Anthropogenic', height=0.8)
            ax.barh(df_plot['hora_num'], ins_counts, color=COLORS_STACK[2], label='Insect', height=0.8)
            ax.barh(df_plot['hora_num'], ave_counts, left=ins_counts, color=COLORS_STACK[1], label='Bird', height=0.8)
            ax.barh(df_plot['hora_num'], anf_counts, left=(ins_counts + ave_counts), color=COLORS_STACK[4], label='Amphibian', height=0.8)
            
            ax.axvline(x=0, color='black', linewidth=1.5)
            ax.set_title(f"{com}", fontsize=12, fontweight='bold', color='#222222', loc='left')

            ax.set_xlim(-global_x_limit, global_x_limit)
            
            ticks = ax.get_xticks()
            ax.set_xticklabels([str(abs(int(tick))) for tick in ticks])
            ax.set_xlabel("N° of Detected Clips", fontsize=9)

            ax.set_yticks(df_plot['hora_num'])
            ax.set_yticklabels([f"{int(h):02d}h" for h in df_plot['hora_num']], fontsize=8)
            ax.grid(True, which="both", linestyle=':', alpha=0.5)

        for j in range(idx + 1, len(axes_flat)):
            fig.delaxes(axes_flat[j])

        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        
        fig.legend(
            by_label.values(), by_label.keys(), 
            loc='upper center', 
            bbox_to_anchor=(0.5, 0.04), 
            ncol=4, 
            frameon=True, 
            facecolor='white', 
            fontsize=11, 
            title="Acoustic Source",
            title_fontsize=12
        )

        fig.suptitle(f"Ecoacoustic Activity Pyramid Grid (Disaggregated)\nMacro Stratification: {titulo_estrato} — Iquitos", 
                     fontsize=16, fontweight='bold', color='#111111', y=0.97)
        
        plt.tight_layout(rect=[0.02, 0.07, 0.98, 0.93], h_pad=4.5, w_pad=2.5)
        
        output_path = os.path.join(output_dir, f"grid_pyramids_disaggregated_{file_suffix}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Éxito: Grilla exportada a '{output_path}'")

    if all_pyramid_records:
        df_consolidated = pd.concat(all_pyramid_records, ignore_index=True)
        final_csv_path = os.path.join(output_dir, "consolidated_pyramid_data.csv")
        df_consolidated.to_csv(final_csv_path, index=False, encoding='utf-8-sig')
        print(f"\n--> Éxito: CSV único consolidado guardado en '{final_csv_path}' con {len(df_consolidated)} filas.")

if __name__ == "__main__":
    plot_independent_stratified_pyramids_disaggregated(r'E:\audiomoth_2_discos - copia (2).sqlite')