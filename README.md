# TikTok Auto-Bot 🤖

Pipeline completo: **Claude genera guión → gTTS narra → Pexels pone imágenes → MoviePy ensambla → TikTok sube**

---

## ⚡ Instalación rápida

```bash
# 1. Clona o descarga la carpeta del bot
cd tiktok_bot

# 2. Crea un entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Instala dependencias
pip install -r requirements.txt

# 4. Instala ffmpeg (necesario para MoviePy)
#    macOS:
brew install ffmpeg
#    Ubuntu/Debian:
sudo apt install ffmpeg
#    Windows: descarga de https://ffmpeg.org/download.html

# 5. Configura tus claves
cp .env.example .env
# → Edita .env con tus API keys
```

---

## 🔑 APIs necesarias

| Servicio | Coste | Para qué |
|----------|-------|----------|
| **Anthropic** | ~$0.01/video | Genera el guión con Claude |
| **Pexels** | Gratis | Imágenes sin copyright |
| **TikTok Developer** | Gratis | Subir videos |

### Obtener el TikTok Access Token

1. Ve a https://developers.tiktok.com y crea una app
2. Activa los scopes: `video.upload` y `video.publish`
3. Usa el flujo OAuth 2.0 para obtener el access token
4. Pega el token en tu archivo `.env`

> ⚠️ TikTok puede tardar 1-3 días en aprobar tu app para producción.
> Mientras tanto, usa `privacy_level: "SELF_ONLY"` para publicar solo para ti.

---

## 🚀 Uso

```bash
# Cargar variables de entorno
export $(cat .env | xargs)

# Prueba inmediata (genera y sube 1 video ahora)
python bot.py --now

# Con tema específico
python bot.py --now datos curiosos del universo

# Modo automático (publica todos los días a las 10:00 AM)
python bot.py
```

---

## ⚙️ Personalización

Edita estas variables en `bot.py`:

```python
TOPIC_LIST = [
    "curiosidades del espacio exterior",   # ← añade tus temas aquí
    ...
]
SECONDS_PER_IMAGE = 4   # duración de cada imagen
```

---

## 📁 Estructura de archivos generados

```
output_videos/
  audio_TIMESTAMP.mp3     ← narración TTS
  img_0.jpg ... img_4.jpg ← imágenes de Pexels
  sub_0.jpg ... sub_4.jpg ← imágenes con subtítulos
  video_TIMESTAMP.mp4     ← video final
```

---

## 🗓️ Cambiar horario de publicación

En `bot.py`, modifica la línea del scheduler:

```python
# Todos los días a las 10:00 AM
scheduler.add_job(ejecutar_pipeline, "cron", hour=10, minute=0)

# Dos veces al día (10 AM y 6 PM)
scheduler.add_job(ejecutar_pipeline, "cron", hour="10,18", minute=0)

# Cada 6 horas
scheduler.add_job(ejecutar_pipeline, "interval", hours=6)
```

---

## 🎤 Voz de alta calidad (opcional)

Para usar ElevenLabs en lugar de gTTS (voz mucho más natural):

```bash
pip install elevenlabs
```

Reemplaza la función `generar_audio` en `bot.py`:

```python
from elevenlabs.client import ElevenLabs

def generar_audio(narracion, ruta_salida):
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    audio = client.generate(
        text=narracion,
        voice="Rachel",
        model="eleven_multilingual_v2"
    )
    with open(ruta_salida, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    clip = AudioFileClip(ruta_salida)
    return clip.duration
```
