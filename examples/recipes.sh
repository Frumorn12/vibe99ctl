#!/usr/bin/env bash
# Example recipes for vibe99ctl. Runs in DRY-RUN unless you pass --apply through.
#
# Usage:
#   ./recipes.sh            # preview everything (no writes)
#   APPLY=--apply ./recipes.sh   # actually send to the keyboard (wired mode!)
set -euo pipefail

APPLY="${APPLY:-}"

echo "== device info =="
vibe99 info || true

echo "== list devices (all HID) =="
vibe99 list-devices --all || true

echo "== RGB: solid orange =="
vibe99 rgb set "#ff8800" --brightness 80 $APPLY

echo "== RGB: breathing blue, slow =="
vibe99 rgb preset breathing --color "0,128,255" --speed 30 $APPLY

echo "== RGB: rainbow =="
vibe99 rgb preset rainbow --speed 70 $APPLY

echo "== Clock: sync now =="
vibe99 clock sync $APPLY

# Screen examples need real files; uncomment and point them at your media.
# echo "== Screen: image =="
# vibe99 screen upload-image ./logo.png --fit cover $APPLY
# echo "== Screen: animation =="
# vibe99 screen upload-animation ./loading.gif --fps 5 $APPLY

echo "Done."
