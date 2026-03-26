"""
TikTok Auto-Bot
Pipeline: Claude genera guión → gTTS genera voz → Pexels busca imágenes → MoviePy ensambla → TikTok sube
"""

import os
import json
import time
import requests
import anthropic
from pathlib import Path
from gtts import gTTS
from moviepy.editor import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    CompositeVideoClip, TextClip
)
from apscheduler.schedulers.blocking import BlockingScheduler
from PIL import Image, ImageDraw, ImageFont
import textwrap
import tempfile
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# CONFIGURACIÓN — edita estas variables
# ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PEXELS_API_KEY    = os.getenv("PEXELS_API_KEY", "")    # gratis en pexels.com/api
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")

TOPIC_LIST = [
    "curiosidades del espacio exterior",
    "datos sorprendentes del océano profundo",
    "avances de inteligencia artificial en 2025",
    "animales con habilidades increíbles",
    "lugares misterioso del mundo",
]

VIDEO_SIZE   = (1080, 1920)   # formato vertical TikTok
SECONDS_PER_IMAGE = 4         # duración de cada imagen
OUTPUT_DIR   = Path("output_videos")
OUTPUT_DIR.mkdir(exist_ok=True)
# ──────────────────────────────────────────────


def generar_guion(tema: str) -> dict:
    """Llama a Claude para generar el guión + título + hashtags."""
    log.info(f"Generando guión para: {tema}")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                f"Crea un video corto de TikTok sobre: {tema}\n"
                "El video dura ~45 segundos. Responde ÚNICAMENTE con JSON válido:\n"
                "{\n"
                '  "titulo": "título atractivo (máx 60 chars)",\n'
                '  "narración": "texto narrado en español, ~120 palabras, divídelo en 5 bloques separados por ||",\n'
                '  "palabras_clave": ["3 palabras clave en inglés para buscar imágenes"],\n'
                '  "hashtags": "#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5"\n'
                "}"
            )
        }]
    )
    raw = msg.content[0].text.strip()
    # limpia backticks si los hay
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def generar_audio(narracion: str, ruta_salida: str) -> float:
    """Convierte texto a MP3 con gTTS y devuelve la duración en segundos."""
    log.info("Generando audio TTS...")
    tts = gTTS(text=narracion, lang="es", slow=False)
    tts.save(ruta_salida)
    clip = AudioFileClip(ruta_salida)
    duracion = clip.duration
    clip.close()
    return duracion


def buscar_imagenes_pexels(palabras: list[str], cantidad: int = 5) -> list[str]:
    """Descarga imágenes de Pexels y devuelve las rutas locales."""
    log.info(f"Buscando imágenes: {palabras}")
    headers = {"Authorization": PEXELS_API_KEY}
    query = " ".join(palabras)
    url = f"https://api.pexels.com/v1/search?query={query}&per_page={cantidad}&orientation=portrait"
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    fotos = resp.json().get("photos", [])

    rutas = []
    for i, foto in enumerate(fotos):
        img_url = foto["src"]["portrait"]
        img_resp = requests.get(img_url, timeout=10)
        ruta = OUTPUT_DIR / f"img_{i}.jpg"
        ruta.write_bytes(img_resp.content)
        rutas.append(str(ruta))
    return rutas


