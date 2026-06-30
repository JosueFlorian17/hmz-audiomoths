-- Indicadores finales
-- DNR
    
SELECT 
    primary_category,
    COUNT(CASE WHEN period = 'day' THEN 1 END) AS n_clips_dia,
    COUNT(CASE WHEN period = 'night' THEN 1 END) AS n_clips_noche,
    ROUND(
        CAST(COUNT(CASE WHEN period = 'day' THEN 1 END) AS FLOAT) * 100 / 
        NULLIF(COUNT(*), 0), 2
    ) AS pct_dia,
    ROUND(
        CAST(COUNT(CASE WHEN period = 'night' THEN 1 END) AS FLOAT) * 100 / 
        NULLIF(COUNT(*), 0), 2
    ) AS pct_noche
FROM 
    clips
GROUP BY 
    primary_category
ORDER BY 
    pct_dia DESC;
    
    
-- IAM

    WITH bloques_base AS (
    SELECT 
        localidad,
        campaña,
        primary_category,
        prob,
        clip_dbfs,
        CASE 
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 0 AND 2 THEN '00-03 Madrugada'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 3 AND 5 THEN '03-06 Alba'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 6 AND 8 THEN '06-09 Mañana (Pico 1)'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 9 AND 11 THEN '09-12 Mediodía'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 12 AND 14 THEN '12-15 Tarde Temprana'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 15 AND 17 THEN '15-18 Tarde (Pico 2)'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 18 AND 20 THEN '18-21 Ocaso'
            ELSE '21-00 Noche'
        END AS ventana_temporal
    FROM 
        clips
    WHERE 
        status != 'ruido_extremo'
        AND localidad IN ("12 DE ABRIL", "PAUJIL", "QUISTOCOCHA", "SAN LUCAS", "VARILLAL")
)
SELECT 
    localidad,
    campaña,
    ventana_temporal,
    primary_category,
    COUNT(*) AS n_clips_categoria,
    ROUND(
        CAST(COUNT(*) AS FLOAT) * 100 / 
        SUM(COUNT(*)) OVER (PARTITION BY localidad, campaña, ventana_temporal), 
        4
    ) AS pct_indice_actividad
FROM 
    bloques_base
GROUP BY 
    localidad, 
    campaña, 
    ventana_temporal,
    primary_category
ORDER BY 
    localidad, 
    campaña, 
    ventana_temporal, 
    pct_indice_actividad DESC;
    
    
WITH bloques_base AS (
    SELECT 
        localidad,
        primary_category,
        prob,
        clip_dbfs,
        CASE 
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 0 AND 2 THEN '00-03 Madrugada'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 3 AND 5 THEN '03-06 Alba'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 6 AND 8 THEN '06-09 Mañana (Pico 1)'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 9 AND 11 THEN '09-12 Mediodía'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 12 AND 14 THEN '12-15 Tarde Temprana'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 15 AND 17 THEN '15-18 Tarde (Pico 2)'
            WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 18 AND 20 THEN '18-21 Ocaso'
            ELSE '21-00 Noche'
        END AS ventana_temporal
    FROM 
        clips
    WHERE 
        status != 'ruido_extremo'
        AND localidad IN ("12 DE ABRIL", "PAUJIL", "QUISTOCOCHA", "SAN LUCAS", "VARILLAL")
        AND prob > 0.5 -- Umbral de confianza para asegurar calidad en las categorías
)
SELECT 
    localidad,
    ventana_temporal,
    primary_category,
    COUNT(*) AS n_clips_total_historico,
    ROUND(
        CAST(COUNT(*) AS FLOAT) * 100 / 
        SUM(COUNT(*)) OVER (PARTITION BY localidad, ventana_temporal), 
        4
    ) AS pct_indice_actividad
FROM 
    bloques_base
GROUP BY 
    localidad, 
    ventana_temporal,
    primary_category
ORDER BY 
    localidad, 
    ventana_temporal, 
    pct_indice_actividad DESC;


