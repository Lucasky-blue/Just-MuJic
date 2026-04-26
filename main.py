import sys
import os
import re
import ctypes
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QLabel, QListWidget, QListWidgetItem,
    QFileDialog, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, QRectF
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPainterPath, QColor, QPen

try:
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.wave import WAVE
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


def set_dark_titlebar(hwnd):
    """强制 Windows 11 22H2+ 标题栏纯黑"""
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMWA_BORDER_COLOR = 34
        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR = 36
        DWMSBT_NONE = 1

        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
            ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(ctypes.c_int(DWMSBT_NONE)), ctypes.sizeof(ctypes.c_int)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(ctypes.c_int(0x00000000)), ctypes.sizeof(ctypes.c_int)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(ctypes.c_int(0x00000000)), ctypes.sizeof(ctypes.c_int)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_TEXT_COLOR,
            ctypes.byref(ctypes.c_int(0x00FFFFFF)), ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass


class OLEDStyles:
    MAIN = """
        QMainWindow { background-color: #000000; color: #E0E0E0; border: none; }
        QWidget { background-color: #000000; color: #E0E0E0; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }
    """

    SIDEBAR = """
        QFrame#Sidebar { background-color: #000000; border-right: 1px solid #1A1A1A; }
        QPushButton {
            background-color: transparent;
            color: #888888;
            border: none;
            outline: none;
            padding: 12px 20px;
            text-align: left;
            font-size: 14px;
            border-radius: 6px;
            margin: 4px 8px;
        }
        QPushButton:hover {
            background-color: #1A1A1A;
            color: #FFFFFF;
            border: none;
            outline: none;
        }
        QPushButton:checked {
            background-color: #1A1A1A;
            color: #FFFFFF;
            border: none;
            outline: none;
            border-left: 3px solid #FFFFFF;
        }
    """

    SONG_LIST = """
        QListWidget {
            background-color: #000000;
            color: #E0E0E0;
            border: none;
            outline: none;
            padding: 8px;
        }
        QListWidget::item {
            background-color: transparent;
            color: #AAAAAA;
            padding: 12px 16px;
            border-radius: 8px;
            margin: 2px 4px;
        }
        QListWidget::item:hover {
            background-color: #111111;
            color: #FFFFFF;
        }
        QListWidget::item:selected {
            background-color: #151515;
            color: #FFFFFF;
            border-left: 3px solid #FFFFFF;
        }
        QScrollBar:vertical {
            background: #000000;
            width: 6px;
            border-radius: 3px;
        }
        QScrollBar::handle:vertical {
            background: #333333;
            border-radius: 3px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #555555;
        }
    """

    CONTROLS = """
        QPushButton#PlayBtn {
            background-color: #FFFFFF;
            color: #000000;
            border-radius: 25px;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 14px;
            min-width: 80px;
        }
        QPushButton#PlayBtn:hover {
            background-color: #CCCCCC;
        }
        QPushButton#CtrlBtn {
            background-color: transparent;
            color: #888888;
            border-radius: 20px;
            padding: 8px 16px;
            font-size: 12px;
        }
        QPushButton#CtrlBtn:hover {
            color: #FFFFFF;
            background-color: #1A1A1A;
        }
        QSlider::groove:horizontal {
            height: 4px;
            background: #333333;
            border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: #FFFFFF;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #FFFFFF;
            width: 12px;
            height: 12px;
            border-radius: 6px;
            margin: -4px 0;
        }
    """

    PLAYER_PANEL = """
        QWidget#PlayerPanel { background-color: #000000; border-bottom: 1px solid #1A1A1A; }
    """ + CONTROLS

    CONTROL_BAR = """
        QWidget#ControlBar { background-color: #000000; border-bottom: 1px solid #1A1A1A; }
    """ + CONTROLS


class RoundedLabel(QLabel):
    """圆角封面标签（带白色边框）"""
    def __init__(self, radius=8, size=80, parent=None):
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
        
        # 1. 画圆角图片/背景（带裁剪）
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self.radius, self.radius)
        painter.setClipPath(path)
        
        if not self._pixmap.isNull():
            painter.drawPixmap(self.rect(), self._pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#1A1A1A"))
        
        # 2. 画白色圆角边框（无裁剪，确保完整）
        painter.setClipPath(QPainterPath())
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            self.radius, self.radius
        )


