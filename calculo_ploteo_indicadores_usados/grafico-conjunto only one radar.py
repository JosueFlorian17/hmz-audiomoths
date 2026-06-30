import os
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

COLORS_STACK = ["#d44a23", "#b0c39a", "#14595d", "#8ecbb8", "#FFD700"] 

RADAR_CATS = [
    'AAI', 'IAI', 'BAI',
    'AIO', 'ABO',
    'HPI', 'BPI', 'IPI'
]

COMMUNITIES = ["QUISTOCOCHA", "VARILLAL", "PAUJIL", "SAN LUCAS", "12 DE ABRIL"]
SPIDER_COLORS = ["#14595d", "#b0c39a", "#eab876", "#8ecbb8", "#d44a23"]

ACRONYM_TEXT = (
    "AAI: Anthropogenic Activity Index | IAI: Insect Activity Index | BAI: Bird Activity Index\n"
    "AIO: Anthro-Insect Overlap | ABO: Anthro-Bird Overlap\n"
    "HPI: Human Penetration Index | BPI: Bird Penetration Index | IPI: Insect Penetration Index"
)

CAT_LABELS = {
    "Anthropogenic": "Anthropogenic (AAI)",
    "Amphibian": "Amphibian (AmAI)",
    "Insect": "Insect (IAI)",
    "Bird": "Bird (BAI)"
}

def generate_dashboard_from_csv(map_png_path, stack_csv_path, radar_csv_path, output_path='dashboard_combined_output.png'):
    if not os.path.exists(stack_csv_path) or not os.path.exists(radar_csv_path):
        raise FileNotFoundError("Asegúrate de que ambos archivos CSV existan en las rutas proporcionadas.")
        
    df_stack = pd.read_csv(stack_csv_path)
    df_radar = pd.read_csv(radar_csv_path)
    
    df_stack['localidad'] = df_stack['localidad'].astype(str).str.upper()
    df_radar['comunidad'] = df_radar['comunidad'].astype(str).str.upper()
    
    img = cv2.imread(map_png_path)
    if img is not None:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        raise FileNotFoundError(f"No se pudo encontrar o leer el mapa en: {map_png_path}") 
    fig = plt.figure(figsize=(24, 20), facecolor='white')
    gs = gridspec.GridSpec(6, 3, width_ratios=[1.1, 1.3, 1.0], wspace=0.35, hspace=0.60)
    

    ax_map = fig.add_subplot(gs[:, 0])
    ax_map.imshow(img_rgb) 
    ax_map.axis('off')
    ax_map.set_title("Geographical Communities Location", fontsize=14, fontweight='bold', pad=15)
    

    ax_radar = fig.add_subplot(gs[:, 2], polar=True)
    ax_radar.set_theta_offset(np.pi / 2)
    ax_radar.set_theta_direction(-1)
    
    angles = np.linspace(0, 2 * np.pi, len(RADAR_CATS), endpoint=False).tolist()
    angles_loop = angles + [angles[0]]


    for i, row_name in enumerate(["GLOBAL"] + COMMUNITIES):
        if row_name == "GLOBAL":
            r_vals = df_radar[['AAI', 'IAI', 'BAI', 'AIO', 'ABO', 'HPI', 'BPI', 'IPI']].mean()
            current_color = 'black'
            linewidth = 3.0
            alpha = 0.1
            label = "GLOBAL AVG"
        else:
            df_match = df_radar[df_radar['comunidad'] == row_name]
            r_vals = df_match.iloc[0] if not df_match.empty else pd.Series(0, index=RADAR_CATS)
            current_color = SPIDER_COLORS[i-1]
            linewidth = 2.0
            alpha = 0.05
            label = row_name
            
        values = [r_vals[cat] for cat in RADAR_CATS]
        values_loop = values + [values[0]]
        
        ax_radar.plot(angles_loop, values_loop, color=current_color, linewidth=linewidth, label=label) 
        ax_radar.fill(angles_loop, values_loop, color=current_color, alpha=alpha) 

    ax_radar.set_thetagrids(np.degrees(angles), RADAR_CATS, fontsize=10, fontweight='bold')
    ax_radar.tick_params(axis='x', pad=25)
    ax_radar.set_rlim(0, 50)
    ax_radar.set_rgrids([10, 20, 30, 40, 50], labels=['10%', '20%', '30%', '40%', '50%'], color='#BBBBBB', fontsize=8)
    ax_radar.grid(True, color='#E0E0E0', linestyle='-', linewidth=0.7)
    ax_radar.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=10, frameon=False) 
    ax_radar.text(0.5, -0.35, ACRONYM_TEXT, transform=ax_radar.transAxes, ha='center', va='center', fontsize=9, color='#444444', style='italic')
    ax_radar.set_title("Multi-Community Acoustic Signature", fontsize=14, fontweight='bold', pad=30)
    pos_radar = gs[:, 2].get_position(fig) 
    ax_radar.set_position([pos_radar.x0, pos_radar.y0 + 0.15, pos_radar.width, pos_radar.height * 0.75]) 

    rows_structure = ["GLOBAL"] + COMMUNITIES
    

    for idx, row_name in enumerate(rows_structure):
        

        ax_stack = fig.add_subplot(gs[idx, 1])
        
        if row_name == "GLOBAL":
            data_curr = df_stack
        else:
            data_curr = df_stack[df_stack['localidad'] == row_name]
            
        f_grouped = data_curr.groupby(['hora_dia', 'primary_category'])['promedio_clips_hora'].mean().reset_index()
        pivot_df = f_grouped.pivot(index='hora_dia', columns='primary_category', values='promedio_clips_hora').fillna(0)
        

        cats_order = ["Anthropogenic", "Mammal", "Bird", "Insect", "Amphibian"]
        
        cols_present = [c for c in cats_order if c in pivot_df.columns]
        pivot_df = pivot_df[cols_present]
        
        row_sums = pivot_df.sum(axis=1)
        pivot_pct = pivot_df.div(np.where(row_sums == 0, 1, row_sums), axis=0) * 100.0
        
        ax_stack.stackplot(pivot_pct.index, pivot_pct.T, labels=pivot_pct.columns, colors=COLORS_STACK, alpha=0.9)
        ax_stack.set_xlim(0, 23)
        ax_stack.set_ylim(0, 100)
        ax_stack.set_xticks([0, 6, 12, 18, 23])
        ax_stack.set_ylabel("Acoustic Dominance (%)", fontsize=9, fontweight='bold')
        ax_stack.tick_params(axis='both', labelsize=9)
        ax_stack.set_title(row_name, color='black', fontweight='bold', fontsize=10, loc='left')
        
        if idx == 0:

            handles, labels = ax_stack.get_legend_handles_labels()

            new_handles = [handles[i] for i, label in enumerate(labels) if label in CAT_LABELS]
            new_labels = [CAT_LABELS[label] for label in labels if label in CAT_LABELS]
            
            leg = ax_stack.legend(new_handles, new_labels, loc='lower center', bbox_to_anchor=(0.5, 1.22), ncol=4, fontsize=11, frameon=False)
            plt.setp(leg.get_texts(), fontweight='bold')


        if idx == len(rows_structure) - 1:
            ax_stack.set_xlabel("Day Hours (24h)", fontsize=10, fontweight='bold')


    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Lienzo unificado exportado con éxito en: {output_path}")

if __name__ == "__main__":
    generate_dashboard_from_csv(
        map_png_path='Screenshot_1.png',
        stack_csv_path='data_24h_combined_seasons.csv',
        radar_csv_path='radar_indicators_cache.csv',
        output_path='final_acoustic_map_dashboard.png'
    )