WITH detecciones_tala AS (
    SELECT 
        localidad,
        campaña,
        fecha,
        CAST(strftime('%H', hora) AS INT) AS hora_num,
        CASE 
            WHEN LOWER(yamnet_label_1) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
              OR LOWER(yamnet_label_2) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
              OR LOWER(yamnet_label_3) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
              OR LOWER(yamnet_label_4) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
            THEN 1 ELSE 0 
        END AS es_tala
    FROM 
        clips
    WHERE 
        status != 'ruido_extremo'
        AND localidad IN ("12 DE ABRIL", "PAUJIL", "QUISTOCOCHA", "SAN LUCAS", "VARILLAL")
)
SELECT 
    localidad,
    hora_num AS hora_del_dia,
    COUNT(*) AS total_clips,
    SUM(es_tala) AS clips_con_tala,
    ROUND(CAST(SUM(es_tala) AS FLOAT) * 100 / COUNT(*), 4) AS pct_fta,
    ROUND(SQRT(AVG(CAST(es_tala AS FLOAT)) * (1.0 - AVG(CAST(es_tala AS FLOAT)))) * 100, 4) AS fta_sd
FROM 
    detecciones_tala
GROUP BY 
    localidad, 
    hora_num
ORDER BY 
    localidad, 
    hora_num;
    
-- Indice de Penetración multiespecie (IPH)
WITH periodos_criticos AS (
    SELECT 
        fecha,
        localidad AS comunidad,
        primary_category AS categoria,
        CASE 
            WHEN hora BETWEEN '05:00:00' AND '07:00:00' THEN 'Amanecer Crítico'
            WHEN hora BETWEEN '17:00:00' AND '19:00:00' THEN 'Anochecer Crítico'
            ELSE 'Otro'
        END AS periodo_analisis
    FROM clips 
    WHERE periodo_analisis != 'Otro'
),
detecciones_diarias AS (
    SELECT 
        fecha,
        periodo_analisis,
        comunidad,
        categoria,
        COUNT(*) AS detecciones_dia
    FROM periodos_criticos
    GROUP BY 1, 2, 3, 4
),
esfuerzo_diario AS (
    SELECT 
        fecha,
        periodo_analisis,
        comunidad,
        COUNT(*) AS total_clips_dia
    FROM periodos_criticos
    GROUP BY 1, 2, 3
),
porcentajes_diarios AS (
    SELECT 
        d.fecha,
        d.periodo_analisis,
        d.comunidad,
        d.categoria,
        (d.detecciones_dia * 100.0) / e.total_clips_dia AS pct_diario
    FROM detecciones_diarias d
    JOIN esfuerzo_diario e 
      ON d.fecha = e.fecha 
      AND d.comunidad = e.comunidad 
      AND d.periodo_analisis = e.periodo_analisis
)
SELECT 
    periodo_analisis,
    categoria,
    comunidad,
    ROUND(AVG(pct_diario), 2) AS porcentaje_promedio,
    ROUND(SQRT((SUM(pct_diario * pct_diario) - COUNT(pct_diario) * AVG(pct_diario) * AVG(pct_diario)) / (COUNT(pct_diario) - 1.0)), 2) AS porcentaje_sd,
    ROUND(MIN(pct_diario), 2) AS porcentaje_min,
    ROUND(MAX(pct_diario), 2) AS porcentaje_max,
    COUNT(DISTINCT fecha) AS dias_muestreados
FROM porcentajes_diarios
GROUP BY 1, 2, 3
ORDER BY 
    CASE WHEN periodo_analisis = 'Amanecer Crítico' THEN 1 ELSE 2 END,
    categoria, 
    comunidad;
    
