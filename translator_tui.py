#!/usr/bin/env python3
"""
Omarchy Translator TUI — Minimal floating translator.
EN ↔ ES ↔ PT. Translation, phonetics, pronunciation, speech practice, LLM context.
"""

import difflib
import os
import tempfile
import subprocess

from rich.console import Console
from rich.prompt import Prompt

from deep_translator import GoogleTranslator
from gtts import gTTS

console = Console()

LANGUAGES = {"en": "English", "es": "Español", "pt": "Portugués"}
FLAGS = {"en": "EN", "es": "ES", "pt": "PT"}

CONFIG_PATH = os.path.expanduser("~/.config/translator/config.json")

# Lazy-loaded
_whisper_model = None
_llm_config = None  # {api_key, base_url, model} or None


def _load_llm_config() -> dict | None:
    """Load LLM config from ~/.config/translator/config.json."""
    try:
        import json
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        if cfg.get("api_key"):
            return cfg
    except Exception:
        pass
    return None


def ask_llm(word: str, translation: str, src: str, tgt: str) -> str:
    """Ask LLM for context and usage examples. Return response text."""
    global _llm_config
    if _llm_config is None:
        _llm_config = _load_llm_config()
    if _llm_config is None or not _llm_config.get("api_key"):
        return ""

    import json
    import urllib.request

    src_name = LANGUAGES.get(src, src)
    tgt_name = LANGUAGES.get(tgt, tgt)

    system = "Sos un asistente de idiomas. Respondé en español. Máximo 5 líneas. Sin markdown. Sin numeración."
    user = (
        f'"{word}" ({src_name}) → "{translation}" ({tgt_name}).\n'
        f"Contextos de uso, 2 ejemplos cortos con traducción, sinónimo y si es formal/informal."
    )

    body = json.dumps({
        "model": _llm_config["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 300,
        "temperature": 0.3,
    }).encode()

    url = _llm_config["base_url"].rstrip("/") + "/chat/completions"
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_llm_config['api_key']}",
        "User-Agent": "opencode/1.0",
    })

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning_content") or ""
    except Exception as e:
        return f"Error: {e}"


# ── Whisper ───────────────────────────────────────────────────
def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        console.print("  [dim]cargando modelo de voz...[/dim]")
        _whisper_model = WhisperModel("tiny", compute_type="int8")
    return _whisper_model


