import sys
import os
import re
import ctypes
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QUrl, QSize, QRectF, QPropertyAnimation,
    QEasingCurve, pyqtProperty, QPoint, QRect, QParallelAnimationGroup,
    QSettings   # ← 新增，用于记忆用户文件夹
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtGui import (
    QFont, QPixmap, QPainter, QPainterPath, QColor, QPen,
    QFontDatabase, QCursor, QBrush, QRegion
)

try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.wave import WAVE
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


# ── 颜色系统 ────────────────────────────────────────────────
C_BG        = "#000000"
C_ISLAND    = "#0A0A0A"
C_BORDER    = "#181818"
C_WHITE     = "#FFFFFF"
C_DIM       = "#555555"
C_MID       = "#888888"
C_ACCENT    = "#FFFFFF"
C_LYRIC_DIM = "#333333"


# ── 无边框拖动 Mixin ────────────────────────────────────────
class DraggableMixin:
    def _drag_init(self):
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# ── 圆角封面 ────────────────────────────────────────────────
class RoundedLabel(QLabel):
    def __init__(self, radius=8, size=60, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.setFixedSize(size, size)
        self._pixmap = QPixmap()

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def clear_pixmap(self):
        self._pixmap = QPixmap()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.radius, self.radius)
        painter.setClipPath(path)
        if not self._pixmap.isNull():
            painter.drawPixmap(self.rect(), self._pixmap)
        else:
            painter.fillRect(self.rect(), QColor(C_ISLAND))
        painter.setClipPath(QPainterPath())
        pen = QPen(QColor(C_BORDER))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            self.radius, self.radius
        )


# ── 矢量图标按钮 ────────────────────────────────────────────
class IconButton(QPushButton):
    def __init__(self, icon_type, size=36, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def enterEvent(self, e):
        self._hover = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        is_main = self.icon_type in ("play", "pause")

        if is_main:
            color = QColor("#CCCCCC") if self._hover else QColor(C_WHITE)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.rect())
            painter.setBrush(QColor(C_BG))
        else:
            painter.setBrush(QColor(C_WHITE) if self._hover else QColor(C_MID))
        painter.setPen(Qt.PenStyle.NoPen)

        if self.icon_type == "play":
            path = QPainterPath()
            path.moveTo(cx - 6, cy - 8)
            path.lineTo(cx - 6, cy + 8)
            path.lineTo(cx + 9, cy)
            path.closeSubpath()
            painter.drawPath(path)

        elif self.icon_type == "pause":
            bw, bh, gap = 4, 14, 3
            x1 = cx - gap / 2 - bw
            x2 = cx + gap / 2
            y = cy - bh / 2
            painter.drawRoundedRect(int(x1), int(y), bw, bh, 1, 1)
            painter.drawRoundedRect(int(x2), int(y), bw, bh, 1, 1)

        elif self.icon_type == "prev":
            bw, bh = 2, 13
            painter.drawRect(int(cx - 9), int(cy - bh / 2), bw, bh)
            path = QPainterPath()
            path.moveTo(cx - 2, cy)
            path.lineTo(cx + 7, cy - 6.5)
            path.lineTo(cx + 7, cy + 6.5)
            path.closeSubpath()
            painter.drawPath(path)

        elif self.icon_type == "next":
            bw, bh = 2, 13
            painter.drawRect(int(cx + 7), int(cy - bh / 2), bw, bh)
            path = QPainterPath()
            path.moveTo(cx + 2, cy)
            path.lineTo(cx - 7, cy - 6.5)
            path.lineTo(cx - 7, cy + 6.5)
            path.closeSubpath()
            painter.drawPath(path)

        elif self.icon_type == "folder":
            painter.setBrush(QColor(C_WHITE) if self._hover else QColor(C_DIM))
            path = QPainterPath()
            path.moveTo(cx - 9, cy - 5)
            path.lineTo(cx - 4, cy - 5)
            path.lineTo(cx - 2, cy - 7)
            path.lineTo(cx + 4, cy - 7)
            path.lineTo(cx + 4, cy - 5)
            path.lineTo(cx + 9, cy - 5)
            path.lineTo(cx + 9, cy + 6)
            path.lineTo(cx - 9, cy + 6)
            path.closeSubpath()
            painter.drawPath(path)

        elif self.icon_type == "close":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(C_WHITE) if self._hover else QColor(C_DIM), 1.5)
            painter.setPen(pen)
            painter.drawLine(int(cx - 5), int(cy - 5), int(cx + 5), int(cy + 5))
            painter.drawLine(int(cx + 5), int(cy - 5), int(cx - 5), int(cy + 5))

        elif self.icon_type == "minus":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(C_WHITE) if self._hover else QColor(C_DIM), 1.5)
            painter.setPen(pen)
            painter.drawLine(int(cx - 6), int(cy), int(cx + 6), int(cy))


