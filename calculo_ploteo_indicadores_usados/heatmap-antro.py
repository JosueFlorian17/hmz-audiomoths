import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
from matplotlib.colors import LinearSegmentedColormap

def crear_directorio(nombre_dir):
    if not os.path.exists(nombre_dir):
        os.makedirs(nombre_dir)

def generar_heatmaps_apilados_globales(db_path, output_dir='output_heatmaps_globales'):
    crear_directorio(output_dir)
    
    localidades = ["12 DE ABRIL", "PAUJIL", "QUISTOCOCHA", "SAN LUCAS", "VARILLAL"]
    localidades_str = '("' + '", "'.join(localidades) + '")'
    horas_del_dia = list(range(24)) 
    
    print(f"Conectando a la base de datos: {db_path}")
    conn = sqlite3.connect(db_path)

    print("\n--- Procesando Gráfico Apilado Antropogénico... ---")
    query_anthro = f"""
    WITH clips_base AS (
        SELECT 
            localidad,
            CAST(strftime('%Y', fecha) AS INT) AS anio,
            CAST(strftime('%H', hora) AS INT) AS hora_del_dia, -- CORREGIDO: Usar columna 'hora'
            CASE 
                WHEN strftime('%m', fecha) BETWEEN '06' AND '10' THEN 'Dry Season'
                ELSE 'Rainy Season'
            END AS ciclo_hidrologico,
            CASE 
                WHEN LOWER(primary_category) = 'antropogénico' THEN 1 
                ELSE 0 
            END AS es_antropogenico
        FROM clips
        WHERE status != 'ruido_extremo' 
          AND localidad IN {localidades_str}
          AND primary_category IS NOT NULL
          AND strftime('%Y', fecha) != '2023' -- Exclusión de 2023
    )
    SELECT 
        ciclo_hidrologico,
        anio,
        localidad,
        hora_del_dia,
        ROUND(CAST(SUM(es_antropogenico) AS FLOAT) * 100 / COUNT(*), 4) AS pct_anthro
    FROM clips_base
    GROUP BY 1, 2, 3, 4;
    """
    df_anthro_raw = pd.read_sql_query(query_anthro, conn)
    
    if not df_anthro_raw.empty:
        df_anthro = df_anthro_raw.groupby(['ciclo_hidrologico', 'localidad', 'hora_del_dia'])['pct_anthro'].mean().reset_index()
        
        blue_colors = ["#f0f4f8", "#6baed6", "#2171b5", "#14595d"]
        custom_blue_cmap = LinearSegmentedColormap.from_list("AnthroBlues", blue_colors)
        vmax_anthro = max(df_anthro['pct_anthro'].max(), 1.0)

        fig, axes = plt.subplots(2, 1, figsize=(11, 10))
        
        df_rainy = df_anthro[df_anthro['ciclo_hidrologico'] == 'Rainy Season']
        pivot_rainy = df_rainy.pivot(index='localidad', columns='hora_del_dia', values='pct_anthro').fillna(0)
        pivot_rainy = pivot_rainy.reindex(index=localidades, columns=horas_del_dia, fill_value=0)
        pivot_rainy.to_csv(os.path.join(output_dir, 'matrix_anthro_rainy.csv'), encoding='utf-8-sig') # <-- NUEVO
        
        sns.heatmap(pivot_rainy, annot=False, cmap=custom_blue_cmap, ax=axes[0], 
                    cbar_kws={'label': '% Anthropogenic'}, vmin=0.0, vmax=vmax_anthro)
        axes[0].set_title("GLOBAL (All Years) - Rainy Season", fontsize=12, fontweight='bold')
        axes[0].set_xlabel("Hour")
        axes[0].set_ylabel("Community")


        df_dry = df_anthro[df_anthro['ciclo_hidrologico'] == 'Dry Season']
        pivot_dry = df_dry.pivot(index='localidad', columns='hora_del_dia', values='pct_anthro').fillna(0)
        pivot_dry = pivot_dry.reindex(index=localidades, columns=horas_del_dia, fill_value=0)
        pivot_dry.to_csv(os.path.join(output_dir, 'matrix_anthro_dry.csv'), encoding='utf-8-sig') # <-- NUEVO

        sns.heatmap(pivot_dry, annot=False, cmap=custom_blue_cmap, ax=axes[1], 
                    cbar_kws={'label': '% Anthropogenic'}, vmin=0.0, vmax=vmax_anthro)
        axes[1].set_title("GLOBAL (All Years) - Dry Season", fontsize=12, fontweight='bold')
        axes[1].set_xlabel("Hour")
        axes[1].set_ylabel("Community")

        fig.suptitle("Seasonal Human Activity Heatmap\n(Excluyendo Año 2023)", fontsize=16, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        output_anthro_path = os.path.join(output_dir, 'grid_anthro_global_24h.png')
        plt.savefig(output_anthro_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Exportado exitosamente: {output_anthro_path}")


    print("\n--- Procesando Gráfico Apilado de Tala (ALF)... ---")
    query_fta = f"""
    WITH clips_base AS (
        SELECT 
            localidad,
            CAST(strftime('%Y', fecha) AS INT) AS anio,
            CAST(strftime('%H', hora) AS INT) AS hora_del_dia, -- CORREGIDO: Usar columna 'hora'
            CASE 
                WHEN strftime('%m', fecha) BETWEEN '06' AND '10' THEN 'Dry Season'
                ELSE 'Rainy Season'
            END AS ciclo_hidrologico,
            CASE 
                WHEN LOWER(yamnet_label_1) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
                  OR LOWER(yamnet_label_2) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
                  OR LOWER(yamnet_label_3) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
                  OR LOWER(yamnet_label_4) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
                THEN 1
                ELSE 0 
            END AS es_tala
        FROM clips
        WHERE status != 'ruido_extremo' 
          AND localidad IN {localidades_str}
          AND strftime('%Y', fecha) != '2023' -- Exclusión de 2023
    )
    SELECT 
        ciclo_hidrologico,
        anio,
        localidad,
        hora_del_dia,
        ROUND(CAST(SUM(es_tala) AS FLOAT) * 100 / COUNT(*), 4) AS pct_alf
    FROM clips_base
    GROUP BY 1, 2, 3, 4;
    """
    df_fta_raw = pd.read_sql_query(query_fta, conn)
    conn.close()
    
    if not df_fta_raw.empty:
        df_fta = df_fta_raw.groupby(['ciclo_hidrologico', 'localidad', 'hora_del_dia'])['pct_alf'].mean().reset_index()
        vmax_fta = max(df_fta['pct_alf'].max(), 1.0)

        fig, axes = plt.subplots(2, 1, figsize=(11, 10))
        
        df_rainy_fta = df_fta[df_fta['ciclo_hidrologico'] == 'Rainy Season']
        pivot_rainy_fta = df_rainy_fta.pivot(index='localidad', columns='hora_del_dia', values='pct_alf').fillna(0)
        pivot_rainy_fta = pivot_rainy_fta.reindex(index=localidades, columns=horas_del_dia, fill_value=0)
        pivot_rainy_fta.to_csv(os.path.join(output_dir, 'matrix_alf_rainy.csv'), encoding='utf-8-sig') # <-- NUEVO
        
        sns.heatmap(pivot_rainy_fta, annot=False, cmap="YlOrRd", ax=axes[0], 
                    cbar_kws={'label': '% ALF'}, vmin=0.0, vmax=vmax_fta)
        axes[0].set_title("GLOBAL (All Years) - Rainy Season", fontsize=12, fontweight='bold')
        axes[0].set_xlabel("Hour")
        axes[0].set_ylabel("Community")

        df_dry_fta = df_fta[df_fta['ciclo_hidrologico'] == 'Dry Season']
        pivot_dry_fta = df_dry_fta.pivot(index='localidad', columns='hora_del_dia', values='pct_alf').fillna(0)
        pivot_dry_fta = pivot_dry_fta.reindex(index=localidades, columns=horas_del_dia, fill_value=0)
        pivot_dry_fta.to_csv(os.path.join(output_dir, 'matrix_alf_dry.csv'), encoding='utf-8-sig') # <-- NUEVO
        
        sns.heatmap(pivot_dry_fta, annot=False, cmap="YlOrRd", ax=axes[1], 
                    cbar_kws={'label': '% ALF'}, vmin=0.0, vmax=vmax_fta)
        axes[1].set_title("GLOBAL (All Years) - Dry Season", fontsize=12, fontweight='bold')
        axes[1].set_xlabel("Hour")
        axes[1].set_ylabel("Community")

        fig.suptitle("Acoustic Logging Frequency (ALF) Heatmap\n(Excluyendo Año 2023)", fontsize=16, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        output_fta_path = os.path.join(output_dir, 'grid_alf_global_24h.png')
        plt.savefig(output_fta_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Exportado exitosamente: {output_fta_path}")

    print(f"\n¡Proceso finalizado! Los archivos corregidos se guardaron en: '{output_dir}'.")

if __name__ == "__main__":
    DATABASE_PATH = r'E:\audiomoth_2_discos - copia (2).sqlite'
    generar_heatmaps_apilados_globales(DATABASE_PATH)