def agregar_subtitulo_a_imagen(ruta_img: str, texto: str, ruta_salida: str):
    """Añade subtítulos centrados en la parte inferior de la imagen."""
    img = Image.open(ruta_img).convert("RGB").resize(VIDEO_SIZE)
    draw = ImageDraw.Draw(img)

    # Fondo semitransparente para el texto
    overlay = Image.new("RGBA", VIDEO_SIZE, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rectangle([(0, VIDEO_SIZE[1] - 280), (VIDEO_SIZE[0], VIDEO_SIZE[1])],
                      fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Fuente (usa la default de Pillow si no hay fuente instalada)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        font = ImageFont.load_default()

    # Envuelve el texto
    lines = textwrap.wrap(texto, width=30)
    y = VIDEO_SIZE[1] - 250
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (VIDEO_SIZE[0] - w) // 2
        # sombra
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += 60

    img.save(ruta_salida)


def crear_video(rutas_img: list[str], ruta_audio: str, bloques: list[str],
                ruta_salida: str) -> str:
    """Ensambla imágenes + audio + subtítulos en un MP4."""
    log.info("Ensamblando video con MoviePy...")
    audio = AudioFileClip(ruta_audio)
    duracion_total = audio.duration
    dur_por_img = duracion_total / len(rutas_img)

    clips = []
    for i, (img_path, bloque) in enumerate(zip(rutas_img, bloques)):
        # Imagen con subtítulo
        img_sub = str(OUTPUT_DIR / f"sub_{i}.jpg")
        agregar_subtitulo_a_imagen(img_path, bloque, img_sub)
        clip = (ImageClip(img_sub)
                .set_duration(dur_por_img)
                .resize(VIDEO_SIZE))
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    video.write_videofile(
        ruta_salida,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(OUTPUT_DIR / "temp_audio.m4a"),
        remove_temp=True,
        logger=None
    )
    audio.close()
    video.close()
    return ruta_salida


def subir_a_tiktok(ruta_video: str, titulo: str, hashtags: str) -> bool:
    """
    Sube el video a TikTok usando la Content Posting API v2.
    Requiere: TIKTOK_ACCESS_TOKEN con scope video.upload
    Documentación: https://developers.tiktok.com/doc/content-posting-api-get-started
    """
    log.info("Subiendo video a TikTok...")

    # 1) Inicializar la subida
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    file_size = os.path.getsize(ruta_video)
    payload = {
        "post_info": {
            "title": f"{titulo} {hashtags}"[:150],
            "privacy_level": "SELF_ONLY",  # cambia a PUBLIC_TO_EVERYONE cuando estés listo
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1
        }
    }
    resp = requests.post(init_url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()["data"]
    upload_url  = data["upload_url"]
    publish_id  = data["publish_id"]

    # 2) Subir el archivo
    with open(ruta_video, "rb") as f:
        video_bytes = f.read()
    upload_headers = {
        "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
        "Content-Length": str(file_size),
        "Content-Type": "video/mp4"
    }
    up_resp = requests.put(upload_url, headers=upload_headers, data=video_bytes, timeout=120)
    up_resp.raise_for_status()

    # 3) Verificar estado
    time.sleep(5)
    status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
    st = requests.post(status_url, headers=headers,
                       json={"publish_id": publish_id}, timeout=15)
    st.raise_for_status()
    log.info(f"Estado TikTok: {st.json()}")
    return True


# ──────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ──────────────────────────────────────────────
def ejecutar_pipeline(tema: str = None):
    if not tema:
        import random
        tema = random.choice(TOPIC_LIST)

    log.info(f"=== Iniciando pipeline para: {tema} ===")
    ts = int(time.time())

    try:
        # 1. Guión
        guion = generar_guion(tema)
        bloques = guion["narración"].split("||")
        log.info(f"Título: {guion['titulo']}")

        # 2. Audio
        ruta_audio = str(OUTPUT_DIR / f"audio_{ts}.mp3")
        generar_audio(" ".join(bloques), ruta_audio)

        # 3. Imágenes
        rutas_img = buscar_imagenes_pexels(guion["palabras_clave"], cantidad=len(bloques))
        if not rutas_img:
            raise RuntimeError("No se encontraron imágenes en Pexels")

        # Iguala listas
        while len(rutas_img) < len(bloques):
            rutas_img.append(rutas_img[-1])
        rutas_img = rutas_img[:len(bloques)]

        # 4 + 5. Video con subtítulos
        ruta_video = str(OUTPUT_DIR / f"video_{ts}.mp4")
        crear_video(rutas_img, ruta_audio, bloques, ruta_video)

        # 6. Subir a TikTok
        if TIKTOK_ACCESS_TOKEN:
            subir_a_tiktok(ruta_video, guion["titulo"], guion["hashtags"])
            log.info("✅ Video subido exitosamente")
        else:
            log.warning("⚠️  TIKTOK_ACCESS_TOKEN no configurado. Video guardado localmente.")

        log.info(f"Video guardado en: {ruta_video}")

    except Exception as e:
        log.error(f"Error en el pipeline: {e}", exc_info=True)


# ──────────────────────────────────────────────
# SCHEDULER — publica automáticamente
# ──────────────────────────────────────────────
def iniciar_scheduler():
    """Publica un video cada día a las 10:00 AM (hora local)."""
    scheduler = BlockingScheduler()
    scheduler.add_job(ejecutar_pipeline, "cron", hour=10, minute=0)
    log.info("Scheduler iniciado. Publica todos los días a las 10:00 AM.")
    log.info("Presiona Ctrl+C para detener.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler detenido.")


if __name__ == "__main__":
    import sys
    if "--now" in sys.argv:
        # Ejecución inmediata para pruebas
        tema_arg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        ejecutar_pipeline(tema_arg)
    else:
        iniciar_scheduler()
