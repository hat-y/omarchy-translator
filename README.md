# Omarchy Translator

Floating translator popup for Hyprland / Omarchy.

Press **SUPER+Z** — a small terminal appears. Type a word, get the translation, hear the pronunciation, practice your accent, ask an LLM for context. Press **Q** to close and the process dies.

Built for quick lookups while reading, coding, or writing in another language.

## Features

- **EN ↔ ES ↔ PT** — English, Spanish, Portuguese
- **Instant translation** via Google Translate
- **IPA phonetics** when `espeak-ng` is installed
- **Audio pronunciation** via gTTS + mpv
- **Speech practice** — record yourself, Whisper transcribes locally, shows accuracy %
- **LLM context** — ask about usage, examples, synonyms, formality (requires API key or Ollama)
- **Floating popup** — centered, pinned, animated, disappears when you quit

## Shortcuts

| Key | Action                                     |
| --- | ------------------------------------------ |
| `x` | Swap languages (EN→ES becomes ES→EN)       |
| `o` | Change source language                     |
| `l` | Change target language                     |
| `p` | Play pronunciation audio                   |
| `s` | Practice pronunciation (record your voice) |
| `c` | Ask LLM for context and examples           |
| `q` | Quit                                       |

Shortcuts are shown in a bar just above the input prompt.

## Install

```bash
git clone https://github.com/hat-y/omarchy-translator.git
cd omarchy-translator
chmod +x install.sh
./install.sh
```

The installer will:

1. Create a Python venv at `~/.local/share/translator`
2. Install dependencies (deep-translator, gTTS, rich, faster-whisper)
3. Copy the launcher to `~/.local/bin/omarchy-translator`
4. Add SUPER+Z keybinding to Hyprland
5. Add window rules for the floating popup

The launcher runs the script directly from the cloned repo, so future updates only need a `git pull`.

### Optional

```bash
# IPA phonetic transcriptions
sudo pacman -S espeak-ng
```

### LLM Context (`c` key)

The `c` shortcut lets you ask an LLM about the word you just translated — contexts of use, example sentences, synonyms, and formality notes.

**This feature requires either:**

- An **API key** from an OpenAI-compatible provider (DeepSeek, OpenRouter, OpenAI, OpenCode Go, etc.)
- **Ollama** running locally with a model loaded (not yet implemented — contributions welcome)

To set it up, edit `~/.config/translator/config.json`:

```json
{
  "api_key": "your-key-here",
  "base_url": "https://opencode.ai/zen/go/v1",
  "model": "kimi-k2.5"
}
```

Any **OpenAI-compatible API** works. Examples:

| Provider    | base_url                        | model                    |
| ----------- | ------------------------------- | ------------------------ |
| OpenCode Go | `https://opencode.ai/zen/go/v1` | `kimi-k2.5`              |
| DeepSeek    | `https://api.deepseek.com`      | `deepseek-chat`          |
| OpenRouter  | `https://openrouter.ai/api/v1`  | `deepseek/deepseek-chat` |
| OpenAI      | `https://api.openai.com/v1`     | `gpt-4o-mini`            |

If no API key is configured, the `c` option simply won't appear in the shortcuts bar.

## How It Works

- **SUPER+Z** launches Alacritty with a custom class (`com.alacritty.translator`)
- Hyprland window rules catch that class and make it float at the bottom-left corner, pinned
- The Python TUI uses a **bottom-input layout**: history scrolls FIFO above, shortcuts bar + separator sit just above the input prompt
- Pressing `q` or Ctrl+C kills the process and the window disappears

## Requirements

- Arch Linux / Omarchy with Hyprland
- Alacritty
- mpv (audio playback)
- Python 3.12+
- arecord (from alsa-utils, for speech recording)

## License

MIT
