"""Vibe99 gallery: browse GIFs/videos, preview them as the screen will, upload.

Run with ``vibe99 gui`` (or ``vibe99-gui``). Needs PyQt6 (``pip install
'vibe99ctl[gui]'`` or the distro package, e.g. ``python-pyqt6`` on Arch).

Two tabs feed one preview panel: the *Libreria* (files in
``~/.local/share/vibe99/libreria``) and the *Store* (Tenor search). The preview
shows the exact frames that will be uploaded (decoded back from RGB565), and
"Metti sulla tastiera" uploads them with a progress bar. Grid thumbnails only
animate under the mouse, to keep the CPU (and the dGPU) idle.
"""

from __future__ import annotations

import functools
import math
import re
import subprocess
import sys
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QFileSystemWatcher,
    QIODevice,
    QObject,
    QRunnable,
    QSettings,
    Qt,
    QThreadPool,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QImage, QMovie, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import (
    CONTROL_USAGE_PAGE,
    DEFAULT_ANIMATION_FPS,
    DEFAULT_SCREEN,
    GIF_MAX_FRAMES,
    MAX_ANIMATION_FRAMES,
    SCREEN_REPORT_SIZE,
    UPLOAD_SECONDS_PER_CHUNK,
)
from ..device.discovery import enumerate_all, open_device
from ..media.animation import VIDEO_SUFFIXES, Clip, load_clip, video_frames_rgb
from ..protocol import clock as clock_proto
from ..protocol import rgb as rgb_proto
from ..protocol import screen as screen_proto
from ..runner import send_packets
from ..util.colors import parse_color
from . import store

SPEC = DEFAULT_SCREEN
ZOOM = 2  # the preview shows the 96x160 screen at 2x, nearest-neighbour
TILE = 150
SUGGESTIONS = [
    "pixel art",
    "pokemon pixel",
    "garganacl",
    "gatto pixel",
    "lofi",
    "anime",
    "spazio",
    "cyberpunk",
    "kirby",
    "fuoco",
]
FITS = [("Adatta (bande nere)", "contain"), ("Riempi (ritaglia)", "cover"), ("Stira", "stretch")]
E = rgb_proto.RgbEffect
EFFECT_LABELS = {
    E.OFF: "Spente",
    E.STATIC: "Fisso",
    E.SINGLE_ON: "Si accende al tocco",
    E.SINGLE_OFF: "Si spegne al tocco",
    E.GLITTERING: "Scintillio",
    E.FALLING: "Pioggia",
    E.COLOURFUL: "Multicolore",
    E.BREATH: "Respiro",
    E.SPECTRUM: "Spettro",
    E.OUTWARD: "Dal centro",
    E.SCROLLING: "Scorrimento",
    E.ROLLING: "Onda (fabbrica)",
    E.ROTATING: "Rotazione",
    E.EXPLODE: "Esplosione",
    E.LAUNCH: "Lancio",
    E.RIPPLES: "Increspature",
    E.FLOWING: "Flusso",
    E.PULSATING: "Pulsazione",
    E.TILT: "Inclinazione",
    E.SHUTTLE: "Navetta",
}
SWATCHES = [
    ("#ff0000", "Rosso"),
    ("#ff6a00", "Arancione"),
    ("#ffd000", "Giallo"),
    ("#00ff40", "Verde"),
    ("#00e5ff", "Azzurro"),
    ("#0040ff", "Blu"),
    ("#8a2be2", "Viola"),
    ("#ff3fb4", "Rosa"),
    ("#ffffff", "Bianco"),
]

THEME_FILES = [
    Path.home() / ".local/state/omarchy/current/theme/colors.toml",
    Path.home() / ".config/omarchy/current/theme/colors.toml",
]
# Tokyo Night, used when no Omarchy theme is found.
DEFAULT_COLORS = {
    "background": "#1a1b26",
    "lighter_background": "#24283b",
    "selection": "#292e42",
    "muted": "#414868",
    "foreground": "#a9b1d6",
    "bright_foreground": "#c0caf5",
    "dark_foreground": "#565f89",
    "accent": "#7aa2f7",
    "red": "#f7768e",
    "green": "#9ece6a",
}


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
def load_colors() -> dict[str, str]:
    colors = dict(DEFAULT_COLORS)
    for f in THEME_FILES:
        try:
            text = f.read_text()
        except OSError:
            continue
        # colors.toml is flat `key = "#rrggbb"` lines; no TOML parser needed (py3.10).
        colors.update(re.findall(r'^\s*(\w+)\s*=\s*"(#[0-9a-fA-F]{6})"', text, re.M))
        break
    return colors


