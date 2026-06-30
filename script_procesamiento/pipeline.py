#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

USE_GPU = os.environ.get("USE_GPU", "0").strip()
CUDA_DIR = os.environ.get("CUDA_DIR", "/usr/local/cuda-12.2").strip()

os.environ["TF_XLA_FLAGS"] = "--tf_xla_auto_jit=0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

if USE_GPU == "1":
    os.environ["XLA_FLAGS"] = (
        f"--xla_cpu_enable_xla=false "
        f"--xla_gpu_enable_xla=false "
        f"--xla_gpu_cuda_data_dir={CUDA_DIR}"
    )
    os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
else:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["XLA_FLAGS"] = "--xla_cpu_enable_xla=false --xla_gpu_enable_xla=false"

import glob
import json
import math
from datetime import datetime
from typing import List, Tuple, Optional

import numpy as np
import pandas as pd
import soundfile as sf
import librosa

import tensorflow as tf
import tensorflow_hub as hub
import kagglehub

HAS_SCIPY = True
try:
    from scipy.signal import butter, sosfiltfilt
except Exception:
    HAS_SCIPY = False
    print("[WARN] scipy no disponible: se omitirá el filtro pasa-banda.")

tf.config.optimizer.set_jit(False)

print(f"[INFO] TensorFlow: {tf.__version__}")
print(f"[INFO] USE_GPU={USE_GPU} | CUDA_DIR={CUDA_DIR}")
print("Dispositivos GPU visibles para TF:", tf.config.list_physical_devices('GPU'))

DAY_START_HOUR = 6
DAY_END_HOUR = 18
CLIP_SECONDS = 5
PERCH_SR = 32000
YAMNET_SR = 16000
BP_LO_HZ = 300
BP_HI_HZ = 9000
CONF_BIRD = 0.50
CONF_DUBIOUS = 0.20
RMS_SILENCE_DB = -60.0

AUDIO_GLOBS = ["/content/*.WAV", "/content/*.wav"]
CLIP_CSV    = "clip_results_multiple.csv"
FILE_CSV    = "file_summary.csv"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def log_info(msg: str) -> None:
    print(f"[INFO] {msg}")

def log_warn(msg: str) -> None:
    print(f"[WARN] {msg}")

def log_error(msg: str) -> None:
    print(f"[ERROR] {msg}")

log_info("Cargando YAMNet…")
try:
    yamnet_model = hub.load("https://tfhub.dev/google/yamnet/1")
    yamnet_classes = pd.read_csv(
        "https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv"
    )["display_name"].tolist()
    YAMNET_OK = True
except Exception as e:
    log_error(f"No se pudo cargar YAMNet: {e}")
    yamnet_model, yamnet_classes = None, []
    YAMNET_OK = False

log_info("Cargando Perch…")
try:
    perch_path = kagglehub.model_download("google/bird-vocalization-classifier/tensorFlow2/perch_v2")
    perch_model = hub.load(perch_path)
    perch_infer = perch_model.signatures["serving_default"]
    labels = pd.read_csv(os.path.join(perch_path, "assets", "perch_v2_ebird_classes.csv"))
    PERCH_OK = True
except Exception as e:
    log_error(f"No se pudo cargar Perch: {e}")
    perch_infer, labels = None, pd.DataFrame()
    PERCH_OK = False

log_info("Cargando SurfPerch…")
try:
    surf_path = kagglehub.model_download("google/surfperch/TensorFlow2/1/1")
    surfperch_model = tf.saved_model.load(surf_path)
    SURF_OK = True
except Exception as e:
    log_error(f"No se pudo cargar SurfPerch: {e}")
    surfperch_model = None
    SURF_OK = False