# ── LRC 解析 ────────────────────────────────────────────────
class LRCParser:
    def __init__(self, source=None, is_file=True):
        self.lines = []
        if not source:
            return
        if is_file and os.path.exists(source):
            with open(source, 'r', encoding='utf-8') as f:
                self._parse(f.read())
        else:
            self._parse(source)

    def _parse(self, text):
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            times = re.findall(r'\[(\d{2}):(\d{2})\.(\d{2,3})\]', line)
            content = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]', '', line).strip()
            for m, s, ms in times:
                t = int(m)*60000 + int(s)*1000 + (int(ms)*10 if len(ms)==2 else int(ms))
                if content:
                    self.lines.append((t, content))
        self.lines.sort(key=lambda x: x[0])

    def get_lines(self, pos_ms):
        if not self.lines:
            return ("暂无歌词", "")
        idx = -1
        for i, (t, _) in enumerate(self.lines):
            if t <= pos_ms:
                idx = i
        if idx == -1:
            return ("", self.lines[0][1])
        cur = self.lines[idx][1]
        nxt = self.lines[idx+1][1] if idx+1 < len(self.lines) else ""
        return (cur, nxt)


# ── Song ────────────────────────────────────────────────────
class Song:
    def __init__(self, path):
        self.path = path
        self.title = Path(path).stem
        self.artist = "未知艺术家"
        self.album = "未知专辑"
        self.date_display = ""
        self.duration = 0
        self.cover_pixmap = None
        self.description = ""
        self.lrc = None
        self._parse_metadata()
        self._load_cover()
        self._load_lyrics()

    def _parse_metadata(self):
        if not MUTAGEN_AVAILABLE:
            return
        try:
            if self.path.lower().endswith('.mp3'):
                audio = MP3(self.path)
                if audio.tags:
                    self.title  = audio.tags.get('TIT2', [self.title])[0]
                    self.artist = audio.tags.get('TPE1', ["未知艺术家"])[0]
                    self.album  = audio.tags.get('TALB', ["未知专辑"])[0]
                    date_raw = ""
                    if 'TDRC' in audio.tags:
                        date_raw = str(audio.tags['TDRC'].text[0])
                    elif 'TYER' in audio.tags:
                        date_raw = str(audio.tags['TYER'].text[0])
                    self.date_display = date_raw if date_raw else ""
                self.duration = int(audio.info.length) if audio.info else 0
            elif self.path.lower().endswith('.flac'):
                audio = FLAC(self.path)
                self.title   = audio.get('title',  [self.title])[0]
                self.artist  = audio.get('artist', ["未知艺术家"])[0]
                self.album   = audio.get('album',  ["未知专辑"])[0]
                date_field = audio.get('date', [""])[0].strip()
                self.date_display = date_field if date_field else ""
                self.description = audio.get('description', [""])[0]
                self.duration = int(audio.info.length) if audio.info else 0
            elif self.path.lower().endswith('.wav'):
                audio = WAVE(self.path)
                self.duration = int(audio.info.length) if audio.info else 0
                self.date_display = ""
        except Exception:
            pass

    def _load_cover(self):
        if not MUTAGEN_AVAILABLE:
            self._fallback_cover(); return
        try:
            if self.path.lower().endswith('.flac'):
                audio = FLAC(self.path)
                if audio.pictures:
                    px = QPixmap(); px.loadFromData(audio.pictures[0].data)
                    self.cover_pixmap = px
            elif self.path.lower().endswith('.mp3'):
                audio = MP3(self.path)
                if audio.tags:
                    for k, v in audio.tags.items():
                        if k.startswith('APIC'):
                            px = QPixmap(); px.loadFromData(v.data)
                            self.cover_pixmap = px; break
        except Exception:
            pass
        if not self.cover_pixmap or self.cover_pixmap.isNull():
            self._fallback_cover()

    def _fallback_cover(self):
        for p in [
            os.path.splitext(self.path)[0] + ".jpg",
            os.path.join(os.path.dirname(self.path), "cover.jpg")
        ]:
            if os.path.exists(p):
                self.cover_pixmap = QPixmap(p); return

    def _load_lyrics(self):
        if self.path.lower().endswith('.flac'):
            try:
                audio = FLAC(self.path)
                embedded = audio.get('lyrics', [""])[0]
                if embedded:
                    self.lrc = LRCParser(source=embedded, is_file=False); return
            except Exception:
                pass
        lrc_path = os.path.splitext(self.path)[0] + ".lrc"
        self.lrc = LRCParser(lrc_path)

    def duration_str(self):
        m, s = divmod(self.duration, 60)
        return f"{m}:{s:02d}"