# ── Phonetics ─────────────────────────────────────────────────
def get_phonetics(word: str, lang_code: str) -> str:
    voice_map = {"en": "en-us", "es": "es", "pt": "pt"}
    voice = voice_map.get(lang_code, "en-us")
    try:
        r = subprocess.run(
            ["espeak-ng", "-x", "-v", voice, "--phonout=/dev/stdout", word],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or ""
    except (FileNotFoundError, Exception):
        return ""


# ── Audio playback ────────────────────────────────────────────
def play_pronunciation(text: str, lang_code: str):
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            gTTS(text=text, lang=lang_code, slow=False).save(f.name)
            subprocess.run(["mpv", "--no-video", "--really-quiet", f.name], timeout=15)
            os.unlink(f.name)
    except Exception as e:
        console.print(f"  ✗ {e}", style="dim red")


# ── Speech recording ─────────────────────────────────────────
def record_audio() -> str:
    """Record from mic until user presses Enter."""
    path = tempfile.mktemp(suffix=".wav")
    try:
        proc = subprocess.Popen(
            ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        console.print("  [dim red]arecord no encontrado. Instalá alsa-utils[/dim red]")
        return ""

    input()
    proc.terminate()
    proc.wait(timeout=2)

    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        try:
            os.unlink(path)
        except OSError:
            pass
        return ""
    return path


def transcribe_audio(path: str, lang: str) -> str:
    model = get_whisper_model()
    lang_map = {"en": "en", "es": "es", "pt": "pt"}
    segments, _ = model.transcribe(path, language=lang_map.get(lang, "en"))
    return " ".join(s.text for s in segments).strip()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def practice_pronunciation(expected: str, lang: str):
    console.print(f"  [dim]Decí: [bold]{expected}[/bold]  —  Enter para parar[/dim]")
    path = record_audio()
    if not path:
        console.print("  [dim red]No se detectó audio[/dim red]")
        return
    try:
        spoken = transcribe_audio(path, lang)
    except Exception as e:
        console.print(f"  [dim red]Error: {e}[/dim red]")
        return
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    if not spoken:
        console.print("  [dim red]No se entendió nada[/dim red]")
        return

    pct = int(similarity(spoken, expected) * 100)
    if pct >= 90:
        label = "[bold green]✓ Excelente[/bold green]"
    elif pct >= 70:
        label = "[bold yellow]≈ Bien[/bold yellow]"
    elif pct >= 50:
        label = "[bold yellow]~ Más o menos[/bold yellow]"
    else:
        label = "[bold red]✗ Intentá de nuevo[/bold red]"

    console.print(f"  Dijiste:  [dim]{spoken}[/dim]")
    console.print(f"  Esperado: [dim]{expected}[/dim]")
    console.print(f"  {label}  [dim]{pct}%[/dim]")


# ── Translation ───────────────────────────────────────────────
def translate(text: str, src: str, tgt: str) -> dict:
    res = {"translation": "", "phonetic": "", "alt": ""}
    try:
        translated = GoogleTranslator(source=src, target=tgt).translate(text) or ""
        res["translation"] = translated
        words = translated.split()
        if len(words) <= 3:
            res["phonetic"] = get_phonetics(translated, tgt)
        if len(text.split()) == 1:
            back = GoogleTranslator(source=tgt, target=src).translate(translated)
            if back and back.lower() != text.lower():
                res["alt"] = f"también: {back}"
    except Exception as e:
        res["translation"] = f"Error: {e}"
    return res


# ── Main ──────────────────────────────────────────────────────
def main():
    subprocess.run(["clear"], check=False)

    # Detect LLM on startup
    global _llm_config
    _llm_config = _load_llm_config()
    llm_tag = " · c contexto" if _llm_config else ""

    src, tgt = "en", "es"
    last = None
    last_original = None

    hint = f"  [dim]x swap · o origen · l destino · p escuchar · s hablar{llm_tag} · q salir[/dim]"

    while True:
        console.print(hint)
        try:
            text = Prompt.ask(
                f"  [dim]{FLAGS[src]} → {FLAGS[tgt]}[/dim]",
                console=console,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not text:
            continue
        t = text.lower()

        if t in ("q", "quit", "salir"):
            break
        elif t == "x":
            src, tgt = tgt, src
            continue
        elif t == "o":
            console.print("  [dim]en | es | pt[/dim]")
            c = Prompt.ask("  origen", default=src, console=console).strip().lower()
            if c in LANGUAGES:
                src = c
            continue
        elif t == "l":
            console.print("  [dim]en | es | pt[/dim]")
            c = Prompt.ask("  destino", default=tgt, console=console).strip().lower()
            if c in LANGUAGES:
                tgt = c
            continue
        elif t == "p":
            if last:
                play_pronunciation(last["translation"], tgt)
            continue
        elif t == "s":
            if last:
                practice_pronunciation(last["translation"], tgt)
            continue
        elif t == "c":
            if last and _llm_config:
                with console.status(""):
                    try:
                        ctx = ask_llm(last_original, last["translation"], src, tgt)
                        if ctx:
                            for line in ctx.strip().split("\n"):
                                line = line.strip()
                                if line:
                                    console.print(f"  {line}")
                        else:
                            console.print("  [dim red]Sin respuesta[/dim red]")
                    except Exception as e:
                        console.print(f"  [dim red]Error: {e}[/dim red]")
            elif not _llm_config:
                console.print("  [dim]Configurá ~/.config/translator/config.json[/dim]")
            continue

        # translate
        with console.status(""):
            r = translate(text, src, tgt)
            last = r
            last_original = text

        # output
        console.print(f"  [bold white]{r['translation']}[/bold white]")
        if r["phonetic"]:
            console.print(f"  [dim]/{r['phonetic']}/[/dim]")
        if r["alt"]:
            console.print(f"  [dim]{r['alt']}[/dim]")

        # sub-loop
        while True:
            try:
                a = Prompt.ask("  ", console=console, default="").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if a == "p":
                play_pronunciation(r["translation"], tgt)
            elif a == "s":
                practice_pronunciation(r["translation"], tgt)
            elif a == "c" and _llm_config:
                with console.status(""):
                    try:
                        ctx = ask_llm(last_original, r["translation"], src, tgt)
                        if ctx:
                            for line in ctx.strip().split("\n"):
                                line = line.strip()
                                if line:
                                    console.print(f"  {line}")
                    except Exception as e:
                        console.print(f"  [dim red]Error: {e}[/dim red]")
            elif a == "x":
                src, tgt = tgt, src
                break
            elif a in ("o", "l", "n", ""):
                if a == "o":
                    console.print("  [dim]en | es | pt[/dim]")
                    c = Prompt.ask("  origen", default=src, console=console).strip().lower()
                    if c in LANGUAGES:
                        src = c
                elif a == "l":
                    console.print("  [dim]en | es | pt[/dim]")
                    c = Prompt.ask("  destino", default=tgt, console=console).strip().lower()
                    if c in LANGUAGES:
                        tgt = c
                break
            elif a in ("q", "quit", "salir"):
                return


if __name__ == "__main__":
    main()