-- RELEVO DIARIO DE ESPECIES
WITH dias_muestreados AS (
    SELECT 
        localidad, 
        COUNT(DISTINCT fecha) as total_dias
    FROM clips
    GROUP BY localidad
)
SELECT 
    c.localidad,
    CAST(strftime('%H', c.hora) AS INT) AS hora_dia,
    c.primary_category,
    ROUND(CAST(COUNT(*) AS FLOAT) / d.total_dias, 2) AS promedio_clips_hora,

    ROUND(
        CAST(COUNT(*) AS FLOAT) * 100 / SUM(COUNT(*)) OVER (PARTITION BY c.localidad, strftime('%H', c.hora)), 
        2
    ) AS pct_composicion_hora
FROM 
    clips c
JOIN 
    dias_muestreados d ON c.localidad = d.localidad
WHERE 
    c.status != 'ruido_extremo'
    AND c.primary_category NOT IN ('Silencio', 'Ruido ambiental')
    AND c.localidad = '12 DE ABRIL' 
GROUP BY 
    1, 2, 3
ORDER BY 
    hora_dia ASC, 
    promedio_clips_hora DESC;
    

    
    
--RBA
SELECT 
    localidad,
    SUM(CASE WHEN primary_category = 'Antropogénico' THEN 1 ELSE 0 END) AS n_humano,
    
    -- 1. Ratio Humano / Ave (RHA)
    ROUND(CAST(SUM(CASE WHEN primary_category = 'Ave' THEN 1 ELSE 0 END) AS FLOAT) / 
          NULLIF(SUM(CASE WHEN primary_category = 'Antropogénico' THEN 1 ELSE 0 END), 0), 4) AS RHA,
    
    -- 2. Ratio Humano / Insecto (RHI)
    ROUND(CAST(SUM(CASE WHEN primary_category = 'Insecto' THEN 1 ELSE 0 END) AS FLOAT) / 
          NULLIF(SUM(CASE WHEN primary_category = 'Antropogénico' THEN 1 ELSE 0 END), 0), 4) AS RHI,
          
    -- 3. Ratio Humano / Anfibio (RHAn)
    ROUND(CAST(SUM(CASE WHEN primary_category = 'Anfibio' THEN 1 ELSE 0 END) AS FLOAT) / 
          NULLIF(SUM(CASE WHEN primary_category = 'Antropogénico' THEN 1 ELSE 0 END), 0), 4) AS RHAn,

    -- 4. Ratio Humano / Tala (RHT) 
    -- Comparamos ruido humano general vs maquinaria específica de tala
    ROUND(CAST(SUM(CASE WHEN 
            LOWER(yamnet_label_1) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
            OR LOWER(yamnet_label_2) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
            THEN 1 ELSE 0 END) AS FLOAT) / 
          NULLIF(SUM(CASE WHEN primary_category = 'Antropogénico' THEN 1 ELSE 0 END), 0), 4) AS RHT

FROM 
    clips
WHERE 
    status != 'ruido_extremo' 
    AND primary_category NOT IN ('Ruido ambiental', 'Silencio')
    AND localidad IN ("12 DE ABRIL", "PAUJIL", "QUISTOCOCHA", "SAN LUCAS", "VARILLAL")
GROUP BY 
    localidad;
    
    



-- tablas descriptivas
WITH conteo_etiquetas AS (
    SELECT 
        localidad,
        primary_category,
        yamnet_label_1,
        COUNT(*) as freq,
        ROW_NUMBER() OVER (PARTITION BY localidad, primary_category ORDER BY COUNT(*) DESC) as ranking
    FROM clips
    WHERE UPPER(localidad) IN ('12 DE ABRIL', 'PAUJIL', 'QUISTOCOCHA', 'SAN LUCAS', 'VARILLAL')
    GROUP BY localidad, primary_category, yamnet_label_1
)
SELECT 
    c.localidad,
    COUNT(DISTINCT c.filename || c.clip_idx) AS total_clips,
    ROUND(CAST(COUNT(DISTINCT c.filename || c.clip_idx) * 5 AS FLOAT) / 3600, 2) AS horas_totales,
    
    GROUP_CONCAT(DISTINCT CASE WHEN ce.primary_category = 'Ave' AND ce.ranking <= 5 THEN ce.yamnet_label_1 END) AS top_5_sonidos_aves,
    GROUP_CONCAT(DISTINCT CASE WHEN ce.primary_category = 'Insecto' AND ce.ranking <= 5 THEN ce.yamnet_label_1 END) AS top_5_sonidos_insectos,
    GROUP_CONCAT(DISTINCT CASE WHEN ce.primary_category = 'Antropogénico' AND ce.ranking <= 5 THEN ce.yamnet_label_1 END) AS top_5_sonidos_humanos,
    GROUP_CONCAT(DISTINCT CASE WHEN ce.primary_category = 'Anfibio' AND ce.ranking <= 5 THEN ce.yamnet_label_1 END) AS top_5_sonidos_anfibios,

    GROUP_CONCAT(DISTINCT CASE WHEN c.whitelist = 'Sí' THEN c.species_common END) AS catalogo_aves_detectadas