def stylesheet(c: dict[str, str]) -> str:
    return f"""
    QWidget {{ background: {c["background"]}; color: {c["foreground"]}; font-size: 10pt; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ background: transparent; color: {c["dark_foreground"]};
        padding: 8px 18px; border-bottom: 2px solid transparent; font-weight: 600; }}
    QTabBar::tab:selected {{ color: {c["bright_foreground"]}; border-bottom-color: {c["accent"]}; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: {c["background"]}; }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {c["lighter_background"]};
        border: 1px solid {c["muted"]}; border-radius: 6px; padding: 5px 8px; }}
    QLineEdit:focus {{ border-color: {c["accent"]}; }}
    QPushButton {{ background: {c["lighter_background"]}; border: 1px solid {c["muted"]};
        border-radius: 6px; padding: 6px 12px; }}
    QPushButton:hover {{ border-color: {c["accent"]}; }}
    QPushButton:disabled {{ color: {c["dark_foreground"]}; border-color: {c["selection"]}; }}
    QPushButton#primary {{ background: {c["accent"]}; color: {c["background"]};
        border: none; font-weight: 700; padding: 9px 12px; }}
    QPushButton#primary:disabled {{ background: {c["muted"]}; color: {c["dark_foreground"]}; }}
    QPushButton#chip {{ border-radius: 12px; padding: 3px 10px; font-size: 9pt; }}
    QPushButton#effect {{ padding: 9px 10px; }}
    QPushButton#effect:checked {{ background: {c["selection"]}; border: 2px solid {c["accent"]};
        color: {c["bright_foreground"]}; font-weight: 700; }}
    QPushButton#swatch {{ border: 2px solid {c["muted"]}; border-radius: 17px; padding: 0; }}
    QPushButton#swatch:checked {{ border: 3px solid {c["bright_foreground"]}; }}
    QPushButton#swatch:disabled {{ border-color: {c["selection"]}; }}
    QTabWidget#pages > QTabBar::tab {{ font-size: 11pt; padding: 10px 26px; }}
    QSlider::groove:horizontal {{ height: 6px; background: {c["lighter_background"]};
        border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {c["accent"]}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {c["bright_foreground"]}; width: 16px;
        margin: -6px 0; border-radius: 8px; }}
    QSlider:disabled, QLabel:disabled {{ color: {c["dark_foreground"]}; }}
    QSlider::sub-page:horizontal:disabled {{ background: {c["muted"]}; }}
    QFrame#tile {{ background: {c["lighter_background"]}; border: 2px solid transparent;
        border-radius: 10px; }}
    QFrame#tile:hover {{ border-color: {c["muted"]}; }}
    QFrame#tile[selected="true"] {{ border-color: {c["accent"]}; }}
    QLabel#screen {{ background: #000; border: 6px solid {c["selection"]}; border-radius: 10px; }}
    QLabel#title {{ color: {c["bright_foreground"]}; font-size: 12pt; font-weight: 700; }}
    QLabel#dim {{ color: {c["dark_foreground"]}; }}
    QProgressBar {{ background: {c["lighter_background"]}; border: none; border-radius: 4px;
        height: 8px; text-align: center; color: transparent; }}
    QProgressBar::chunk {{ background: {c["accent"]}; border-radius: 4px; }}
    """


# --------------------------------------------------------------------------- #
# Background work
# --------------------------------------------------------------------------- #
class _Signals(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)


class Task(QRunnable):
    """Run ``fn`` on the thread pool; results come back as Qt signals."""

    def __init__(self, fn: Callable, *args, with_progress: bool = False):
        super().__init__()
        self.fn, self.args, self.with_progress = fn, args, with_progress
        self.signals = _Signals()

    def run(self) -> None:
        try:
            if self.with_progress:
                result = self.fn(*self.args, progress=self.signals.progress.emit)
            else:
                result = self.fn(*self.args)
        except Exception as exc:  # shown in the status line
            traceback.print_exc()
            self.signals.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.signals.done.emit(result)


def frame_image(buf: bytes) -> QImage:
    """A device frame (RGB565 LE) as a QImage: exactly what the screen shows."""
    return QImage(buf, SPEC.width, SPEC.height, SPEC.width * 2, QImage.Format.Format_RGB16).copy()


def upload_estimate(frames: int) -> str:
    chunks = math.ceil((256 + frames * SPEC.frame_bytes) / SCREEN_REPORT_SIZE)
    secs = round(chunks * UPLOAD_SECONDS_PER_CHUNK)
    return f"{secs // 60} min {secs % 60} s" if secs >= 60 else f"{secs} s"


def keyboard_connected() -> bool:
    return any(
        d.usage_page == CONTROL_USAGE_PAGE and "Vibe99" in d.product for d in enumerate_all()
    )


def send_to_keyboard(packets: list, progress: Callable[[int, int], None] | None = None) -> int:
    """Send packets to the wired keyboard; returns the number of missing screen ACKs."""
    device, transport = open_device()
    if "Vibe99" not in device.product or device.usage_page != CONTROL_USAGE_PAGE:
        transport.close()
        raise RuntimeError("Collega la tastiera con il cavo USB-C (in 2.4G non si configura).")
    try:
        result = send_packets(transport, packets, progress=progress)
    finally:
        transport.close()
    return result.missing_acks


def do_upload(clip: Clip, progress: Callable[[int, int], None]) -> int:
    packets = screen_proto.upload_animation(clip.frames, spec=SPEC, delays_ms=clip.delays_ms)
    return send_to_keyboard(packets, progress)


def video_thumbnail(path: Path) -> QImage:
    try:
        img = video_frames_rgb(path, spec=SPEC, fit="cover", fps=1, max_frames=1, start=1.0)[0]
    except Exception:
        img = video_frames_rgb(path, spec=SPEC, fit="cover", fps=1, max_frames=1)[0]
    data = img.tobytes()
    return QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888).copy()


