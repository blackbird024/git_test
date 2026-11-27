#!/usr/bin/env python3
"""Genera un YouTube Short (1080x1920, 30 fps) a partir de un guion JSON.

Uso:
    python3 generar_short.py guiones/001_datos_que_parecen_falsos.json

Produce en salida/<slug>/:
    <slug>.mp4      video final listo para subir
    portada.png     imagen de portada
    youtube.txt     título, descripción y etiquetas para copiar y pegar
"""
import json
import math
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "assets" / "fonts"
VOICES = Path(os.environ.get("VOICES_DIR", ROOT / "assets" / "voices"))
EMOJI_FONT = os.environ.get("EMOJI_FONT", "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")

W, H, FPS, SR = 1080, 1920, 30, 22050
SENTENCE_GAP = 0.22   # silencio entre frases (s)
SCENE_GAP = 0.30      # silencio entre escenas (s)
LEAD_IN = 0.15        # silencio al principio


# ----------------------------------------------------------------- utilidades
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def font(name, size, _cache={}):
    key = (name, size)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(str(FONTS / name), size)
    return _cache[key]


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


# ---------------------------------------------------------------------- audio
def find_voice(name):
    for p in VOICES.rglob(f"{name}.onnx"):
        return p
    sys.exit(f"No encuentro la voz {name}.onnx en {VOICES}. Ejecuta ./instalar.sh")


def tts(text, voice, out_wav, length_scale=0.92):
    subprocess.run(
        [sys.executable, "-m", "piper", "-m", str(voice), "-c", str(voice) + ".json",
         "-f", str(out_wav), "--length-scale", str(length_scale), "--sentence-silence", "0"],
        input=text.encode(), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with wave.open(str(out_wav)) as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if sr != SR:  # remuestreo lineal sencillo
        n = int(len(data) * SR / sr)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data)
    # recorta silencio inicial/final
    idx = np.where(np.abs(data) > 0.01)[0]
    if len(idx):
        data = data[max(idx[0] - 200, 0): idx[-1] + 600]
    return data.astype(np.float32)


def silence(sec):
    return np.zeros(int(sec * SR), dtype=np.float32)


def make_music(duration):
    """Pad ambiental suave + arpegio, generado por síntesis (sin derechos de autor)."""
    t = np.arange(int(duration * SR)) / SR
    out = np.zeros_like(t)
    # Am - F - C - G
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
    bar = 2.4
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    for i in range(int(duration / bar) + 1):
        s, e = int(i * bar * SR), int(min((i + 1) * bar, duration) * SR)
        if s >= len(t):
            break
        seg = t[s:e] - i * bar
        env = np.minimum(1, seg / 0.4) * np.minimum(1, (bar - seg) / 0.4)
        ch = chords[i % 4]
        for m in ch:
            f = midi(m)
            out[s:e] += env * 0.10 * (np.sin(2 * np.pi * f * seg) + 0.5 * np.sin(2 * np.pi * f * 1.003 * seg))
        out[s:e] += env * 0.12 * np.sin(2 * np.pi * midi(ch[0] - 12) * seg)
        # arpegio en corcheas
        step = bar / 8
        for k in range(8):
            a = int((i * bar + k * step) * SR)
            b = min(a + int(step * SR), len(t))
            if a >= len(t):
                break
            tt = t[a:b] - (i * bar + k * step)
            note = ch[[0, 1, 2, 1, 0, 2, 1, 2][k]] + 12
            out[a:b] += 0.07 * np.exp(-tt * 9) * np.sin(2 * np.pi * midi(note) * tt)
        # pulso suave (bombo) en cada tiempo
        for k in range(4):
            a = int((i * bar + k * bar / 4) * SR)
            b = min(a + int(0.25 * SR), len(t))
            if a >= len(t):
                break
            tt = t[a:b] - (i * bar + k * bar / 4)
            out[a:b] += 0.18 * np.exp(-tt * 18) * np.sin(2 * np.pi * (55 + 60 * np.exp(-tt * 30)) * tt)
    # filtro paso bajo sencillo para suavizar
    k = np.ones(6) / 6
    out = np.convolve(out, k, mode="same")
    return out / (np.abs(out).max() + 1e-9)


