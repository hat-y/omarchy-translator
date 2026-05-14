#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/translator"
BIN_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/translator"

echo "Installing omarchy-translator..."

# Create venv and install deps
python3 -m venv "$INSTALL_DIR"
"$INSTALL_DIR/bin/pip" install --quiet deep-translator gTTS rich faster-whisper

# Copy script
cp translator_tui.py "$INSTALL_DIR/translator_tui.py"

# Copy launcher
cp omarchy-translator "$BIN_DIR/omarchy-translator"
chmod +x "$BIN_DIR/omarchy-translator"

# Config
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.json" ]; then
	cp config.example.json "$CONFIG_DIR/config.json"
	chmod 600 "$CONFIG_DIR/config.json"
	echo ""
	echo "  Config created at $CONFIG_DIR/config.json"
	echo "  Edit it with your API key and preferred model."
else
	echo "  Config already exists at $CONFIG_DIR/config.json (not overwritten)"
fi

# Hyprland keybinding
BINDINGS="${HOME}/.config/hypr/bindings.lua"
if [ -f "$BINDINGS" ] && ! grep -q "omarchy-translator" "$BINDINGS"; then
	echo "" >>"$BINDINGS"
	echo "-- Translator popup (floating Alacritty)." >>"$BINDINGS"
	echo 'hl.bind("SUPER + Z", hl.dsp.exec_cmd("omarchy-translator"), { description = "Translator" })' >>"$BINDINGS"
	echo "  Added SUPER+Z keybinding to $BINDINGS"
else
	echo "  Keybinding already exists or bindings.lua not found"
fi

# Hyprland window rules
HYPRLAND="${HOME}/.config/hypr/hyprland.lua"
if [ -f "$HYPRLAND" ] && ! grep -q "com.alacritty.translator" "$HYPRLAND"; then
	# Insert before the last line
	sed -i '/^-- Add any other personal/i\
-- Translator popup: small floating centered window.\
hl.window_rule({ match = { class = "com.alacritty.translator" }, float = true })\
hl.window_rule({ match = { class = "com.alacritty.translator" }, center = true })\
hl.window_rule({ match = { class = "com.alacritty.translator" }, size = "72ch 24ch" })\
hl.window_rule({ match = { class = "com.alacritty.translator" }, pin = true })\
hl.window_rule({ match = { class = "com.alacritty.translator" }, animation = "popin 80" })\
' "$HYPRLAND"
	echo "  Added window rules to $HYPRLAND"
fi

echo ""
echo "Done! Press SUPER+Z to open the translator."
echo ""
echo "Optional: install espeak-ng for IPA phonetics:"
echo "  sudo pacman -S espeak-ng"