def _safe_read_taxonomy(path_xlsx: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(path_xlsx)
        return df.rename(columns={
            "SPECIES_CODE": "ebird2021",
            "PRIMARY_COM_NAME": "common_name",
            "SCI_NAME": "sci_name"
        })
    except Exception as e:
        log_warn(f"No se pudo leer taxonomy Excel ({path_xlsx}): {e}. Se usará DataFrame vacío.")
        return pd.DataFrame(columns=["ebird2021", "common_name", "sci_name"])

taxonomy = _safe_read_taxonomy(os.path.join(BASE_DIR, "eBird_taxonomy_v2024.xlsx"))

def _safe_read_whitelist(path_csv: str) -> pd.DataFrame:
    try:
        wl = pd.read_csv(path_csv)
        wl_cols = [c.lower() for c in wl.columns]
        if "scientific_name" not in wl_cols:
            rename_map = {}
            for c in wl.columns:
                lc = c.lower()
                if lc == "sci_name":
                    rename_map[c] = "scientific_name"
                if lc in ("primary_com_name", "common"):
                    rename_map[c] = "common_name"
            if rename_map:
                wl = wl.rename(columns=rename_map)
        return wl
    except Exception as e:
        log_warn(f"No se pudo leer whitelist CSV ({path_csv}): {e}. Se usará DataFrame vacío.")
        return pd.DataFrame(columns=["ebird2021", "scientific_name", "common_name"])

whitelist = _safe_read_whitelist(os.path.join(BASE_DIR, "species_whitelists_peru.csv"))

def is_in_whitelist(ebird_code: str, sci_name: str, common_name: str) -> bool:
    try:
        return (
            (whitelist.get("ebird2021", pd.Series(dtype=str)) == ebird_code).any() or
            (whitelist.get("scientific_name", pd.Series(dtype=str)).str.lower() == str(sci_name).lower()).any() or
            (whitelist.get("common_name", pd.Series(dtype=str)).str.lower() == str(common_name).lower()).any()
        )
    except Exception:
        return False

def file_oldest_timestamp(path: str) -> datetime:
    st = os.stat(path)
    ts = min(st.st_mtime, getattr(st, "st_ctime", st.st_mtime))
    return datetime.fromtimestamp(ts)

def day_or_night(dt: datetime) -> str:
    h = dt.hour
    return "day" if (DAY_START_HOUR <= h < DAY_END_HOUR) else "night"

def _mkset(words: List[str]) -> set:
    return set([w.strip().lower() for w in words])

BIRD_KEYS = _mkset(["bird", "bird vocalization, bird call, bird song", "chirp, tweet", "fowl", "crow", "owl"])
AMPH_KEYS = _mkset(["frog", "croak", "tree frog", "amphibian"])
MAMM_KEYS = _mkset(["mammal", "primate", "monkey", "howler monkey", "bat", "dog", "cat"])
INSE_KEYS = _mkset(["insect", "cricket", "cicada", "mosquito", "buzz"])
ANTH_KEYS = _mkset([
    "chainsaw","speech","conversation","narration, monologue","shout","child speech, kid speaking",
    "car","vehicle","motorcycle","engine","truck","airplane","helicopter","siren","footsteps",
    "jackhammer","drill","hammer","gunshot, gunfire","music","street music","mechanisms"
])
AMBI_KEYS = _mkset([
    "rain","raindrop","thunder","wind","water","stream","river","rustle","white noise","pink noise","environmental noise"
])

def map_yamnet_category(topk: List[Tuple[str, float]]) -> Tuple[str, str, float]:
    buckets = [
        ("Antropogénico", ANTH_KEYS),
        ("Ave", BIRD_KEYS),
        ("Anfibio", AMPH_KEYS),
        ("Mamífero", MAMM_KEYS),
        ("Insecto", INSE_KEYS),
        ("Ruido ambiental", AMBI_KEYS),
    ]
    best = ("", "", 0.0)
    for label, score in topk:
        lcl = str(label).lower()
        for cname, keyset in buckets:
            if any(k in lcl for k in keyset):
                if score > best[2]:
                    best = (cname, label, score)
                break
    return best

def design_bandpass(sr: int, lo_hz: float, hi_hz: float, order: int = 4):
    nyq = 0.5 * sr
    lo = max(1.0, lo_hz) / nyq
    hi = min(hi_hz, sr/2 - 100.0) / nyq
    if hi <= lo:
        hi = min(0.49, lo + 0.01)
    sos = butter(order, [lo, hi], btype="bandpass", output="sos")
    return sos

def apply_bandpass(x: np.ndarray, sr: int) -> np.ndarray:
    if not HAS_SCIPY:
        return x
    sos = design_bandpass(sr, BP_LO_HZ, BP_HI_HZ, order=4)
    try:
        return sosfiltfilt(sos, x).astype(np.float32)
    except Exception as e:
        log_warn(f"Filtro pasa-banda falló: {e}")
        return x

def peak_normalize(x: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    m = np.max(np.abs(x)) + eps
    return (x / m).astype(np.float32)

def dBFS(x: np.ndarray, eps: float = 1e-12) -> float:
    rms = np.sqrt(np.mean(np.square(x)) + eps)
    return 20.0 * math.log10(rms + eps)

def preprocess_audio(path: str, target_sr: int = PERCH_SR) -> Tuple[np.ndarray, int]:
    try:
        y, sr = sf.read(path, always_2d=False)
    except Exception as e:
        raise RuntimeError(f"No se pudo leer audio con soundfile: {e}")

    if y is None or len(y) == 0:
        raise RuntimeError("Audio vacío o no legible.")

    if np.ndim(y) > 1:
        y = np.mean(y, axis=1)

    if sr != target_sr:
        try:
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            sr = target_sr
        except Exception as e:
            raise RuntimeError(f"Fallo en resample a {target_sr} Hz: {e}")

    y = apply_bandpass(y, sr)
    y = peak_normalize(y)
    return y.astype(np.float32), sr

def segment_audio(y: np.ndarray, sr: int, clip_sec: int = CLIP_SECONDS) -> List[np.ndarray]:
    clip_len = int(sr * clip_sec)
    n_clips = int(np.ceil(len(y) / clip_len))
    clips = []
    for i in range(n_clips):
        start = i * clip_len
        end = start + clip_len
        chunk = y[start:end]
        if len(chunk) < clip_len:
            chunk = np.pad(chunk, (0, clip_len - len(chunk)))
        clips.append(chunk.astype(np.float32))
    return clips

def yamnet_topk_from_clip(clip_32k: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
    if not YAMNET_OK or yamnet_model is None:
        return []
    try:
        clip_16k = librosa.resample(clip_32k, orig_sr=PERCH_SR, target_sr=YAMNET_SR)
    except Exception as e:
        log_warn(f"Resample a 16k para YAMNet falló: {e}")
        return []
    try:
        waveform = tf.constant(clip_16k, dtype=tf.float32)
        scores, _, _ = yamnet_model(waveform)
        mean_scores = scores.numpy().mean(axis=0)
        idx = mean_scores.argsort()[::-1][:top_k]
        return [(yamnet_classes[i], float(mean_scores[i])) for i in idx]
    except Exception as e:
        log_warn(f"Inferencia YAMNet falló: {e}")
        return []

def classify_perch_clip(clip_32k: np.ndarray) -> Tuple[str, str, str, float]:
    if not PERCH_OK or perch_infer is None or labels.empty:
        return ("", "", "", 0.0)
    try:
        audio_batch = tf.expand_dims(clip_32k, axis=0)
        outputs = perch_infer(inputs=tf.constant(audio_batch))
        probs = tf.nn.softmax(outputs["label"]).numpy()[0]
        top_idx = int(np.argmax(probs))
        ebird_code = str(labels.loc[top_idx, "ebird2021"])
        row = taxonomy[taxonomy["ebird2021"] == ebird_code] if not taxonomy.empty else pd.DataFrame()
        if not row.empty:
            sci = str(row["sci_name"].values[0])
            common = str(row["common_name"].values[0])
        else:
            sci, common = "Desconocido", "Desconocido"
        return ebird_code, sci, common, float(probs[top_idx])
    except Exception as e:
        log_warn(f"Inferencia Perch falló: {e}")
        return ("", "", "", 0.0)

def embed_surfperch(clip_32k: np.ndarray) -> Optional[np.ndarray]:
    if not SURF_OK or surfperch_model is None:
        return None
    try:
        batch = clip_32k[np.newaxis, :]
        outputs = surfperch_model.infer_tf(batch)
        return outputs["embedding"].numpy()[0]
    except Exception as e:
        log_warn(f"Embedding SurfPerch falló: {e}")
        return None

def decide_status(prob: float, yamnet_top: List[Tuple[str, float]]) -> str:
    labels_low = [str(l).lower() for l, _ in yamnet_top]
    is_birdish = any(("bird" in l) for l in labels_low)
    if prob >= CONF_BIRD and is_birdish:
        return "Confiable"
    elif prob >= CONF_DUBIOUS:
        return "Dudoso"
    else:
        return "No-Ave"

def analyze_file(path: str) -> Tuple[List[dict], dict]:
    ts = file_oldest_timestamp(path)
    period = day_or_night(ts)

    y, sr = preprocess_audio(path, target_sr=PERCH_SR)
    clips = segment_audio(y, sr, clip_sec=CLIP_SECONDS)

    st = os.stat(path)
    size_mb = round(st.st_size / (1024*1024), 2)
    duration_sec = round(len(y) / sr, 2)
    created_str = ts.strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    agg = {
        "filename": os.path.basename(path),
        "total_clips": len(clips),
        "duration_sec": duration_sec,
        "size_mb": size_mb,
        "created": created_str,
        "confiables": 0, "dudosos": 0, "no_ave": 0,
        "en_whitelist": 0, "fuera_whitelist": 0,
        "day_clips": 0, "night_clips": 0,
        "n_ave": 0, "n_mamifero": 0, "n_anfibio": 0,
        "n_insecto": 0, "n_antropogenico": 0, "n_ruido_ambiental": 0, "n_silencio": 0
    }

    if period == "day":
        agg["day_clips"] = len(clips)
    else:
        agg["night_clips"] = len(clips)

    for i, clip in enumerate(clips):
        clip_db = dBFS(clip)
        is_silence = clip_db < RMS_SILENCE_DB

        topk = []
        try:
            topk = yamnet_topk_from_clip(clip, top_k=5)
        except Exception as e:
            log_warn(f"YAMNet falló en clip {i}: {e}")
            topk = []

        primary_cat, trig_label, trig_score = map_yamnet_category(topk)

        if not is_silence:
            ebird_code, sci, common, prob = classify_perch_clip(clip)
            if (ebird_code, sci, common, prob) == ("", "", "", 0.0):
                log_warn(f"Perch falló en clip {i}.")
        else:
            ebird_code, sci, common, prob = ("", "", "", 0.0)

        status = decide_status(prob, topk) if not is_silence else "No-Ave"
        wl = is_in_whitelist(ebird_code, sci, common) if ebird_code or sci or common else False
        wl_status = "En whitelist" if wl else "Fuera whitelist"

        if status == "Confiable":
            agg["confiables"] += 1
        elif status == "Dudoso":
            agg["dudosos"] += 1
        else:
            agg["no_ave"] += 1

        if wl:
            agg["en_whitelist"] += 1
        else:
            agg["fuera_whitelist"] += 1

        if status == "Confiable" and wl:
            cat = "Ave"
        else:
            if is_silence:
                cat = "Silencio"
            elif primary_cat:
                cat = primary_cat
            else:
                cat = "Ruido ambiental"

        if   cat == "Ave": agg["n_ave"] += 1
        elif cat == "Mamífero": agg["n_mamifero"] += 1
        elif cat == "Anfibio": agg["n_anfibio"] += 1
        elif cat == "Insecto": agg["n_insecto"] += 1
        elif cat == "Antropogénico": agg["n_antropogenico"] += 1
        elif cat == "Ruido ambiental": agg["n_ruido_ambiental"] += 1
        elif cat == "Silencio": agg["n_silencio"] += 1

        surf_emb = None
        if not is_silence:
            surf_emb = embed_surfperch(clip)
            if surf_emb is None:
                log_warn(f"SurfPerch falló en clip {i}.")

        if not topk:
            log_warn(f"YAMNet falló en clip {i}.")
        if not is_silence and prob == 0.0 and (not ebird_code and not sci and not common):
            log_warn(f"Perch falló en clip {i}: prob=0.0 sin especie.")
        if not is_silence and surf_emb is None:
            log_warn(f"SurfPerch falló en clip {i}: sin embedding.")

        rows.append({
            "filename": os.path.basename(path),
            "clip_idx": i,
            "period": period,
            "clip_dbfs": round(clip_db, 2),
            "status": status,
            "primary_category": cat,
            "species_common": common,
            "species_sci": sci,
            "ebird_code": ebird_code,
            "prob": round(prob, 3),
            "whitelist": wl_status,
            "yamnet_top5": json.dumps(topk, ensure_ascii=False),
            "surfperch_emb": json.dumps(surf_emb.tolist()) if isinstance(surf_emb, np.ndarray) else "",
            "duration_sec": duration_sec,
            "size_mb": size_mb,
            "created": created_str
        })

    return rows, agg

def main():
    CSV_MAESTRO = os.path.join(BASE_DIR, "mapa_audios_wsl.csv")
    RESULTS_DIR = os.path.join(BASE_DIR, "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    if not os.path.exists(CSV_MAESTRO):
        log_error(f"No se encontró {CSV_MAESTRO}")
        return

    try:
        df = pd.read_csv(CSV_MAESTRO)
    except Exception as e:
        log_error(f"No se pudo leer el CSV maestro: {e}")
        return

    expected_cols = {"ruta_completa", "localidad", "campaña", "dispositivo"}
    if not expected_cols.issubset(df.columns):
        log_error(f"El CSV maestro debe contener las columnas: {expected_cols}")
        return

    all_rows, aggs = [], []

    log_info(f"Procesando {len(df)} audios del CSV maestro...")

    for idx, row in df.iterrows():
        path = row["ruta_completa"]
        loc  = str(row["localidad"])
        camp = str(row["campaña"])
        dev  = str(row["dispositivo"])

        if not os.path.exists(path):
            log_warn(f"No se encontró archivo: {path}")
            continue

        out_dir = os.path.join(RESULTS_DIR, loc, camp, dev)
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n[{idx+1}/{len(df)}] {os.path.basename(path)}")
        print(f"    → Localidad: {loc} | Campaña: {camp} | Dispositivo: {dev}")

        try:
            rows, agg = analyze_file(path)

            for r in rows:
                r.update({
                    "localidad": loc,
                    "campaña": camp,
                    "dispositivo": dev,
                    "fecha": row.get("fecha", ""),
                    "hora": row.get("hora", "")
                })
            agg.update({
                "localidad": loc,
                "campaña": camp,
                "dispositivo": dev,
                "fecha": row.get("fecha", ""),
                "hora": row.get("hora", "")
            })

            clip_path = os.path.join(out_dir, "clip_results.csv")
            file_path = os.path.join(out_dir, "file_summary.csv")

            pd.DataFrame(rows).to_csv(clip_path, index=False)
            pd.DataFrame([agg]).to_csv(file_path, index=False)

            print(f"  → Guardado en {clip_path}")

            all_rows.extend(rows)
            aggs.append(agg)

        except Exception as e:
            log_error(f"{os.path.basename(path)} falló: {e}")

    if all_rows:
        df_clips = pd.DataFrame(all_rows)
        df_clips.to_csv(os.path.join(RESULTS_DIR, "master_clips.csv"), index=False, encoding="utf-8-sig")
        log_info("Consolidado de clips guardado en results/master_clips.csv")

    if aggs:
        df_files = pd.DataFrame(aggs)

        def pct(a, b): 
            try:
                return round(100.0 * a / b, 2) if b else 0.0
            except Exception:
                return 0.0

        df_files["pct_ave"] = [pct(a, t) for a, t in zip(df_files["n_ave"], df_files["total_clips"])]
        df_files["pct_antropogenico"] = [pct(a, t) for a, t in zip(df_files["n_antropogenico"], df_files["total_clips"])]
        df_files["pct_ruido"] = [pct(a, t) for a, t in zip(df_files["n_ruido_ambiental"], df_files["total_clips"])]

        df_files.to_csv(os.path.join(RESULTS_DIR, "master_files.csv"), index=False, encoding="utf-8-sig")
        log_info("Consolidado de archivos guardado en results/master_files.csv")

    print("\nFlujo completado con éxito.")

if __name__ == "__main__":
    print("[DEBUG] __name__ =", __name__)
    main()