FROM clips c
LEFT JOIN conteo_etiquetas ce ON c.localidad = ce.localidad 
WHERE UPPER(c.localidad) IN ('12 DE ABRIL', 'PAUJIL', 'QUISTOCOCHA', 'SAN LUCAS', 'VARILLAL')
GROUP BY c.localidad
ORDER BY total_clips DESC;



-- de indicadores
WITH clips_filtrados AS (
    SELECT 
        fecha,
        UPPER(localidad) AS comunidad,
        UniqueAudioKey,
        LOWER(primary_category) AS categoria,
        prob,
        yamnet_label_1,
        yamnet_label_2,
        CASE 
            WHEN hora BETWEEN '05:00:00' AND '07:00:00' THEN 'Critico'
            WHEN hora BETWEEN '17:00:00' AND '19:00:00' THEN 'Critico'
            ELSE 'Otro'
        END AS tipo_periodo
    FROM clips
    WHERE UPPER(localidad) IN ('SAN LUCAS', '12 DE ABRIL', 'PAUJIL', 'VARILLAL', 'QUISTOCOCHA')
),

ip_diario AS (
    SELECT 
        fecha,
        comunidad,
        (SUM(CASE WHEN categoria = 'antropogénico' THEN 1 ELSE 0 END) * 100.0) / COUNT(*) AS pct_h_dia,
        (SUM(CASE WHEN categoria = 'insecto' THEN 1 ELSE 0 END) * 100.0) / COUNT(*) AS pct_i_dia,
        (SUM(CASE WHEN categoria = 'ave' THEN 1 ELSE 0 END) * 100.0) / COUNT(*) AS pct_a_dia,
        (SUM(CASE WHEN categoria = 'anfibio' THEN 1 ELSE 0 END) * 100.0) / COUNT(*) AS pct_an_dia
    FROM clips_filtrados
    WHERE tipo_periodo = 'Critico'
    GROUP BY 1, 2
),
ip_final AS (
    SELECT 
        comunidad,
        AVG(pct_h_dia) AS iph_p, MIN(pct_h_dia) AS iph_min, MAX(pct_h_dia) AS iph_max,
        SQRT((SUM(pct_h_dia * pct_h_dia) - COUNT(pct_h_dia) * AVG(pct_h_dia) * AVG(pct_h_dia)) / (COUNT(pct_h_dia) - 1)) AS iph_sd,
        AVG(pct_i_dia) AS ipi_p, MIN(pct_i_dia) AS ipi_min, MAX(pct_i_dia) AS ipi_max,
        SQRT((SUM(pct_i_dia * pct_i_dia) - COUNT(pct_i_dia) * AVG(pct_i_dia) * AVG(pct_i_dia)) / (COUNT(pct_i_dia) - 1)) AS ipi_sd,
        AVG(pct_a_dia) AS ipa_p, MIN(pct_a_dia) AS ipa_min, MAX(pct_a_dia) AS ipa_max,
        SQRT((SUM(pct_a_dia * pct_a_dia) - COUNT(pct_a_dia) * AVG(pct_a_dia) * AVG(pct_a_dia)) / (COUNT(pct_a_dia) - 1)) AS ipa_sd,
        AVG(pct_an_dia) AS ipan_p, MIN(pct_an_dia) AS ipan_min, MAX(pct_an_dia) AS ipan_max,
        SQRT((SUM(pct_an_dia * pct_an_dia) - COUNT(pct_an_dia) * AVG(pct_an_dia) * AVG(pct_an_dia)) / (COUNT(pct_an_dia) - 1)) AS ipan_sd
    FROM ip_diario
    GROUP BY 1
),

