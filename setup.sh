#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Устаналивается виртуальное окружение"
python3 -m venv "$SCRIPT_DIR/.venv"
echo "Устанавливается pywayland и pycairo..."
"$SCRIPT_DIR/.venv/bin/pip" install --no-cache-dir pywayland pycairo

echo "Генерируется модуль layer-shell..."
"$SCRIPT_DIR/.venv/bin/python" -m pywayland.scanner \
  -i "$SCRIPT_DIR/kwin-dot-overlay/wlr-layer-shell-unstable-v1.xml" \
     /usr/share/wayland/wayland.xml \
     /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
  -o "$SCRIPT_DIR/_gen"

mkdir -p "$SCRIPT_DIR/.venv/lib/python3.14/site-packages/pywayland/protocol/wlr_layer_shell_unstable_v1"

cp "$SCRIPT_DIR/_gen/wlr_layer_shell_unstable_v1.py" "$SCRIPT_DIR/.venv/lib/python3.14/site-packages/pywayland/protocol/wlr_layer_shell_unstable_v1/"
cp "$SCRIPT_DIR/_gen/wayland.py" "$SCRIPT_DIR/.venv/lib/python3.14/site-packages/pywayland/protocol/wlr_layer_shell_unstable_v1/"
cp "$SCRIPT_DIR/_gen/xdg_shell.py" "$SCRIPT_DIR/.venv/lib/python3.14/site-packages/pywayland/protocol/wlr_layer_shell_unstable_v1/"

echo "# Auto" > "$SCRIPT_DIR/.venv/lib/python3.14/site-packages/pywayland/protocol/wlr_layer_shell_unstable_v1/__init__.py"

rm -rf "$SCRIPT_DIR/_gen"


cat > "$SCRIPT_DIR/.venv/lib/python3.14/site-packages/pywayland/protocol/wlr_layer_shell_unstable_v1/__init__.py" << 'EOF'
from .wlr_layer_shell_unstable_v1 import ZwlrLayerShellV1, ZwlrLayerSurfaceV1
EOF

echo "Запуск:"
echo "  $SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/dot_overlay_native.py"
