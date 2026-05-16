#!/usr/bin/env python3
"""
Omarchy Translator TUI — Bottom-input layout.
EN ↔ ES ↔ PT. Translation, phonetics, pronunciation, speech practice, LLM context.

Layout:
  - History area (top, FIFO, wraps long lines)
  - Shortcuts bar + separator (just above input)
  - Input prompt (always at bottom-left)
"""

import difflib
import os
import tempfile
import subprocess
import json
import urllib.request
from typing import Optional

from rich.console import Console
from deep_translator import GoogleTranslator
from gtts import gTTS

console = Console()

LANGUAGES = {"en": "English", "es": "Español", "pt": "Portugués"}
FLAGS = {"en": "EN", "es": "ES", "pt": "PT"}
CONFIG_PATH = os.path.expanduser("~/.config/translator/config.json")

# Lazy-loaded globals
_whisper_model = None
_llm_config: Optional[dict] = None

# ── Session history ───────────────────────────────────────────
# Each entry: {src, tgt, original, translation, phonetic, alt}
history: list[dict] = []


# ── LLM context ───────────────────────────────────────────────
def _load_llm_config() -> Optional[dict]:
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        if cfg.get("api_key"):
            return cfg
    except Exception:
        pass
    return None


def ask_llm(word: str, translation: str, src: str, tgt: str) -> str:
    """Ask LLM for context / examples via OpenAI-compatible API."""
    global _llm_config
    if _llm_config is None:
        _llm_config = _load_llm_config()
    if _llm_config is None or not _llm_config.get("api_key"):
        return ""

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
        console.print(f"  ✗ {e}")


# ── Speech recording & practice ───────────────────────────────
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


# ── Display helpers ───────────────────────────────────────────
def entry_lines(entry: dict, width: int) -> list[str]:
    """Format one history entry as list of Rich-renderable strings."""
    src_f = FLAGS.get(entry["src"], entry["src"].upper())
    tgt_f = FLAGS.get(entry["tgt"], entry["tgt"].upper())
    sep = "─" * (width - 4)
    lines = [
        f"  [{src_f}→{tgt_f}]  {entry['original']}",
        f"  {sep}",
        f"  [bold white]{entry['translation']}[/bold white]",
    ]
    if entry.get("phonetic"):
        lines.append(f"  [dim]/{entry['phonetic']}/[/dim]")
    if entry.get("alt"):
        lines.append(f"  [dim]{entry['alt']}[/dim]")
    lines.append("")
    return lines


def estimate_lines(text: str, width: int) -> int:
    """Rough terminal lines a string will take when printed (Rich wraps)."""
    if not text:
        return 0
    # Strip markup tags for length estimation
    plain = text
    for tag in ("[bold white]", "[bold green]", "[bold yellow]", "[bold red]",
                "[/bold]", "[dim]", "[/dim]", "[dim red]", "[/dim red]"):
        plain = plain.replace(tag, "")
    return max(1, (len(plain) + width - 1) // width)


def entry_line_count(entry: dict, width: int) -> int:
    """Estimated total terminal lines for one entry."""
    total = 0
    for line in entry_lines(entry, width):
        total += estimate_lines(line, width)
    return total


# ── Main ──────────────────────────────────────────────────────
def main():
    subprocess.run(["clear"], check=False)

    global _llm_config
    _llm_config = _load_llm_config()
    context_mode = bool(_llm_config)

    src, tgt = "en", "es"
    last_result = None
    last_original = None

    shortcut_items = [
        ("p", "play"),
        ("s", "speak"),
    ]
    if context_mode:
        shortcut_items.append(("c", "context"))
    shortcut_items += [
        ("x", "swap"),
        ("o", "src"),
        ("l", "dst"),
        ("q", "quit"),
    ]
    shortcuts_text = " · ".join(f"{k} {v}" for k, v in shortcut_items)

    while True:
        # ── Sizing ────────────────────────────────────────────
        w = console.width - 2 if console.width > 10 else 56
        reserved = 3  # shortcuts + separator + input
        available = console.height - reserved

        # ── Build visible entries (FIFO, newest at bottom) ────
        visible: list[list[str]] = []   # entry line-groups, top-to-bottom
        used = 0

        for entry in reversed(history):
            cnt = entry_line_count(entry, w)
            if used + cnt > available:
                break
            visible.insert(0, entry_lines(entry, w))
            used += cnt

        # ── Render ────────────────────────────────────────────
        console.clear()

        for group in visible:
            for line in group:
                console.print(line)

        for _ in range(available - used):
            console.print("")

        # Bottom area
        console.print(f"  [dim]{shortcuts_text}[/dim]")
        console.print(f"  {'─' * (w - 4)}")

        # ── Input ─────────────────────────────────────────────
        try:
            prompt = f"  [dim]{FLAGS[src]}→{FLAGS[tgt]}[/dim] > "
            text = console.input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not text:
            continue

        t = text.lower()

        # ── Command dispatch ──────────────────────────────────
        if t in ("q", "quit", "salir"):
            break

        elif t == "x":
            src, tgt = tgt, src
            continue

        elif t == "o":
            console.print("  [dim]en | es | pt[/dim]")
            try:
                c = console.input("  origen > ").strip().lower()
                if c in LANGUAGES:
                    src = c
            except (EOFError, KeyboardInterrupt):
                break
            continue

        elif t == "l":
            console.print("  [dim]en | es | pt[/dim]")
            try:
                c = console.input("  destino > ").strip().lower()
                if c in LANGUAGES:
                    tgt = c
            except (EOFError, KeyboardInterrupt):
                break
            continue

        elif t == "p":
            if last_result:
                play_pronunciation(last_result["translation"], tgt)
            continue

        elif t == "s":
            if last_result:
                practice_pronunciation(last_result["translation"], tgt)
            # Wait for user to see result before re-render
            if last_result:
                try:
                    console.input("  [dim]Enter para continuar...[/dim]")
                except (EOFError, KeyboardInterrupt):
                    break
            continue

        elif t == "c":
            if last_result and _llm_config:
                console.print("  [dim]Consultando...[/dim]")
                try:
                    ctx = ask_llm(last_original, last_result["translation"], src, tgt)
                    if ctx:
                        for line in ctx.strip().split("\n"):
                            line = line.strip()
                            if line:
                                console.print(f"  {line}")
                    else:
                        console.print("  [dim red]Sin respuesta[/dim red]")
                except Exception as e:
                    console.print(f"  [dim red]Error: {e}[/dim red]")
                try:
                    console.input("  [dim]Enter para continuar...[/dim]")
                except (EOFError, KeyboardInterrupt):
                    break
            elif not _llm_config:
                console.print("  [dim]Configurá ~/.config/translator/config.json[/dim]")
                try:
                    console.input("  [dim]Enter para continuar...[/dim]")
                except (EOFError, KeyboardInterrupt):
                    break
            continue

        # ── Translate ─────────────────────────────────────────
        r = translate(text, src, tgt)
        last_result = r
        last_original = text

        history.append({
            "src": src,
            "tgt": tgt,
            "original": text,
            "translation": r["translation"],
            "phonetic": r.get("phonetic", ""),
            "alt": r.get("alt", ""),
        })


if __name__ == "__main__":
    main()