def make_whoosh(sec=0.45):
    n = int(sec * SR)
    noise = np.random.default_rng(1).standard_normal(n)
    tt = np.arange(n) / n
    env = np.sin(np.pi * tt) ** 2
    # barrido: media móvil de tamaño decreciente
    out = np.zeros(n)
    for w, sl in ((24, slice(0, n // 3)), (10, slice(n // 3, 2 * n // 3)), (4, slice(2 * n // 3, n))):
        out[sl] = np.convolve(noise, np.ones(w) / w, mode="same")[sl]
    return (out * env * 0.6).astype(np.float32)


# --------------------------------------------------------------------- gráficos
def render_emoji(ch, size):
    f = ImageFont.truetype(EMOJI_FONT, 109)
    img = Image.new("RGBA", (220, 220), (0, 0, 0, 0))
    ch = ch.replace("\ufe0f", "")
    ImageDraw.Draw(img).text((110, 110), ch, font=f, embedded_color=True, anchor="mm")
    img = img.crop(img.getbbox())
    r = size / max(img.size)
    return img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)


def wrap(text, fnt, max_w, draw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_background(c1, c2):
    """Degradado grande (más alto que el video) para poder desplazarlo."""
    c1, c2 = np.array(hex2rgb(c1), float), np.array(hex2rgb(c2), float)
    bh = H + 400
    y = np.linspace(0, 1, bh)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    mix = np.clip(0.75 * y + 0.25 * x, 0, 1)
    mix = 0.5 - 0.5 * np.cos(mix * 2 * np.pi)  # sube y baja: c1 -> c2 -> c1
    arr = c1 * (1 - mix) + c2 * mix
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def make_blob(radius, color, alpha):
    s = radius * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((radius // 2, radius // 2, s - radius // 2, s - radius // 2),
                                fill=color + (alpha,))
    return img.filter(ImageFilter.GaussianBlur(radius // 4))


def make_vignette():
    y, x = np.ogrid[:H, :W]
    d = np.sqrt(((x - W / 2) / (W * 0.75)) ** 2 + ((y - H / 2) / (H * 0.7)) ** 2)
    a = (np.clip(d - 0.45, 0, 1) * 330).clip(0, 170).astype(np.uint8)
    v = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    v.putalpha(Image.fromarray(a))
    return v


def draw_outlined(draw, xy, text, fnt, fill, stroke=8, anchor="mm"):
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor,
              stroke_width=stroke, stroke_fill=(0, 0, 0))


def build_static_layer(scene):
    """Capa con insignia y titular (no se anima salvo la entrada)."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if scene.get("badge"):
        f = font("Anton-Regular.ttf", 64)
        tw = d.textlength(scene["badge"], font=f)
        bx0, by0 = (W - tw) / 2 - 44, 250
        d.rounded_rectangle((bx0, by0, bx0 + tw + 88, by0 + 100), radius=50, fill=(255, 225, 77))
        d.text((W / 2, by0 + 50), scene["badge"], font=f, fill=(20, 20, 20), anchor="mm")
    size = 118
    while True:
        f = font("Anton-Regular.ttf", size)
        lines = wrap(scene["headline"], f, 940, d)
        if len(lines) <= 2 or size <= 70:
            break
        size -= 6
    y = 1130
    for line in lines:
        draw_outlined(d, (W / 2, y), line, f, (255, 255, 255), stroke=7)
        y += int(size * 1.12)
    return layer


def chunk_words(sentence):
    words, chunks, cur = sentence.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or len(" ".join(cur)) >= 15 or re.search(r"[,.;:?!]$", w):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def build_captions(sentences_timing):
    """Lista de (inicio, fin, [(palabra, inicio, fin)]) para subtítulos palabra a palabra."""
    caps = []
    for text, start, dur in sentences_timing:
        chunks = chunk_words(text)
        total = sum(len(w) + 1 for c in chunks for w in c)
        t = start
        for c in chunks:
            words = []
            for w in c:
                wd = dur * (len(w) + 1) / total
                words.append((w, t, t + wd))
                t += wd
            caps.append((words[0][1], words[-1][2], words))
    return caps


def draw_caption(frame, cap, now):
    start, end, words = cap
    pop = ease_out_back((now - start) / 0.18)
    size = int(88 * (0.8 + 0.2 * pop))
    f = font("Montserrat-Black.ttf", size)
    d = ImageDraw.Draw(frame)
    texts = [w.upper() for w, _, _ in words]
    space = d.textlength(" ", font=f)
    widths = [d.textlength(t, font=f) for t in texts]
    total = sum(widths) + space * (len(texts) - 1)
    lines = [[0, list(range(len(texts)))]]
    if total > 980:  # parte en dos líneas
        mid = max(1, len(texts) // 2)
        lines = [[0, list(range(mid))], [0, list(range(mid, len(texts)))]]
    y = 1500 - (len(lines) - 1) * size * 0.6
    for _, idxs in lines:
        lw = sum(widths[i] for i in idxs) + space * (len(idxs) - 1)
        x = (W - lw) / 2
        for i in idxs:
            w, ws, we = words[i]
            color = (255, 225, 77) if ws <= now < we + 0.05 else (255, 255, 255)
            d.text((x, y), texts[i], font=f, fill=color, anchor="lm",
                   stroke_width=9, stroke_fill=(0, 0, 0))
            x += widths[i] + space
        y += size * 1.15


# ----------------------------------------------------------------------- main
def main(script_path):
    script = json.load(open(script_path, encoding="utf-8"))
    slug = script["slug"]
    out_dir = ROOT / "salida" / slug
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    voice = find_voice(script.get("voice", "es_MX-ald-medium"))

    # 1) voz, escena por escena y frase por frase
    print("» Generando narración…")
    voice_track = [silence(LEAD_IN)]
    t = LEAD_IN
    scenes = []
    for si, sc in enumerate(script["scenes"]):
        s_start = t
        timing = []
        for k, sent in enumerate(split_sentences(sc["narration"])):
            audio = tts(sent, voice, tmp / f"s{si}_{k}.wav")
            timing.append((sent, t, len(audio) / SR))
            voice_track.append(audio)
            t += len(audio) / SR
            voice_track.append(silence(SENTENCE_GAP))
            t += SENTENCE_GAP
        voice_track.append(silence(SCENE_GAP))
        t += SCENE_GAP
        scenes.append({"data": sc, "start": s_start, "end": t, "caps": build_captions(timing)})
    voice_audio = np.concatenate(voice_track)
    voice_audio = np.concatenate([voice_audio, silence(0.6)])
    duration = len(voice_audio) / SR
    scenes[-1]["end"] = duration
    print(f"  duración: {duration:.1f} s")

    # 2) mezcla: voz + música con ducking + whoosh en cada cambio de escena
    print("» Mezclando audio…")
    music = make_music(duration)
    env = np.convolve(np.abs(voice_audio), np.ones(int(0.25 * SR)) / int(0.25 * SR), mode="same")
    duck = 1 - 0.6 * np.clip(env / 0.04, 0, 1)
    mix = voice_audio / (np.abs(voice_audio).max() + 1e-9) * 0.9 + music * 0.16 * duck
    wh = make_whoosh()
    for sc in scenes[1:]:
        a = int(max(sc["start"] - 0.2, 0) * SR)
        b = min(a + len(wh), len(mix))
        mix[a:b] += wh[: b - a] * 0.5
    fade = int(0.8 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = np.clip(mix / max(1.0, np.abs(mix).max() / 0.95), -1, 1)
    audio_path = tmp / "mezcla.wav"
    with wave.open(str(audio_path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

    # 3) preparar capas
    print("» Preparando gráficos…")
    vignette = make_vignette()
    for sc in scenes:
        d = sc["data"]
        sc["bg"] = make_background(*d["colors"])
        sc["static"] = build_static_layer(d)
        sc["emoji"] = render_emoji(d["emoji"], 520)
        c2 = hex2rgb(d["colors"][1])
        light = tuple(min(255, int(v * 1.8 + 40)) for v in c2)
        sc["blobs"] = [make_blob(r, light, a) for r, a in ((420, 90), (300, 70), (360, 60))]

    # 4) render de fotogramas -> ffmpeg
    print("» Renderizando video…")
    video_path = out_dir / f"{slug}.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(audio_path),
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-movflags", "+faststart",
         str(video_path)], stdin=subprocess.PIPE)

    n_frames = int(duration * FPS)
    cover = None
    for fi in range(n_frames):
        now = fi / FPS
        sc = next(s for s in scenes if s["start"] <= now < s["end"] or s is scenes[-1])
        local = now - sc["start"]
        # fondo animado
        off = int(200 + 200 * math.sin(now * 0.6))
        frame = sc["bg"].crop((0, off, W, off + H)).convert("RGBA")
        for k, b in enumerate(sc["blobs"]):
            bx = int(W * (0.2 + 0.6 * (0.5 + 0.5 * math.sin(now * (0.35 + 0.1 * k) + k * 2)))) - b.width // 2
            by = int(H * (0.15 + 0.7 * (0.5 + 0.5 * math.cos(now * (0.27 + 0.08 * k) + k)))) - b.height // 2
            frame.paste(b, (bx, by), b)
        frame.alpha_composite(vignette)
        # emoji: entrada con rebote + flotación
        p = ease_out_back(local / 0.45)
        scale = max(0.05, p) * (1 + 0.03 * math.sin(now * 3))
        em = sc["emoji"]
        ew, eh = max(1, int(em.width * scale)), max(1, int(em.height * scale))
        e = em.resize((ew, eh), Image.BILINEAR)
        ey = int(720 + 18 * math.sin(now * 2.2)) - eh // 2
        frame.paste(e, ((W - ew) // 2, ey), e)
        # titular + insignia (deslizan desde abajo al entrar)
        a = min(1, local / 0.3)
        st = sc["static"]
        if a < 1:
            st = st.copy()
            st.putalpha(st.getchannel("A").point(lambda v: int(v * a)))
            frame.alpha_composite(st, (0, int(40 * (1 - a))))
        else:
            frame.alpha_composite(st)
        # subtítulos
        cap = next((c for c in sc["caps"] if c[0] <= now < c[1] + 0.12), None)
        if cap:
            draw_caption(frame, cap, now)
        # barra de progreso
        d = ImageDraw.Draw(frame)
        d.rectangle((0, 0, W, 14), fill=(0, 0, 0, 120))
        d.rectangle((0, 0, int(W * now / duration), 14), fill=(255, 225, 77))
        # destello en el cambio de escena
        if local < 0.12 and sc is not scenes[0]:
            fl = Image.new("RGBA", (W, H), (255, 255, 255, int(160 * (1 - local / 0.12))))
            frame.alpha_composite(fl)
        rgb = frame.convert("RGB")
        if cover is None and local > 1.0 and sc is scenes[0]:
            cover = rgb.copy()
        ff.stdin.write(rgb.tobytes())
        if fi % (FPS * 5) == 0:
            print(f"  {now:5.1f}/{duration:.1f} s")
    ff.stdin.close()
    ff.wait()
    if ff.returncode:
        sys.exit("ffmpeg falló")

    (cover or rgb).save(out_dir / "portada.png")
    yt = script.get("youtube", {})
    (out_dir / "youtube.txt").write_text(
        f"TÍTULO:\n{yt.get('title', '')}\n\nDESCRIPCIÓN:\n{yt.get('description', '')}\n\n"
        f"ETIQUETAS:\n{', '.join(yt.get('tags', []))}\n", encoding="utf-8")
    print(f"✔ Listo: {video_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        main(p)