flags_por_audio AS (
    SELECT 
        comunidad,
        UniqueAudioKey,
        MAX(CASE WHEN categoria = 'antropogénico' THEN 1 ELSE 0 END) AS tiene_h,
        MAX(CASE WHEN categoria = 'insecto' THEN 1 ELSE 0 END) AS tiene_i,
        MAX(CASE WHEN categoria = 'ave' THEN 1 ELSE 0 END) AS tiene_a,
        MAX(CASE WHEN categoria = 'anfibio' THEN 1 ELSE 0 END) AS tiene_an,
        MAX(CASE WHEN categoria = 'mamifero' THEN 1 ELSE 0 END) AS tiene_m
    FROM clips_filtrados
    GROUP BY comunidad, UniqueAudioKey
),
isah_final AS (
    SELECT 
        comunidad,
        COUNT(*) AS n_audios,
        CAST(SUM(CASE WHEN tiene_h = 1 AND tiene_i = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS isah_i_p,
        CAST(SUM(CASE WHEN tiene_h = 1 AND tiene_a = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS isah_a_p,
        CAST(SUM(CASE WHEN tiene_h = 1 AND tiene_an = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS isah_an_p,
        CAST(SUM(CASE WHEN tiene_h = 1 AND tiene_m = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS isah_m_p
    FROM flags_por_audio
    GROUP BY comunidad
),

otros_indicadores_base AS (
    SELECT 
        comunidad,
        COUNT(*) AS n_total,
        SUM(CASE WHEN categoria = 'antropogénico' THEN 1 ELSE 0 END) AS n_hum,
        SUM(CASE WHEN categoria = 'insecto' THEN 1 ELSE 0 END) AS n_ins,
        SUM(CASE WHEN categoria = 'ave' THEN 1 ELSE 0 END) AS n_ave,
        SUM(CASE WHEN categoria = 'anfibio' THEN 1 ELSE 0 END) AS n_anf,
        SUM(CASE WHEN categoria = 'mamifero' THEN 1 ELSE 0 END) AS n_mam,
        SUM(CASE WHEN LOWER(yamnet_label_1) IN ('tools', 'engine', 'chainsaw') THEN 1 ELSE 0 END) AS n_tala,
        SUM(CASE WHEN categoria IN ('insecto', 'ave', 'anfibio', 'mamifero') THEN 1 ELSE 0 END) AS n_bio
    FROM clips_filtrados
    GROUP BY 1
)

-- --- ENSAMBLAJE FINAL ---
SELECT 
    o.comunidad,
    ROUND(CAST(n_hum AS FLOAT)/n_total * 100, 2) AS IAA_pct,
    ROUND(SQRT((CAST(n_hum AS FLOAT)/n_total) * (1 - CAST(n_hum AS FLOAT)/n_total)) * 100, 2) AS iaa_sd,
    ROUND((CAST(n_hum AS FLOAT)/n_total - 1.96 * SQRT((CAST(n_hum AS FLOAT)/n_total*(1-CAST(n_hum AS FLOAT)/n_total))/n_total)) * 100, 2) AS iaa_min,
    ROUND((CAST(n_hum AS FLOAT)/n_total + 1.96 * SQRT((CAST(n_hum AS FLOAT)/n_total*(1-CAST(n_hum AS FLOAT)/n_total))/n_total)) * 100, 2) AS iaa_max,
    
    ROUND(CAST(n_ins AS FLOAT)/n_total * 100, 2) AS IAI_pct,
    ROUND(SQRT((CAST(n_ins AS FLOAT)/n_total) * (1 - CAST(n_ins AS FLOAT)/n_total)) * 100, 2) AS iai_sd,
    ROUND((CAST(n_ins AS FLOAT)/n_total - 1.96 * SQRT((CAST(n_ins AS FLOAT)/n_total*(1-CAST(n_ins AS FLOAT)/n_total))/n_total)) * 100, 2) AS iai_min,
    ROUND((CAST(n_ins AS FLOAT)/n_total + 1.96 * SQRT((CAST(n_ins AS FLOAT)/n_total*(1-CAST(n_ins AS FLOAT)/n_total))/n_total)) * 100, 2) AS iai_max,

    ROUND(CAST(n_ave AS FLOAT)/n_total * 100, 2) AS IAAv_pct,
    ROUND(SQRT((CAST(n_ave AS FLOAT)/n_total) * (1 - CAST(n_ave AS FLOAT)/n_total)) * 100, 2) AS iaav_sd,
    ROUND((CAST(n_ave AS FLOAT)/n_total - 1.96 * SQRT((CAST(n_ave AS FLOAT)/n_total*(1-CAST(n_ave AS FLOAT)/n_total))/n_total)) * 100, 2) AS iaav_min,
    ROUND((CAST(n_ave AS FLOAT)/n_total + 1.96 * SQRT((CAST(n_ave AS FLOAT)/n_total*(1-CAST(n_ave AS FLOAT)/n_total))/n_total)) * 100, 2) AS iaav_max,

    ROUND(CAST(n_anf AS FLOAT)/n_total * 100, 2) AS IAAn_pct,
    ROUND(SQRT((CAST(n_anf AS FLOAT)/n_total) * (1 - CAST(n_anf AS FLOAT)/n_total)) * 100, 2) AS iaan_sd,
    ROUND((CAST(n_anf AS FLOAT)/n_total - 1.96 * SQRT((CAST(n_anf AS FLOAT)/n_total*(1-CAST(n_anf AS FLOAT)/n_total))/n_total)) * 100, 2) AS iaan_min,
    ROUND((CAST(n_anf AS FLOAT)/n_total + 1.96 * SQRT((CAST(n_anf AS FLOAT)/n_total*(1-CAST(n_anf AS FLOAT)/n_total))/n_total)) * 100, 2) AS iaan_max,

    ROUND(CAST(n_mam AS FLOAT)/n_total * 100, 2) AS IAMa_pct,
    ROUND(SQRT((CAST(n_mam AS FLOAT)/n_total) * (1 - CAST(n_mam AS FLOAT)/n_total)) * 100, 2) AS iama_sd,
    ROUND((CAST(n_mam AS FLOAT)/n_total - 1.96 * SQRT((CAST(n_mam AS FLOAT)/n_total*(1-CAST(n_mam AS FLOAT)/n_total))/n_total)) * 100, 2) AS iama_min,
    ROUND((CAST(n_mam AS FLOAT)/n_total + 1.96 * SQRT((CAST(n_mam AS FLOAT)/n_total*(1-CAST(n_mam AS FLOAT)/n_total))/n_total)) * 100, 2) AS iama_max,

    ROUND(CAST(n_tala AS FLOAT)/n_total * 100, 2) AS FTA_pct,
    ROUND(SQRT((CAST(n_tala AS FLOAT)/n_total) * (1 - CAST(n_tala AS FLOAT)/n_total)) * 100, 2) AS fta_sd,
    ROUND((CAST(n_tala AS FLOAT)/n_total - 1.96 * SQRT((CAST(n_tala AS FLOAT)/n_total*(1-CAST(n_tala AS FLOAT)/n_total))/n_total)) * 100, 2) AS fta_min,
    ROUND((CAST(n_tala AS FLOAT)/n_total + 1.96 * SQRT((CAST(n_tala AS FLOAT)/n_total*(1-CAST(n_tala AS FLOAT)/n_total))/n_total)) * 100, 2) AS fta_max,

    ROUND(isah_i_p * 100, 2) AS ISAH_I_pct,
    ROUND(SQRT(isah_i_p * (1 - isah_i_p)) * 100, 2) AS isahi_sd,
    ROUND((isah_i_p - 1.96 * SQRT((isah_i_p * (1 - isah_i_p)) / n_audios)) * 100, 2) AS isahi_min,
    ROUND((isah_i_p + 1.96 * SQRT((isah_i_p * (1 - isah_i_p)) / n_audios)) * 100, 2) AS isahi_max,
    
    ROUND(isah_a_p * 100, 2) AS ISAH_A_pct,
    ROUND(SQRT(isah_a_p * (1 - isah_a_p)) * 100, 2) AS isaha_sd,
    ROUND((isah_a_p - 1.96 * SQRT((isah_a_p * (1 - isah_a_p)) / n_audios)) * 100, 2) AS isaha_min,
    ROUND((isah_a_p + 1.96 * SQRT((isah_a_p * (1 - isah_a_p)) / n_audios)) * 100, 2) AS isaha_max,

    ROUND(isah_an_p * 100, 2) AS ISAH_An_pct,
    ROUND(SQRT(isah_an_p * (1 - isah_an_p)) * 100, 2) AS isahan_sd,
    ROUND((isah_an_p - 1.96 * SQRT((isah_an_p * (1 - isah_an_p)) / n_audios)) * 100, 2) AS isahan_min,
    ROUND((isah_an_p + 1.96 * SQRT((isah_an_p * (1 - isah_an_p)) / n_audios)) * 100, 2) AS isahan_max,

    ROUND(isah_m_p * 100, 2) AS ISAH_M_pct,
    ROUND(SQRT(isah_m_p * (1 - isah_m_p)) * 100, 2) AS isahm_sd,

    ROUND(iph_p, 2) AS IPH, ROUND(iph_sd, 2) AS iph_sd, ROUND(iph_min, 2) AS iph_min, ROUND(iph_max, 2) AS iph_max,
    ROUND(ipi_p, 2) AS IPI, ROUND(ipi_sd, 2) AS ipi_sd, ROUND(ipi_min, 2) AS ipi_min, ROUND(ipi_max, 2) AS ipi_max,
    ROUND(ipa_p, 2) AS IPA, ROUND(ipa_sd, 2) AS ipa_sd, ROUND(ipa_min, 2) AS ipa_min, ROUND(ipa_max, 2) AS ipa_max,
    ROUND(ipan_p, 2) AS IPAn, ROUND(ipan_sd, 2) AS ipan_sd, ROUND(ipan_min, 2) AS ipan_min, ROUND(ipan_max, 2) AS ipan_max,

    ROUND(CAST(n_bio AS FLOAT)/NULLIF(n_hum, 0), 3) AS RBA,
    ROUND(CAST(n_ins AS FLOAT)/NULLIF(n_hum, 0), 3) AS RMA_I,
    ROUND(CAST(n_ave AS FLOAT)/NULLIF(n_hum, 0), 3) AS RAvA,
    ROUND(CAST(n_anf AS FLOAT)/NULLIF(n_hum, 0), 3) AS RAnA,
    ROUND(CAST(n_mam AS FLOAT)/NULLIF(n_hum, 0), 3) AS RMaA
    
FROM otros_indicadores_base o
LEFT JOIN ip_final i ON o.comunidad = i.comunidad
LEFT JOIN isah_final s ON o.comunidad = s.comunidad
ORDER BY o.comunidad;





-- de Burbujas
WITH flags_por_clip AS (
    SELECT 
        UPPER(localidad) AS loc_clean,
        UniqueAudioKey,
        primary_category,
        yamnet_label_1,
        yamnet_label_2,
        clip_dbfs,
        CAST(strftime('%Y', fecha) AS INT) AS anio,
        CAST(strftime('%H', hora) AS INT) AS hora_num,
        CASE WHEN LOWER(primary_category) = 'antropogénico' THEN 1 ELSE 0 END AS es_humano,
        CASE WHEN LOWER(primary_category) = 'insecto' THEN 1 ELSE 0 END AS es_insecto,
        CASE WHEN LOWER(yamnet_label_1) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
               OR LOWER(yamnet_label_2) IN ('chainsaw', 'saw', 'power tool', 'circular saw', 'mechanical fan', 'engine', 'idling', 'mechanisms', 'electric toothbrush', 'motor', 'light engine (high frequency)', 'electric shaver, electric razor', 'blender')
        THEN 1 ELSE 0 END AS es_tala,
        CASE WHEN (primary_category = 'Insecto' OR yamnet_label_1 = 'Insect') AND clip_dbfs > -40 THEN 1 ELSE 0 END AS es_mosquito,
        CASE WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 4 AND 6 THEN 'Amanecer'
             WHEN CAST(strftime('%H', hora) AS INT) BETWEEN 18 AND 20 THEN 'Anochecer'
             ELSE 'Otro' END AS fase_critica
    FROM clips
    WHERE status != 'ruido_extremo' 
      AND UPPER(localidad) IN ('12 DE ABRIL', 'PAUJIL', 'QUISTOCOCHA', 'SAN LUCAS', 'VARILLAL')
      AND CAST(strftime('%Y', fecha) AS INT) BETWEEN 2023 AND 2025
),
superposicion_por_audio AS (
    SELECT 
        loc_clean,
        anio,
        UniqueAudioKey,
        CASE WHEN MAX(es_humano) = 1 AND MAX(es_insecto) = 1 THEN 1 ELSE 0 END AS coincidencia_hv
    FROM flags_por_clip
    GROUP BY loc_clean, anio, UniqueAudioKey
),
stats_probabilisticas AS (
    SELECT 
        loc_clean,
        anio,
        CAST(SUM(coincidencia_hv) AS FLOAT) / COUNT(*) AS isahi_p
    FROM superposicion_por_audio
    GROUP BY loc_clean, anio
)
SELECT 
    f.anio AS Año,
    f.loc_clean AS Localidad,
    COUNT(*) AS Total_Clips,
    
    ROUND(SUM(f.es_mosquito) * 100.0 / COUNT(*), 2) AS IAM_pct,
    
    ROUND(s.isahi_p * 100.0, 2) AS ISAHI_pct,
    
    ROUND(SUM(f.es_tala) * 100.0 / COUNT(*), 2) AS FTA_pct,

    ROUND(
        SUM(CASE WHEN f.fase_critica != 'Otro' AND f.es_humano = 1 THEN 1 ELSE 0 END) * 100.0 / 
        NULLIF(SUM(CASE WHEN f.fase_critica != 'Otro' THEN 1 ELSE 0 END), 0), 
    2) AS IPH_pct,

    ROUND(CAST(SUM(CASE WHEN f.primary_category = 'Ave' THEN 1 ELSE 0 END) AS FLOAT) / 
          NULLIF(SUM(CASE WHEN f.es_humano = 1 THEN 1 ELSE 0 END), 0), 2) AS Ratio_Aves_Humano,
          
    ROUND(CAST(SUM(CASE WHEN f.primary_category = 'Anfibio' THEN 1 ELSE 0 END) AS FLOAT) / 
          NULLIF(SUM(CASE WHEN f.es_humano = 1 THEN 1 ELSE 0 END), 0), 2) AS Ratio_Anfibios_Humano

FROM flags_por_clip f
JOIN stats_probabilisticas s ON f.loc_clean = s.loc_clean AND f.anio = s.anio
GROUP BY f.anio, f.loc_clean
ORDER BY f.anio ASC, f.loc_clean ASC;