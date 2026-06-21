# Examples

Copy-paste recipes for `vibe99ctl`.

> All write commands are **dry-run by default**. Add `--apply` to send to the
> keyboard. Connect it in **wired** mode first.

## Shell recipes

See [`recipes.sh`](recipes.sh) for a runnable script. Highlights:

```bash
# Solid color
vibe99 rgb set "#ff8800" --apply

# Effect with a base color, slower
vibe99 rgb preset breathing --color "0,128,255" --speed 30 --apply

# Image to the screen, cropped to fill
vibe99 screen upload-image logo.png --fit cover --apply

# A GIF, looping at ~5 fps
vibe99 screen upload-animation loading.gif --fps 5 --apply

# Convert a short video into an animation (downsampled, not streamed)
vibe99 screen upload-video clip.mp4 --max-frames 60 --apply

# Keep the on-screen clock correct
vibe99 clock sync --apply
```

## Keep the clock synced (cron)

```cron
# crontab -e  — sync every 6 hours
0 */6 * * * /path/to/.venv/bin/vibe99 clock sync --apply >/dev/null 2>&1
```

## Use it as a library

See [`library_usage.py`](library_usage.py): build packets and inspect the exact
bytes without any hardware (great for understanding the protocol model).