class LRCParser:
    def __init__(self, source=None, is_file=True):
        self.lines = []
        if not source:
            return
        if is_file and os.path.exists(source):
            with open(source, 'r', encoding='utf-8') as f:
                self._parse_text(f.read())
        else:
            self._parse_text(source)

    def _parse_text(self, text):
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            times = re.findall(r'\[(\d{2}):(\d{2})\.(\d{2,3})\]', line)
            text_content = re.sub(r'\[\d{2}:\d{2}\.\d{2,3}\]', '', line).strip()
            for m, s, ms in times:
                ms_int = int(ms) if len(ms) == 2 else int(ms) // 10
                time_ms = int(m) * 60000 + int(s) * 1000 + ms_int * 10
                if text_content:
                    self.lines.append((time_ms, text_content))
        self.lines.sort(key=lambda x: x[0])

    def get_lines(self, pos_ms):
        if not self.lines:
            return ("暂无歌词", "")
        current_idx = -1
        for i, (t, text) in enumerate(self.lines):
            if t <= pos_ms:
                current_idx = i
        if current_idx == -1:
            return ("", self.lines[0][1])
        current = self.lines[current_idx][1]
        next_text = self.lines[current_idx + 1][1] if current_idx + 1 < len(self.lines) else ""
        return (current, next_text)