class MusicScanner:
    @staticmethod
    def scan_folder(folder_path):
        songs = []
        exts = {'.mp3', '.flac', '.wav', '.m4a', '.ogg'}
        for root, _, files in os.walk(folder_path):
            for f in sorted(files):
                if Path(f).suffix.lower() in exts:
                    songs.append(Song(os.path.join(root, f)))
        return songs


# ── Island Widget（带圆角背景的容器）──────────────────────
class Island(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            Island {{
                background-color: {C_ISLAND};
                border-radius: 12px;
                border: 1px solid {C_BORDER};
            }}
        """)


# ── 可拖动顶部条 ────────────────────────────────────────────
class TitleBar(DraggableMixin, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_init()
        self.setFixedHeight(40)
        self.setStyleSheet(f"background: {C_BG};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(0)

        self.folder_btn = IconButton("folder", size=28)
        self.folder_btn.setToolTip("选择音乐文件夹")

        layout.addWidget(self.folder_btn)
        layout.addStretch()

        self.min_btn   = IconButton("minus", size=28)
        self.close_btn = IconButton("close", size=28)
        self.min_btn.setToolTip("最小化")
        self.close_btn.setToolTip("关闭")

        layout.addWidget(self.min_btn)
        layout.addSpacing(4)
        layout.addWidget(self.close_btn)


# ── 歌曲列表项 ──────────────────────────────────────────────
class SongItem(QWidget):
    def __init__(self, song, index, parent=None):
        super().__init__(parent)
        self.song = song
        self.index = index
        self.setFixedHeight(56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        self.cover = RoundedLabel(radius=4, size=44)
        if song.cover_pixmap and not song.cover_pixmap.isNull():
            scaled = song.cover_pixmap.scaled(44, 44,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self.cover.setPixmap(scaled)
        layout.addWidget(self.cover)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QLabel(str(song.title))
        self.title_lbl.setStyleSheet(f"color: {C_WHITE}; font-size: 12px; font-weight: 600; background: transparent;")
        self.title_lbl.setMaximumWidth(220)

        self.artist_lbl = QLabel(str(song.artist))
        self.artist_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 11px; background: transparent;")
        self.artist_lbl.setMaximumWidth(220)

        info.addWidget(self.title_lbl)
        info.addWidget(self.artist_lbl)
        layout.addLayout(info, stretch=1)

        self.dur_lbl = QLabel(song.duration_str())
        self.dur_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 10px; background: transparent;")
        layout.addWidget(self.dur_lbl)

    def enterEvent(self, e):
        self._hover = True; self.update()

    def leaveEvent(self, e):
        self._hover = False; self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hover:
            painter.setBrush(QColor("#141414"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 6, 6)


# ── 歌词视图（两行滚动）────────────────────────────────────
class LyricsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self._line_height = 28

        self._current_label = QLabel(self)
        self._next_label = QLabel(self)

        for lbl in (self._current_label, self._next_label):
            lbl.setStyleSheet(f"color: {C_WHITE}; font-size: 14px; font-weight: 600; background: transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            lbl.setWordWrap(False)
            lbl.setFixedHeight(self._line_height)

        self._next_label.setStyleSheet(f"color: {C_LYRIC_DIM}; font-size: 12px; background: transparent;")
        self._next_label.setFixedHeight(self._line_height)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_cur = QPropertyAnimation(self._current_label, b"pos")
        self._anim_next = QPropertyAnimation(self._next_label, b"pos")
        self._anim_group.addAnimation(self._anim_cur)
        self._anim_group.addAnimation(self._anim_next)
        self._anim_group.finished.connect(self._on_anim_finished)

        self._pending_cur = ""
        self._pending_next = ""
        self._animating = False

        self._reset_positions()
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._animating:
            self._reset_positions()

    def _reset_positions(self):
        w = self.width()
        self._current_label.setGeometry(0, 4, w, self._line_height)
        self._next_label.setGeometry(0, 4 + self._line_height, w, self._line_height)

    def set_lyrics(self, current: str, next_line: str):
        if current == self._current_label.text() and next_line == self._next_label.text():
            return
        if self._animating:
            self._anim_group.stop()
            self._on_anim_finished()

        self._anim_cur.setStartValue(self._current_label.pos())
        self._anim_next.setStartValue(self._next_label.pos())
        cur_start = self._current_label.pos()
        next_start = self._next_label.pos()
        self._anim_cur.setEndValue(QPoint(cur_start.x(), cur_start.y() - self._line_height))
        self._anim_next.setEndValue(QPoint(next_start.x(), next_start.y() - self._line_height))

        self._pending_cur = current
        self._pending_next = next_line
        self._animating = True

        self._anim_cur.setDuration(250)
        self._anim_next.setDuration(250)
        self._anim_group.start()

    def _on_anim_finished(self):
        self._current_label.setText(self._pending_cur)
        self._next_label.setText(self._pending_next)
        self._reset_positions()
        self._animating = False
        self._pending_cur = ""
        self._pending_next = ""


# ── 主窗口 ──────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Just Music")
        self.setFixedSize(380, 680)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self.songs = []
        self.current_index = -1
        self.is_playing = False
        self.is_seeking = False
        self._song_widgets = []

        # 🔥 新增：用户数据设置
        self.settings = QSettings("JustMusic", "JustMusic")

        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(500)

        self._setup_ui()
        self._connect_signals()

        # 🔥 修改启动加载逻辑：优先加载上次文件夹
        last_folder = self.settings.value("last_folder", "")
        if last_folder and os.path.exists(last_folder):
            self.load_folder(last_folder)
        else:
            default = os.path.join(os.path.expanduser("~"), "Music", "Just Music")
            if os.path.exists(default):
                self.load_folder(default)

        self._update_window_mask()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_window_mask()

    def _update_window_mask(self):
        radius = 16
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

    def _setup_ui(self):
        root = QWidget()
        root.setStyleSheet(f"""
            QWidget {{
                background-color: {C_BG};
                border-radius: 16px;
            }}
        """)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar()
        root_layout.addWidget(self.title_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ background: {C_BG}; border: none; }}")

        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(16, 8, 16, 16)
        self.body_layout.setSpacing(10)

        info_island = Island()
        info_layout = QHBoxLayout(info_island)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(12)

        self.cover_label = RoundedLabel(radius=8, size=64)
        info_layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignTop)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(3)
        meta_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel("未在播放")
        self.title_label.setStyleSheet(
            f"color: {C_WHITE}; font-size: 18px; font-weight: 700; "
            f"background: transparent; letter-spacing: -0.3px;"
        )
        self.title_label.setWordWrap(True)

        self.date_label = QLabel("")
        self.date_label.setStyleSheet(f"color: {C_DIM}; font-size: 11px; background: transparent;")

        self.artist_label = QLabel("选择一首歌曲")
        self.artist_label.setStyleSheet(f"color: {C_MID}; font-size: 12px; background: transparent;")

        self.album_label = QLabel("")
        self.album_label.setStyleSheet(f"color: {C_DIM}; font-size: 11px; background: transparent;")

        meta_layout.addWidget(self.title_label)
        meta_layout.addWidget(self.date_label)
        meta_layout.addWidget(self.artist_label)
        meta_layout.addWidget(self.album_label)
        info_layout.addLayout(meta_layout, stretch=1)

        self.body_layout.addWidget(info_island)

        ctrl_island = Island()
        ctrl_layout = QVBoxLayout(ctrl_island)
        ctrl_layout.setContentsMargins(14, 10, 14, 10)
        ctrl_layout.setSpacing(8)

        vol_row = QHBoxLayout()
        vol_row.setSpacing(6)
        vol_label = QLabel("音量")
        vol_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px; background: transparent;")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 2px; background: {C_BORDER}; border-radius: 1px;
            }}
            QSlider::sub-page:horizontal {{
                background: {C_MID}; border-radius: 1px;
            }}
            QSlider::handle:horizontal {{
                background: {C_MID}; width: 8px; height: 8px;
                border-radius: 4px; margin: -3px 0;
            }}
        """)
        vol_row.addWidget(vol_label)
        vol_row.addWidget(self.vol_slider)
        ctrl_layout.addLayout(vol_row)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.setSpacing(16)

        self.prev_btn = IconButton("prev", size=36)
        self.play_btn = IconButton("play", size=46)
        self.next_btn = IconButton("next", size=36)

        btn_row.addWidget(self.prev_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.next_btn)
        ctrl_layout.addLayout(btn_row)

        prog_row = QHBoxLayout()
        prog_row.setSpacing(8)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 3px;
                background: {C_BORDER};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {C_WHITE};
                border-radius: 3px;
            }}
            QSlider::add-page:horizontal {{
                background: {C_BORDER};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                border: none;
                width: 12px;
                height: 12px;
                border-radius: 6px;
                margin: -4px 0;
            }}
        """)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet(f"color: {C_DIM}; font-size: 10px; background: transparent;")
        self.time_label.setFixedWidth(72)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_row.addWidget(self.progress)
        prog_row.addWidget(self.time_label)
        ctrl_layout.addLayout(prog_row)

        self.body_layout.addWidget(ctrl_island)

        lyric_island = Island()
        lyric_layout = QVBoxLayout(lyric_island)
        lyric_layout.setContentsMargins(14, 12, 14, 12)
        lyric_layout.setSpacing(0)

        self.lyrics_view = LyricsView()
        lyric_layout.addWidget(self.lyrics_view)

        self.body_layout.addWidget(lyric_island)

        desc_island = Island()
        desc_outer = QVBoxLayout(desc_island)
        desc_outer.setContentsMargins(14, 10, 14, 10)
        desc_outer.setSpacing(6)

        desc_header = QLabel("歌曲赏析")
        desc_header.setStyleSheet(f"color: {C_DIM}; font-size: 10px; letter-spacing: 1px; background: transparent;")
        desc_outer.addWidget(desc_header)

        self.desc_scroll = QScrollArea()
        self.desc_scroll.setFixedHeight(80)
        self.desc_scroll.setWidgetResizable(True)
        self.desc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.desc_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.desc_scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QWidget {{ background: transparent; }}
        """)

        desc_inner = QWidget()
        desc_inner_layout = QVBoxLayout(desc_inner)
        desc_inner_layout.setContentsMargins(0, 0, 0, 0)

        self.desc_label = QLabel("选择一首歌曲，这里将显示对应的歌曲赏析。")
        self.desc_label.setStyleSheet(f"color: {C_MID}; font-size: 12px; line-height: 1.6; background: transparent;")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        desc_inner_layout.addWidget(self.desc_label)
        desc_inner_layout.addStretch()

        self.desc_scroll.setWidget(desc_inner)
        desc_outer.addWidget(self.desc_scroll)
        self.body_layout.addWidget(desc_island)

        list_island = Island()
        list_layout = QVBoxLayout(list_island)
        list_layout.setContentsMargins(0, 10, 0, 10)
        list_layout.setSpacing(6)

        list_header = QLabel("播放列表")
        list_header.setStyleSheet(
            f"color: {C_DIM}; font-size: 10px; letter-spacing: 1px; "
            f"background: transparent; padding-left: 14px;"
        )
        list_layout.addWidget(list_header)

        self.list_scroll = QScrollArea()
        self.list_scroll.setFixedHeight(200)
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QWidget {{ background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 4px; border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {C_DIM};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_inner = QVBoxLayout(self.list_container)
        self.list_inner.setContentsMargins(0, 0, 0, 0)
        self.list_inner.setSpacing(0)
        self.list_inner.addStretch()

        self.list_scroll.setWidget(self.list_container)
        list_layout.addWidget(self.list_scroll)
        self.body_layout.addWidget(list_island)

        scroll.setWidget(body)
        root_layout.addWidget(scroll)

    def _connect_signals(self):
        self.title_bar.folder_btn.clicked.connect(self.scan_folder)
        self.title_bar.close_btn.clicked.connect(self.close)
        self.title_bar.min_btn.clicked.connect(self.showMinimized)

        self.play_btn.clicked.connect(self.toggle_play)
        self.prev_btn.clicked.connect(self.prev_song)
        self.next_btn.clicked.connect(self.next_song)

        self.progress.sliderPressed.connect(lambda: setattr(self, 'is_seeking', True))
        self.progress.sliderMoved.connect(self._on_slider_moved)
        self.progress.sliderReleased.connect(self._on_slider_released)
        self.vol_slider.valueChanged.connect(self._change_volume)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(lambda _: self._update_time_label())

    def load_folder(self, folder_path):
        if not os.path.exists(folder_path):
            return
        self.songs = MusicScanner.scan_folder(folder_path)
        self._rebuild_list()

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if folder:
            # 🔥 保存用户选择的文件夹
            self.settings.setValue("last_folder", folder)
            self.load_folder(folder)

    def _rebuild_list(self):
        while self.list_inner.count() > 1:
            item = self.list_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._song_widgets.clear()

        for i, song in enumerate(self.songs):
            w = SongItem(song, i)
            w.mouseReleaseEvent = lambda e, idx=i: self._on_song_clicked(idx)
            self.list_inner.insertWidget(self.list_inner.count() - 1, w)
            self._song_widgets.append(w)

    def _on_song_clicked(self, idx):
        self.current_index = idx
        self.play_song(self.songs[idx])

    def play_song(self, song):
        self.player.setSource(QUrl.fromLocalFile(song.path))
        self.player.play()
        self.is_playing = True

        self.title_label.setText(str(song.title))
        self.date_label.setText(song.date_display if song.date_display else "")
        self.artist_label.setText(str(song.artist))
        self.album_label.setText(str(song.album))

        self.play_btn.icon_type = "pause"
        self.play_btn.update()

        if song.cover_pixmap and not song.cover_pixmap.isNull():
            scaled = song.cover_pixmap.scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_label.setPixmap(scaled)
        else:
            self.cover_label.clear_pixmap()

        self.desc_label.setText(song.description if song.description else "暂无歌曲赏析。")
        self._update_lyric_display(0)
        self._highlight_list_item()

    def toggle_play(self):
        if not self.songs:
            return
        if self.is_playing:
            self.player.pause()
            self.is_playing = False
            self.play_btn.icon_type = "play"
            self.play_btn.update()
        else:
            if self.player.source().isEmpty():
                self.current_index = 0
                self.play_song(self.songs[0])
            else:
                self.player.play()
                self.is_playing = True
                self.play_btn.icon_type = "pause"
                self.play_btn.update()

    def prev_song(self):
        if not self.songs or self.current_index <= 0:
            return
        self.current_index -= 1
        self.play_song(self.songs[self.current_index])

    def next_song(self):
        if not self.songs:
            return
        self.current_index = (self.current_index + 1) % len(self.songs)
        self.play_song(self.songs[self.current_index])

    def _on_slider_moved(self, val):
        if self.player.duration() <= 0:
            return
        pos = int(val / 1000 * self.player.duration())
        self._fmt_time_label(pos // 1000, self.player.duration() // 1000)
        self._update_lyric_display(pos)

    def _on_slider_released(self):
        self.is_seeking = False
        if self.player.duration() > 0:
            self.player.setPosition(int(self.progress.value() / 1000 * self.player.duration()))

    def _on_position_changed(self, pos):
        if self.is_seeking:
            return
        if self.player.duration() > 0:
            self.progress.setValue(int(pos / self.player.duration() * 1000))
        self._update_lyric_display(pos)

    def _tick(self):
        self._update_time_label()

    def _update_time_label(self):
        pos = self.player.position() // 1000
        dur = self.player.duration() // 1000
        self._fmt_time_label(pos, dur)

    def _fmt_time_label(self, pos_s, dur_s):
        def f(s): m, sec = divmod(s, 60); return f"{m}:{sec:02d}"
        self.time_label.setText(f"{f(pos_s)} / {f(dur_s)}")

    def _change_volume(self, val):
        self.audio_output.setVolume((val / 100.0) ** 2)

    def _update_lyric_display(self, pos_ms):
        if 0 <= self.current_index < len(self.songs):
            song = self.songs[self.current_index]
            if song.lrc:
                cur, nxt = song.lrc.get_lines(pos_ms)
                self.lyrics_view.set_lyrics(cur if cur else "…", nxt if nxt else "—")
                return
        self.lyrics_view.set_lyrics("暂无歌词", "")

    def _highlight_list_item(self):
        for i, w in enumerate(self._song_widgets):
            is_cur = (i == self.current_index)
            w.title_lbl.setStyleSheet(
                f"color: {C_WHITE}; font-size: 12px; font-weight: {'700' if is_cur else '600'}; background: transparent;"
            )
            w.artist_lbl.setStyleSheet(
                f"color: {'#AAAAAA' if is_cur else C_DIM}; font-size: 11px; background: transparent;"
            )

    # 🔥 可选：关闭时同步设置，确保写入硬盘
    def closeEvent(self, event):
        self.settings.sync()
        super().closeEvent(event)

import sys
import os

def resource_path(relative_path):
    """让打包后的exe也能找到同目录的文件"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ── 入口 ────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    for fname in ["SarasaUiSC-Regular.ttf", "SarasaUiSC-Bold.ttf"]:
        fid = QFontDatabase.addApplicationFont(resource_path(fname))
        if fid != -1:
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                app.setFont(QFont(families[0], 10))
                break
    else:
        app.setFont(QFont("Microsoft YaHei", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()