# --------------------------------------------------------------------------- #
# Grid of thumbnails
# --------------------------------------------------------------------------- #
class Tile(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, key: object, caption: str):
        super().__init__()
        self.key = key
        self.setObjectName("tile")
        self.setFixedSize(TILE, TILE + 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(2)
        self.image = QLabel("…")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setFixedSize(TILE - 12, TILE - 12)
        self.image.setStyleSheet("background: transparent;")
        self.caption = QLabel()
        self.caption.setObjectName("dim")
        self.caption.setStyleSheet("background: transparent; font-size: 8pt;")
        metrics = self.caption.fontMetrics()
        self.caption.setText(metrics.elidedText(caption, Qt.TextElideMode.ElideRight, TILE - 14))
        self.caption.setToolTip(caption)
        lay.addWidget(self.image)
        lay.addWidget(self.caption)
        self.movie: QMovie | None = None
        self._buffer: QBuffer | None = None

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def _fit_movie(self) -> None:
        size = self.movie.currentImage().size()
        if size.isValid() and not size.isEmpty():
            self.movie.setScaledSize(
                size.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio)
            )

    def set_movie_file(self, path: Path) -> None:
        self._start_movie(QMovie(str(path)))

    def set_movie_bytes(self, data: bytes) -> None:
        self._buffer = QBuffer()
        self._buffer.setData(QByteArray(data))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        movie = QMovie()
        movie.setDevice(self._buffer)
        self._start_movie(movie)

    def _start_movie(self, movie: QMovie) -> None:
        self.movie = movie
        if not movie.jumpToFrame(0):
            self.image.setText("✕")
            return
        self._fit_movie()
        self.image.setMovie(movie)
        movie.jumpToFrame(0)

    def set_image(self, img: QImage) -> None:
        pix = QPixmap.fromImage(img).scaled(
            self.image.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image.setPixmap(pix)

    def enterEvent(self, event) -> None:
        if self.movie is not None:
            self.movie.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.movie is not None:
            self.movie.stop()
            self.movie.jumpToFrame(0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.key)


class TileGrid(QScrollArea):
    """A scrollable, reflowing grid of tiles."""

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._inner = QWidget()
        self._grid = QGridLayout(self._inner)
        self._grid.setSpacing(10)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self._inner)
        self.tiles: list[Tile] = []
        self._cols = 0

    def clear(self) -> None:
        for t in self.tiles:
            t.setParent(None)
            t.deleteLater()
        self.tiles = []
        self._cols = 0

    def add(self, tile: Tile) -> None:
        self.tiles.append(tile)
        self._reflow(force=True)

    def _reflow(self, force: bool = False) -> None:
        cols = max(1, (self.viewport().width() - 10) // (TILE + 10))
        if cols == self._cols and not force:
            return
        self._cols = cols
        for i, t in enumerate(self.tiles):
            self._grid.addWidget(t, i // cols, i % cols)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def select(self, key: object) -> None:
        for t in self.tiles:
            t.set_selected(t.key == key)


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
class Gallery(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vibe99")
        self.resize(1080, 720)
        self.pool = QThreadPool.globalInstance()
        self._tasks: set[Task] = set()  # keep running tasks alive
        self.source: Path | None = None  # file being previewed
        self.store_item: store.StoreItem | None = None  # set when it comes from the store
        self.clip: Clip | None = None
        self.preview_frames: list[QPixmap] = []
        self.preview_index = 0
        self.convert_token = 0
        self.uploading = False
        self.busy = False  # one keyboard operation at a time (upload, lights, clock)
        self.lights_pending = False
        self.was_connected = False
        self.settings = QSettings("vibe99", "vibe99")

        self.pages = QTabWidget()
        self.pages.setObjectName("pages")
        self.pages.addTab(self._build_screen_page(), "Schermo")
        self.pages.addTab(self._build_lights_page(), "Luci")
        self.pages.addTab(self._build_keyboard_page(), "Tastiera")
        self.setCentralWidget(self.pages)

        self.anim_timer = QTimer(self)
        self.anim_timer.setSingleShot(True)
        self.anim_timer.timeout.connect(self._next_preview_frame)
        self.convert_timer = QTimer(self)
        self.convert_timer.setSingleShot(True)
        self.convert_timer.setInterval(350)
        self.convert_timer.timeout.connect(self._convert)
        self.device_timer = QTimer(self)
        self.device_timer.timeout.connect(self._refresh_device)
        self.device_timer.start(3000)

        self._apply_theme()
        self._watch_theme()
        self._refresh_device()
        self.refresh_library()
        if not self.library.tiles:
            self.tabs.setCurrentIndex(1)
        self.search(SUGGESTIONS[0])

    # ----- helpers ---------------------------------------------------------
    def run(self, task: Task, done=None, failed=None, progress=None) -> Task:
        self._tasks.add(task)
        if done:
            task.signals.done.connect(done)
        task.signals.failed.connect(failed or self._show_error)
        if progress:
            task.signals.progress.connect(progress)
        task.signals.done.connect(lambda _=None, t=task: self._tasks.discard(t))
        task.signals.failed.connect(lambda _=None, t=task: self._tasks.discard(t))
        self.pool.start(task)
        return task

    def _show_error(self, message: str) -> None:
        self.status.setText(f"⚠ {message}")

    def device_op(
        self,
        packets: list,
        status: QLabel,
        doing: str,
        done_text: str,
        after: Callable[[], None] | None = None,
    ) -> bool:
        """Send a short command sequence (lights, clock) unless the keyboard is busy."""
        if self.busy:
            status.setText("Attendi: la tastiera sta già ricevendo dati…")
            return False
        self.busy = True
        status.setText(doing)

        def finish(text: str) -> None:
            self.busy = False
            status.setText(text)
            if after is not None:
                after()

        self.run(
            Task(send_to_keyboard, packets),
            done=lambda _: finish(done_text),
            failed=lambda msg: finish(f"⚠ {msg}"),
        )
        return True

    def _build_screen_page(self) -> QWidget:
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(14, 6, 14, 14)
        lay.setSpacing(16)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_library(), "Libreria")
        self.tabs.addTab(self._build_store(), "Store")
        lay.addWidget(self.tabs, 1)
        lay.addWidget(self._build_preview())
        return page

    # ----- lights tab ------------------------------------------------------
    def _build_lights_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)

        head = QLabel("Effetto")
        head.setObjectName("title")
        lay.addWidget(head)
        grid = QGridLayout()
        grid.setSpacing(8)
        self.effect_group = QButtonGroup(self)
        self.effect_group.setExclusive(True)
        for i, effect in enumerate(rgb_proto.RgbEffect):
            b = QPushButton(EFFECT_LABELS[effect])
            b.setObjectName("effect")
            b.setCheckable(True)
            b.setToolTip(rgb_proto.EFFECTS[effect].name)
            self.effect_group.addButton(b, int(effect))
            grid.addWidget(b, i // 5, i % 5)
        self.effect_group.idClicked.connect(lambda _: self._lights_changed())
        lay.addLayout(grid)

        color_head = QLabel("Colore")
        color_head.setObjectName("title")
        lay.addWidget(color_head)
        colors = QHBoxLayout()
        colors.setSpacing(8)
        self.rainbow_btn = QPushButton("🌈 Arcobaleno")
        self.rainbow_btn.setObjectName("effect")
        self.rainbow_btn.setCheckable(True)
        self.rainbow_btn.clicked.connect(lambda: self._pick_color(None))
        colors.addWidget(self.rainbow_btn)
        self.swatches: list[QPushButton] = []
        for hex_color, name in SWATCHES:
            s = QPushButton()
            s.setObjectName("swatch")
            s.setCheckable(True)
            s.setToolTip(name)
            s.setFixedSize(34, 34)
            s.setStyleSheet(f"QPushButton#swatch {{ background: {hex_color}; }}")
            s.clicked.connect(lambda _=False, c=hex_color: self._pick_color(c))
            self.swatches.append(s)
            colors.addWidget(s)
        more = QPushButton("Altro colore…")
        more.clicked.connect(self._custom_color)
        colors.addWidget(more)
        self.color_chip = QLabel()
        self.color_chip.setFixedSize(34, 34)
        colors.addWidget(self.color_chip)
        colors.addStretch()
        lay.addLayout(colors)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, rgb_proto.BRIGHTNESS_MAX)
        self.brightness.setPageStep(1)
        self.brightness.valueChanged.connect(lambda _: self._lights_changed())
        form.addRow("Luminosità", self._with_value(self.brightness))
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(0, rgb_proto.SPEED_MAX)
        self.speed.setPageStep(1)
        self.speed.valueChanged.connect(lambda _: self._lights_changed())
        self.speed_label = QLabel("Velocità")
        form.addRow(self.speed_label, self._with_value(self.speed))
        dirs = QHBoxLayout()
        self.dir_group = QButtonGroup(self)
        for i, text in enumerate(("→  Avanti", "←  Indietro")):
            b = QPushButton(text)
            b.setObjectName("effect")
            b.setCheckable(True)
            self.dir_group.addButton(b, i)
            dirs.addWidget(b)
        dirs.addStretch()
        self.dir_group.idClicked.connect(lambda _: self._lights_changed())
        self.dir_label = QLabel("Direzione")
        self.dir_box = QWidget()
        self.dir_box.setLayout(dirs)
        dirs.setContentsMargins(0, 0, 0, 0)
        form.addRow(self.dir_label, self.dir_box)
        lay.addLayout(form)

        bottom = QHBoxLayout()
        factory = QPushButton("Ripristina effetto di fabbrica")
        factory.clicked.connect(self._factory_lights)
        bottom.addWidget(factory)
        bottom.addStretch()
        lay.addLayout(bottom)
        self.lights_status = QLabel("Le modifiche vengono applicate subito alla tastiera.")
        self.lights_status.setObjectName("dim")
        lay.addWidget(self.lights_status)
        lay.addStretch()

        self.lights_timer = QTimer(self)
        self.lights_timer.setSingleShot(True)
        self.lights_timer.setInterval(300)
        self.lights_timer.timeout.connect(self._apply_lights)
        self._load_lights()
        return page

    @staticmethod
    def _with_value(slider: QSlider) -> QWidget:
        """A slider with its ``n/max`` value shown on the right."""
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        value = QLabel()
        value.setObjectName("dim")
        value.setFixedWidth(34)

        def show(v: int) -> None:
            value.setText(f"{v}/{slider.maximum()}")

        slider.valueChanged.connect(show)
        show(slider.value())
        row.addWidget(slider, 1)
        row.addWidget(value)
        return box

    def _load_lights(self) -> None:
        """Restore the controls from the last settings (the keyboard can't report them)."""
        s = self.settings
        self._loading_lights = True
        effect = int(s.value("lights/effect", int(rgb_proto.DEFAULT_EFFECT)))
        self.effect_group.button(effect).setChecked(True)
        self.light_color = s.value("lights/color", "") or None
        self.brightness.setValue(int(s.value("lights/brightness", rgb_proto.DEFAULT_BRIGHTNESS)))
        self.speed.setValue(int(s.value("lights/speed", rgb_proto.DEFAULT_SPEED)))
        self.dir_group.button(int(s.value("lights/direction", 0))).setChecked(True)
        self._loading_lights = False
        self._sync_light_controls()

    def _sync_light_controls(self) -> None:
        effect = rgb_proto.RgbEffect(self.effect_group.checkedId())
        info = rgb_proto.EFFECTS[effect]
        on = effect != rgb_proto.RgbEffect.OFF
        self.brightness.setEnabled(on)
        for w in (self.speed, self.speed_label):
            w.setEnabled(info.speed)
        for w in (self.dir_box, self.dir_label):
            w.setEnabled(info.direction)
        color_ok = info.color
        self.rainbow_btn.setEnabled(color_ok and effect != rgb_proto.RgbEffect.STATIC)
        for s in self.swatches:
            s.setEnabled(color_ok)
        rainbow = self.light_color is None and effect != rgb_proto.RgbEffect.STATIC
        self.rainbow_btn.setChecked(rainbow)
        for s, (hex_color, _) in zip(self.swatches, SWATCHES, strict=True):
            s.setChecked(self.light_color == hex_color)
        shown = self.light_color or ("#ffffff" if effect == rgb_proto.RgbEffect.STATIC else None)
        self.color_chip.setStyleSheet(
            f"background: {shown}; border-radius: 6px;"
            if shown
            else "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f7768e,"
            " stop:0.33 #e0af68, stop:0.66 #9ece6a, stop:1 #7aa2f7); border-radius: 6px;"
        )

    def _pick_color(self, hex_color: str | None) -> None:
        self.light_color = hex_color
        effect = rgb_proto.RgbEffect(self.effect_group.checkedId())
        if not rgb_proto.EFFECTS[effect].color:  # picking a color implies a colorable effect
            self.effect_group.button(int(rgb_proto.RgbEffect.STATIC)).setChecked(True)
        self._lights_changed()

    def _custom_color(self) -> None:
        start = QColor(self.light_color or "#ffffff")
        color = QColorDialog.getColor(start, self, "Colore delle luci")
        if color.isValid():
            self._pick_color(color.name())

    def _lights_changed(self) -> None:
        if getattr(self, "_loading_lights", False):
            return
        self._sync_light_controls()
        self.lights_timer.start()

    def _apply_lights(self) -> None:
        effect = rgb_proto.RgbEffect(self.effect_group.checkedId())
        color = self.light_color
        if effect == rgb_proto.RgbEffect.STATIC and color is None:
            color = "#ffffff"  # "static rainbow" isn't a thing: static needs a color
        rgb = None
        if color and rgb_proto.EFFECTS[effect].color:
            rgb = parse_color(color)
        packets = rgb_proto.lighting_packets(
            effect,
            color=rgb,
            brightness=self.brightness.value(),
            speed=self.speed.value(),
            direction=self.dir_group.checkedId(),
        )
        s = self.settings
        s.setValue("lights/effect", int(effect))
        s.setValue("lights/color", self.light_color or "")
        s.setValue("lights/brightness", self.brightness.value())
        s.setValue("lights/speed", self.speed.value())
        s.setValue("lights/direction", self.dir_group.checkedId())

        def after() -> None:
            if self.lights_pending:  # something changed while we were sending
                self.lights_pending = False
                self.lights_timer.start()

        name = EFFECT_LABELS[effect]
        if not self.device_op(
            packets, self.lights_status, f"Applico “{name}”…", f"✓ {name}", after
        ):
            self.lights_pending = not self.uploading
            if self.uploading:
                self.lights_status.setText("Attendi la fine del caricamento sullo schermo.")

    def _factory_lights(self) -> None:
        self._loading_lights = True
        self.effect_group.button(int(rgb_proto.DEFAULT_EFFECT)).setChecked(True)
        self.light_color = None
        self.brightness.setValue(rgb_proto.DEFAULT_BRIGHTNESS)
        self.speed.setValue(rgb_proto.DEFAULT_SPEED)
        self.dir_group.button(0).setChecked(True)
        self._loading_lights = False
        self._lights_changed()

    # ----- keyboard tab ----------------------------------------------------
    def _build_keyboard_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)

        clock_head = QLabel("Orologio")
        clock_head.setObjectName("title")
        lay.addWidget(clock_head)
        row = QHBoxLayout()
        sync = QPushButton("Sincronizza ora")
        sync.setObjectName("primary")
        sync.clicked.connect(self.sync_clock)
        row.addWidget(sync)
        row.addStretch()
        lay.addLayout(row)
        self.auto_clock = QCheckBox(
            "Sincronizza da sola quando colleghi la tastiera (con questa finestra aperta)"
        )
        self.auto_clock.setChecked(self.settings.value("clock/auto", True, type=bool))
        self.auto_clock.toggled.connect(lambda on: self.settings.setValue("clock/auto", on))
        lay.addWidget(self.auto_clock)
        self.clock_status = QLabel(" ")
        self.clock_status.setObjectName("dim")
        lay.addWidget(self.clock_status)

        screen_head = QLabel("Schermo")
        screen_head.setObjectName("title")
        lay.addWidget(screen_head)
        row2 = QHBoxLayout()
        stock = QPushButton("Rimetti l'animazione originale Mechlands")
        stock.clicked.connect(self._stock_animation)
        row2.addWidget(stock)
        row2.addStretch()
        lay.addLayout(row2)

        info_head = QLabel("Stato")
        info_head.setObjectName("title")
        lay.addWidget(info_head)
        self.info_label = QLabel()
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.info_label)
        hint = QLabel(
            "Suggerimento: schermo, luci e orologio si configurano solo col cavo USB-C;\n"
            "in 2.4G la tastiera funziona normalmente ma non accetta impostazioni."
        )
        hint.setObjectName("dim")
        lay.addWidget(hint)
        lay.addStretch()
        return page

    def sync_clock(self) -> None:
        now = datetime.now()
        self.device_op(
            clock_proto.sync(now),
            self.clock_status,
            "Sincronizzo l'orologio…",
            f"✓ Orologio impostato alle {now:%H:%M:%S} del {now:%d/%m/%Y}",
        )

    def _stock_animation(self) -> None:
        stock = store.LIBRARY_DIR / "mechlands-originale.gif"
        if not stock.exists():
            self.clock_status.setText("⚠ Animazione originale non trovata in libreria.")
            return
        self.pages.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)
        self.select_library(stock)

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(stylesheet(load_colors()))

    def _watch_theme(self) -> None:
        self.theme_watcher = QFileSystemWatcher(self)
        for f in THEME_FILES:
            if f.parent.parent.exists():
                self.theme_watcher.addPath(str(f.parent.parent))
        self.theme_watcher.directoryChanged.connect(lambda _: self._apply_theme())

    # ----- library tab -----------------------------------------------------
    def _build_library(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 10, 0, 0)
        bar = QHBoxLayout()
        add = QPushButton("Aggiungi file…")
        add.clicked.connect(self.add_files)
        folder = QPushButton("Apri cartella")
        folder.clicked.connect(self.open_library_folder)
        self.delete_btn = QPushButton("Elimina")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setEnabled(False)
        for b in (add, folder, self.delete_btn):
            bar.addWidget(b)
        bar.addStretch()
        lay.addLayout(bar)
        self.library = TileGrid()
        lay.addWidget(self.library, 1)
        self.library_empty = QLabel(
            "La libreria è vuota: cerca qualcosa nello Store, oppure aggiungi GIF e video."
        )
        self.library_empty.setObjectName("dim")
        self.library_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.library_empty)
        return page

    def refresh_library(self) -> None:
        self.library.clear()
        items = store.library_items()
        self.library_empty.setVisible(not items)
        for path in items:
            tile = Tile(path, path.stem)
            tile.clicked.connect(self.select_library)
            self.library.add(tile)
            if path.suffix.lower() in VIDEO_SUFFIXES:
                self.run(Task(video_thumbnail, path), done=tile.set_image, failed=lambda _: None)
            else:
                tile.set_movie_file(path)
        if self.source is not None and self.store_item is None:
            self.library.select(self.source)

    def select_library(self, path: Path) -> None:
        self.library.select(path)
        self.store_grid.select(None)
        self.delete_btn.setEnabled(True)
        self.store_item = None
        self.save_btn.setVisible(False)
        self.set_source(path)

    def add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Aggiungi alla libreria",
            str(Path.home()),
            "GIF e video (*.gif *.webp *.png *.mp4 *.webm *.mov *.mkv *.m4v)",
        )
        last = None
        for f in files:
            last = store.save_to_library(Path(f))
        self.refresh_library()
        if last is not None:
            self.select_library(last)

    def open_library_folder(self) -> None:
        store.LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["xdg-open", str(store.LIBRARY_DIR)])

    def delete_selected(self) -> None:
        if self.source is None or self.store_item is not None:
            return
        answer = QMessageBox.question(self, "Elimina", f"Eliminare {self.source.name}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.source.unlink(missing_ok=True)
        self.source = None
        self.clip = None
        self.delete_btn.setEnabled(False)
        self._show_empty_preview()
        self.refresh_library()

    # ----- store tab -------------------------------------------------------
    def _build_store(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 10, 0, 0)
        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Cerca GIF (es. pixel art, pokemon, gatto, lofi…)")
        self.query.returnPressed.connect(lambda: self.search(self.query.text()))
        go = QPushButton("Cerca")
        go.clicked.connect(lambda: self.search(self.query.text()))
        self.stickers = QCheckBox("Solo sticker (sfondo trasparente)")
        self.stickers.toggled.connect(lambda _: self.search(self.query.text()))
        bar.addWidget(self.query, 1)
        bar.addWidget(go)
        bar.addWidget(self.stickers)
        lay.addLayout(bar)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for s in SUGGESTIONS:
            b = QPushButton(s)
            b.setObjectName("chip")
            b.clicked.connect(lambda _=False, q=s: self.search(q))
            chips.addWidget(b)
        chips.addStretch()
        lay.addLayout(chips)
        self.store_status = QLabel()
        self.store_status.setObjectName("dim")
        lay.addWidget(self.store_status)
        self.store_grid = TileGrid()
        lay.addWidget(self.store_grid, 1)
        credit = QLabel("Risultati da Tenor · le GIF restano dei rispettivi autori")
        credit.setObjectName("dim")
        credit.setStyleSheet("font-size: 8pt;")
        lay.addWidget(credit)
        return page

    def search(self, query: str) -> None:
        query = query.strip()
        if not query:
            return
        self.query.setText(query)
        self.store_status.setText(f"Cerco “{query}”…")
        self.store_grid.clear()
        self.search_token = getattr(self, "search_token", 0) + 1
        token = self.search_token

        def show(items: list[store.StoreItem]) -> None:
            if token != self.search_token:
                return
            self.store_status.setText(
                f"{len(items)} risultati per “{query}”" if items else "Nessun risultato."
            )
            for it in items:
                tile = Tile(it, it.title or it.id)
                tile.clicked.connect(self.select_store)
                self.store_grid.add(tile)
                self.run(
                    Task(store.fetch, it.preview_url),
                    done=lambda data, t=tile: t.set_movie_bytes(data),
                    failed=lambda _: None,
                )

        self.run(
            Task(functools.partial(store.search, query, stickers=self.stickers.isChecked())),
            done=show,
            failed=lambda msg: self.store_status.setText(f"⚠ {msg}"),
        )

    def select_store(self, item: store.StoreItem) -> None:
        self.store_grid.select(item)
        self.library.select(None)
        self.delete_btn.setEnabled(False)
        self.store_item = item
        self.save_btn.setVisible(True)
        self.save_btn.setEnabled(False)
        self.title.setText(item.title or "GIF dallo store")
        self.status.setText("Scarico la GIF…")

        def ready(path: Path) -> None:
            if self.store_item is item:
                self.save_btn.setEnabled(True)
                self.set_source(path, title=item.title or "GIF dallo store")

        self.run(Task(store.download_full, item), done=ready)

    def save_store_item(self) -> Path | None:
        if self.store_item is None or self.source is None:
            return None
        dest = store.save_to_library(self.source, self.store_item.filename)
        self.status.setText(f"Salvata in libreria: {dest.name}")
        self.refresh_library()
        return dest

    # ----- preview panel ---------------------------------------------------
    def _build_preview(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(SPEC.width * ZOOM + 120)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(10)
        self.title = QLabel("Scegli una GIF")
        self.title.setObjectName("title")
        self.title.setWordWrap(True)
        lay.addWidget(self.title)

        self.screen = QLabel()
        self.screen.setObjectName("screen")
        self.screen.setFixedSize(SPEC.width * ZOOM + 12, SPEC.height * ZOOM + 12)
        self.screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.screen, 0, Qt.AlignmentFlag.AlignHCenter)
        self.summary = QLabel(" ")
        self.summary.setObjectName("dim")
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.fit = QComboBox()
        for label, _ in FITS:
            self.fit.addItem(label)
        self.fit.currentIndexChanged.connect(self.reconvert)
        form.addRow("Inquadratura", self.fit)
        self.max_frames = QSpinBox()
        self.max_frames.setRange(1, GIF_MAX_FRAMES)
        self.max_frames.setValue(MAX_ANIMATION_FRAMES)
        self.max_frames.valueChanged.connect(self.reconvert)
        form.addRow("Fotogrammi max", self.max_frames)
        self.fps = QSpinBox()
        self.fps.setRange(1, 30)
        self.fps.setValue(DEFAULT_ANIMATION_FPS)
        self.fps.setSuffix(" fps")
        self.fps.valueChanged.connect(self.reconvert)
        self.start = QDoubleSpinBox()
        self.start.setRange(0, 36000)
        self.start.setDecimals(1)
        self.start.setSuffix(" s")
        self.start.valueChanged.connect(self.reconvert)
        self.fps_label, self.start_label = QLabel("Velocità"), QLabel("Parti da")
        form.addRow(self.fps_label, self.fps)
        form.addRow(self.start_label, self.start)
        lay.addLayout(form)
        self._set_video_controls(False)

        self.save_btn = QPushButton("Salva in libreria")
        self.save_btn.clicked.connect(self.save_store_item)
        self.save_btn.setVisible(False)
        lay.addWidget(self.save_btn)
        self.upload_btn = QPushButton("Metti sulla tastiera")
        self.upload_btn.setObjectName("primary")
        self.upload_btn.clicked.connect(self.upload)
        self.upload_btn.setEnabled(False)
        lay.addWidget(self.upload_btn)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        lay.addWidget(self.progress)
        self.status = QLabel(" ")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addStretch()
        self.device_label = QLabel()
        self.device_label.setObjectName("dim")
        lay.addWidget(self.device_label)
        self._show_empty_preview()
        return panel

    def _set_video_controls(self, visible: bool) -> None:
        for w in (self.fps, self.start, self.fps_label, self.start_label):
            w.setVisible(visible)

    def _show_empty_preview(self) -> None:
        if hasattr(self, "anim_timer"):
            self.anim_timer.stop()
        self.preview_frames = []
        self.screen.clear()
        self.title.setText("Scegli una GIF")
        self.summary.setText("Anteprima a dimensione schermo (96x160)")
        if hasattr(self, "upload_btn"):
            self.upload_btn.setEnabled(False)

    def set_source(self, path: Path, title: str | None = None) -> None:
        self.source = path
        is_video = path.suffix.lower() in VIDEO_SUFFIXES
        self._set_video_controls(is_video)
        self.fit.blockSignals(True)
        self.fit.setCurrentIndex(1 if is_video else 0)
        self.fit.blockSignals(False)
        self.title.setText(title or path.stem)
        self.status.setText(" ")
        self._convert()

    def reconvert(self) -> None:
        if self.source is not None:
            self.convert_timer.start()

    def _convert(self) -> None:
        if self.source is None:
            return
        self.convert_token += 1
        token = self.convert_token
        self.upload_btn.setEnabled(False)
        self.summary.setText("Converto…")
        args = (
            self.source,
            FITS[self.fit.currentIndex()][1],
            float(self.fps.value()),
            self.max_frames.value(),
            self.start.value(),
        )

        def convert(source, fit, fps, max_frames, start):
            return load_clip(
                source, spec=SPEC, fit=fit, fps=fps, max_frames=max_frames, start=start
            )

        def done(clip: Clip) -> None:
            if token != self.convert_token:
                return
            self.clip = clip
            self.preview_frames = [
                QPixmap.fromImage(frame_image(f)).scaled(
                    SPEC.width * ZOOM,
                    SPEC.height * ZOOM,
                    transformMode=Qt.TransformationMode.FastTransformation,
                )
                for f in clip.frames
            ]
            self.preview_index = 0
            self._next_preview_frame()
            n = len(clip.frames)
            self.summary.setText(
                f"{n} fotogrammi · {clip.duration_ms / 1000:.1f} s in loop\n".replace(".", ",")
                + f"caricamento ≈ {upload_estimate(n)}"
            )
            self.upload_btn.setEnabled(not self.uploading)

        def failed(msg: str) -> None:
            if token == self.convert_token:
                self.summary.setText(f"⚠ {msg}")

        self.run(Task(convert, *args), done=done, failed=failed)

    def _next_preview_frame(self) -> None:
        if not self.preview_frames or self.clip is None:
            return
        i = self.preview_index % len(self.preview_frames)
        self.screen.setPixmap(self.preview_frames[i])
        self.preview_index = i + 1
        if len(self.preview_frames) > 1:
            delay = max(2, min(510, round(self.clip.delays_ms[i])))
            self.anim_timer.start(delay)

    # ----- upload ----------------------------------------------------------
    def upload(self) -> None:
        if self.clip is None or self.uploading:
            return
        if self.busy:
            self.status.setText("Attendi: la tastiera sta già ricevendo dati…")
            return
        if not keyboard_connected():
            self.status.setText("⚠ Collega la tastiera con il cavo USB-C.")
            return
        if self.store_item is not None:
            self.save_store_item()  # the library doubles as history
        self.uploading = self.busy = True
        self.upload_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setText("Carico sulla tastiera… (puoi continuare a scrivere)")

        def progress(done: int, total: int) -> None:
            self.progress.setMaximum(total)
            self.progress.setValue(done)

        def finished(missing: int) -> None:
            self.uploading = self.busy = False
            self.progress.setVisible(False)
            self.upload_btn.setEnabled(self.clip is not None)
            self.status.setText(
                "✓ Fatto! È sulla tastiera."
                if not missing
                else f"⚠ {missing} blocchi senza conferma: riprova col cavo ben inserito."
            )

        def failed(msg: str) -> None:
            self.uploading = self.busy = False
            self.progress.setVisible(False)
            self.upload_btn.setEnabled(self.clip is not None)
            self.status.setText(f"⚠ {msg}")

        self.run(
            Task(do_upload, self.clip, with_progress=True),
            done=finished,
            failed=failed,
            progress=progress,
        )

    def _refresh_device(self) -> None:
        if self.busy:
            return
        devices = enumerate_all()
        ok = any(d.usage_page == CONTROL_USAGE_PAGE and "Vibe99" in d.product for d in devices)
        dongle = any("Wireless Receiver" in d.product for d in devices if d.catalog)
        text = "● Vibe99 collegata (cavo)" if ok else "○ Tastiera non collegata col cavo"
        self.device_label.setText(text)
        self.info_label.setText(
            f"{text}\n"
            + ("● Ricevitore 2.4G inserito\n" if dongle else "")
            + f"Schermo {SPEC.width}x{SPEC.height} · fino a {GIF_MAX_FRAMES} fotogrammi\n"
            + f"Libreria: {store.LIBRARY_DIR}\n"
            + f"vibe99ctl {__version__}"
        )
        if ok and not self.was_connected and self.auto_clock.isChecked():
            self.sync_clock()
        self.was_connected = ok

    def closeEvent(self, event) -> None:
        if self.uploading:
            answer = QMessageBox.question(
                self,
                "Caricamento in corso",
                "Sto ancora caricando sulla tastiera. Chiudere lo stesso?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Vibe99")
    app.setDesktopFileName("vibe99")
    win = Gallery()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