class Song:
    def __init__(self, path):
        self.path = path
        self.title = Path(path).stem
        self.artist = "未知艺术家"
        self.album = "未知专辑"
        self.year = ""
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
                    self.title = audio.tags.get('TIT2', [self.title])[0]
                    self.artist = audio.tags.get('TPE1', ["未知艺术家"])[0]
                    self.album = audio.tags.get('TALB', ["未知专辑"])[0]
                    year_tag = audio.tags.get('TDRC') or audio.tags.get('TYER')
                    if year_tag:
                        self.year = str(year_tag[0])[:4]
                self.duration = int(audio.info.length) if audio.info else 0
            elif self.path.lower().endswith('.flac'):
                audio = FLAC(self.path)
                self.title = audio.get('title', [self.title])[0]
                self.artist = audio.get('artist', ["未知艺术家"])[0]
                self.album = audio.get('album', ["未知专辑"])[0]
                date = audio.get('date', [""])[0]
                self.year = date[:4] if date else ""
                self.description = audio.get('description', [""])[0]
                self.duration = int(audio.info.length) if audio.info else 0
            elif self.path.lower().endswith('.wav'):
                audio = WAVE(self.path)
                self.duration = int(audio.info.length) if audio.info else 0
        except Exception:
            pass

    def _load_cover(self):
        if not MUTAGEN_AVAILABLE:
            self._fallback_cover()
            return
        try:
            if self.path.lower().endswith('.flac'):
                audio = FLAC(self.path)
                if audio.pictures:
                    pic = audio.pictures[0]
                    pixmap = QPixmap()
                    pixmap.loadFromData(pic.data)
                    self.cover_pixmap = pixmap
            elif self.path.lower().endswith('.mp3'):
                audio = MP3(self.path)
                if audio.tags:
                    for k, v in audio.tags.items():
                        if k.startswith('APIC'):
                            pixmap = QPixmap()
                            pixmap.loadFromData(v.data)
                            self.cover_pixmap = pixmap
                            break
        except Exception:
            pass
        if self.cover_pixmap is None or self.cover_pixmap.isNull():
            self._fallback_cover()

    def _fallback_cover(self):
        cover_path = os.path.splitext(self.path)[0] + ".jpg"
        if not os.path.exists(cover_path):
            cover_path = os.path.join(os.path.dirname(self.path), "cover.jpg")
        if os.path.exists(cover_path):
            self.cover_pixmap = QPixmap(cover_path)

    def _load_lyrics(self):
        if self.path.lower().endswith('.flac'):
            try:
                audio = FLAC(self.path)
                embedded = audio.get('lyrics', [""])[0]
                if embedded:
                    self.lrc = LRCParser(source=embedded, is_file=False)
                    return
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Just Music")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet(OLEDStyles.MAIN)

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

        self.songs = []
        self.current_index = -1
        self.is_playing = False
        self.is_seeking = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(500)

        self._setup_ui()
        self._connect_signals()

        default_music_path = r"C:\Users\hp\Music\Just Music"
        self.load_folder(default_music_path)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧边栏
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(OLEDStyles.SIDEBAR)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 20, 0, 20)
        sb_layout.setSpacing(8)

        self.btn_local = QPushButton("📁 本地音乐")
        self.btn_local.setCheckable(True)
        self.btn_local.setChecked(True)
        self.btn_scan = QPushButton("🔄 扫描文件夹")

        sb_layout.addWidget(self.btn_local)
        sb_layout.addWidget(self.btn_scan)

        self.song_list = QListWidget()
        self.song_list.setStyleSheet(OLEDStyles.SONG_LIST)
        self.song_list.setSpacing(4)
        sb_layout.addWidget(self.song_list, stretch=1)

        # 右侧主区域
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 顶部面板：封面 + 歌名 + 歌词
        self.player_panel = QWidget()
        self.player_panel.setObjectName("PlayerPanel")
        self.player_panel.setFixedHeight(120)
        self.player_panel.setStyleSheet(OLEDStyles.PLAYER_PANEL)
        panel_layout = QHBoxLayout(self.player_panel)
        panel_layout.setContentsMargins(30, 16, 30, 16)
        panel_layout.setSpacing(20)

        # 封面（圆角 + 白色边框，80x80）
        self.cover_label = RoundedLabel(radius=8, size=80)
        panel_layout.addWidget(self.cover_label)

        # 歌名信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        self.title_label = QLabel("未在播放")
        self.title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #FFFFFF;")
        self.year_label = QLabel("")
        self.year_label.setStyleSheet("font-size: 13px; color: #666666;")
        self.artist_label = QLabel("选择一首歌曲")
        self.artist_label.setStyleSheet("font-size: 15px; color: #888888;")
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.year_label)
        info_layout.addWidget(self.artist_label)
        panel_layout.addLayout(info_layout, stretch=2)

        # 歌词
        lyric_box = QVBoxLayout()
        lyric_box.setSpacing(6)
        lyric_box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.lyric_current = QLabel("歌词")
        self.lyric_current.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: bold;")
        self.lyric_current.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lyric_box.addWidget(self.lyric_current)

        self.lyric_next = QLabel("即将播放...")
        self.lyric_next.setStyleSheet("color: #444444; font-size: 13px;")
        self.lyric_next.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lyric_box.addWidget(self.lyric_next)

        panel_layout.addLayout(lyric_box, stretch=3)

        right_layout.addWidget(self.player_panel)

        # 中间控制条
        control_bar = QWidget()
        control_bar.setObjectName("ControlBar")
        control_bar.setFixedHeight(70)
        control_bar.setStyleSheet(OLEDStyles.CONTROL_BAR)
        ctrl_layout = QHBoxLayout(control_bar)
        ctrl_layout.setContentsMargins(30, 10, 30, 10)
        ctrl_layout.setSpacing(20)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.prev_btn = QPushButton("◀◀")
        self.prev_btn.setObjectName("CtrlBtn")
        self.play_btn = QPushButton("播放")
        self.play_btn.setObjectName("PlayBtn")
        self.next_btn = QPushButton("▶▶")
        self.next_btn.setObjectName("CtrlBtn")
        btn_row.addWidget(self.prev_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.next_btn)
        ctrl_layout.addLayout(btn_row)

        prog_layout = QVBoxLayout()
        prog_layout.setSpacing(4)
        prog_row = QHBoxLayout()
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: #888888; font-size: 11px;")
        prog_row.addWidget(self.progress, stretch=1)
        prog_row.addSpacing(8)
        prog_row.addWidget(self.time_label)
        prog_layout.addLayout(prog_row)
        ctrl_layout.addLayout(prog_layout, stretch=3)

        vol_row = QHBoxLayout()
        vol_row.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("font-size: 12px; color: #888888;")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setMaximumWidth(100)
        vol_row.addWidget(vol_icon)
        vol_row.addWidget(self.vol_slider)
        ctrl_layout.addLayout(vol_row)

        right_layout.addWidget(control_bar)

        # 下方赏析区
        self.content_area = QWidget()
        self.content_area.setStyleSheet("background-color: #000000;")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(60, 40, 60, 40)
        content_layout.setSpacing(16)

        desc_title = QLabel("歌曲赏析")
        desc_title.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        content_layout.addWidget(desc_title)

        self.desc_label = QLabel("选择一首歌曲，这里将显示对应的歌曲赏析。")
        self.desc_label.setStyleSheet("color: #888888; font-size: 15px; line-height: 1.8;")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self.desc_label)
        content_layout.addStretch()

        right_layout.addWidget(self.content_area, stretch=1)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(right_container, stretch=1)

    def _connect_signals(self):
        self.btn_scan.clicked.connect(self.scan_folder)
        self.song_list.itemClicked.connect(self.on_song_clicked)

        self.play_btn.clicked.connect(self.toggle_play)
        self.prev_btn.clicked.connect(self.prev_song)
        self.next_btn.clicked.connect(self.next_song)
        self.progress.sliderPressed.connect(self.on_slider_pressed)
        self.progress.sliderMoved.connect(self.on_slider_moved)
        self.progress.sliderReleased.connect(self.on_slider_released)
        self.vol_slider.valueChanged.connect(self.change_volume)

        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)

    def on_slider_pressed(self):
        self.is_seeking = True

    def on_slider_moved(self, val):
        if self.player.duration() <= 0:
            return
        # 计算预览位置（毫秒）
        preview_pos = int(val / 1000 * self.player.duration())
        
        # 更新时间标签
        pos_s = preview_pos // 1000
        dur_s = self.player.duration() // 1000
        def fmt(s):
            m, sec = divmod(s, 60)
            return f"{m}:{sec:02d}"
        self.time_label.setText(f"{fmt(pos_s)} / {fmt(dur_s)}")
        
        # 实时更新歌词（预览模式）
        self._update_lyric_display(preview_pos)

    def on_slider_released(self):
        self.is_seeking = False
        if self.player.duration() > 0:
            val = self.progress.value() / 1000
            self.player.setPosition(int(val * self.player.duration()))

    def load_folder(self, folder_path):
        if not os.path.exists(folder_path):
            return
        self.songs = MusicScanner.scan_folder(folder_path)
        self.song_list.clear()
        for song in self.songs:
            text = f"{song.title}\n    {song.artist} — {song.album}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, song)
            item.setSizeHint(QSize(0, 60))
            self.song_list.addItem(item)

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if not folder:
            return
        self.load_folder(folder)

    def on_song_clicked(self, item):
        song = item.data(Qt.ItemDataRole.UserRole)
        self.play_song(song)
        self.current_index = self.song_list.row(item)

    def play_song(self, song):
        self.player.setSource(QUrl.fromLocalFile(song.path))
        self.player.play()
        self.is_playing = True
        self.title_label.setText(str(song.title))
        self.year_label.setText(song.year if song.year else "")
        self.artist_label.setText(f"{song.artist} — {song.album}")
        self.play_btn.setText("暂停")

        # 封面
        if song.cover_pixmap and not song.cover_pixmap.isNull():
            scaled = song.cover_pixmap.scaled(
                80, 80,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_label.setPixmap(scaled)
        else:
            self.cover_label.clear_pixmap()

        self.desc_label.setText(song.description if song.description else "暂无歌曲赏析。")
        self._update_lyric_display(0)

    def toggle_play(self):
        if not self.songs:
            return
        if self.is_playing:
            self.player.pause()
            self.is_playing = False
            self.play_btn.setText("播放")
        else:
            if self.player.source().isEmpty() and self.songs:
                self.play_song(self.songs[0])
                self.current_index = 0
            else:
                self.player.play()
                self.is_playing = True
                self.play_btn.setText("暂停")

    def prev_song(self):
        if not self.songs or self.current_index <= 0:
            return
        self.current_index -= 1
        item = self.song_list.item(self.current_index)
        self.song_list.setCurrentItem(item)
        self.play_song(self.songs[self.current_index])

    def next_song(self):
        if not self.songs:
            return
        if self.current_index < len(self.songs) - 1:
            self.current_index += 1
        else:
            self.current_index = 0
        item = self.song_list.item(self.current_index)
        self.song_list.setCurrentItem(item)
        self.play_song(self.songs[self.current_index])

    def on_position_changed(self, pos):
        # 拖动期间不更新滑块，避免冲突
        if self.is_seeking:
            return
        if self.player.duration() > 0:
            self.progress.setValue(int(pos / self.player.duration() * 1000))
        self._update_lyric_display(pos)

    def on_duration_changed(self, dur):
        self.update_time_label()

    def update_progress(self):
        self.update_time_label()

    def update_time_label(self):
        pos = self.player.position() // 1000
        dur = self.player.duration() // 1000
        def fmt(s):
            m, sec = divmod(s, 60)
            return f"{m}:{sec:02d}"
        self.time_label.setText(f"{fmt(pos)} / {fmt(dur)}")

    def change_volume(self, val):
        normalized = val / 100.0
        actual_volume = normalized ** 2
        self.audio_output.setVolume(actual_volume)

    def _update_lyric_display(self, pos_ms):
        if 0 <= self.current_index < len(self.songs):
            song = self.songs[self.current_index]
            if song.lrc:
                current, next_text = song.lrc.get_lines(pos_ms)
                self.lyric_current.setText(current)
                self.lyric_next.setText(next_text)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    window = MainWindow()
    window.show()
    
    try:
        hwnd = window.winId().__int__()
        set_dark_titlebar(hwnd)
    except Exception:
        pass
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()