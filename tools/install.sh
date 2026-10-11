#!/usr/bin/env bash
# Install the `jambox` command into ~/.local/share/jambox/venv and link it to ~/.local/bin,
# and install the udev rule (needs sudo once).
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
venv=$HOME/.local/share/jambox/venv

python3 -m venv "$venv"
"$venv/bin/pip" install --quiet --upgrade pip
"$venv/bin/pip" install --quiet "$repo"
mkdir -p "$HOME/.local/bin"
ln -sf "$venv/bin/jambox" "$HOME/.local/bin/jambox"
echo "installed: $HOME/.local/bin/jambox"

rule=/etc/udev/rules.d/70-jawbone.rules
if ! cmp -s "$repo/tools/udev/70-jawbone.rules" "$rule" 2>/dev/null; then
  echo "installing udev rule (sudo):"
  sudo cp "$repo/tools/udev/70-jawbone.rules" "$rule"
  sudo udevadm control --reload
fi
id -nG | grep -qw plugdev || echo "note: add yourself to group plugdev: sudo usermod -aG plugdev $USER"
echo "done. Try: jambox --help"
