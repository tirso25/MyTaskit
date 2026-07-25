#!/usr/bin/env python3

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Static
from textual.binding import Binding
from textual import events, on, work
from dataclasses import dataclass
from typing import Optional, Any
from threading import Lock
import json
import random
import time
from pathlib import Path
from datetime import datetime, date, timedelta
import calendar
import webbrowser
import pyperclip
from PIL import Image
import shutil
from rich_pixels import Pixels
from rich.console import Console
import subprocess
import platform
import os
import warnings
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
warnings.filterwarnings("ignore", category=RuntimeWarning, module="pydub")
from textual.widgets import TextArea

try:
    import sounddevice
    import soundfile
    import numpy
    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False

try:
    import pydub
    _HAS_PYDUB = True
except ImportError:
    _HAS_PYDUB = False

try:
    import just_playback
    _HAS_JUST_PLAYBACK = True
except ImportError:
    _HAS_JUST_PLAYBACK = False

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:
    _HAS_PYGAME = False

(Path.home() / "todo" / "audios").mkdir(exist_ok=True, parents=True)


class UndoableInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history = [self.value]
        self._history_index = 0
        self._last_saved_value = self.value
        self._char_count = 0

    def _is_word_boundary(self, old_val: str, new_val: str) -> bool:
        if not old_val or not new_val:
            return False

        if len(new_val) > len(old_val):
            last_char = new_val[-1]
            return last_char in ' .,;:!?-\n\t'

        if len(old_val) - len(new_val) > 1:
            return True

        return False

    def _save_state(self):
        if self._last_saved_value == self.value:
            return

        is_boundary = self._is_word_boundary(self._last_saved_value, self.value)
        self._char_count += abs(len(self.value) - len(self._last_saved_value))

        if is_boundary or self._char_count >= 20:
            self._history = self._history[:self._history_index + 1]
            self._history.append(self.value)
            self._history_index += 1
            self._last_saved_value = self.value
            self._char_count = 0
            if len(self._history) > 50:
                self._history.pop(0)
                self._history_index -= 1

    def on_input_changed(self, event: Input.Changed) -> None:
        self._save_state()

    def on_key(self, event) -> None:
        if event.key == "ctrl+z":
            event.prevent_default()
            event.stop()
            if self.value != self._history[self._history_index]:
                self._history = self._history[:self._history_index + 1]
                self._history.append(self.value)
                self._history_index += 1
            if self._history_index > 0:
                self._history_index -= 1
                self.value = self._history[self._history_index]
                self._last_saved_value = self.value
                self._char_count = 0
                self.cursor_position = len(self.value)
        elif event.key == "ctrl+y":
            event.prevent_default()
            event.stop()
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.value = self._history[self._history_index]
                self._last_saved_value = self.value
                self._char_count = 0
                self.cursor_position = len(self.value)
        elif event.key == "ctrl+a":
            event.prevent_default()
            event.stop()
            self.cursor_position = 0
            self.selection = (0, len(self.value))
        elif event.key == "ctrl+x":
            event.prevent_default()
            event.stop()
            if self.value:
                try:
                    import pyperclip
                    pyperclip.copy(self.value)
                except:
                    pass
                self.value = ""
                self.cursor_position = 0
        elif event.key == "tab":
            widget_id = getattr(self, "id", "") or ""
            if "search" in widget_id:
                event.prevent_default()
                event.stop()
                self.blur()
                screen = getattr(self, "screen", None)
                if screen and hasattr(screen, "action_blur_search"):
                    screen.action_blur_search()
                elif hasattr(self.app, "action_blur_main_search") and widget_id == "main-search-input":
                    self.app.action_blur_main_search()

    def on_click(self, event: events.Click) -> None:
        widget_id = getattr(self, "id", "") or ""
        if "search" in widget_id:
            screen = getattr(self, "screen", None)
            if screen and hasattr(screen, "_explicit_search_focus"):
                screen._explicit_search_focus = True
            if screen and hasattr(screen, "search_focused"):
                screen.search_focused = True
            if widget_id == "main-search-input":
                if hasattr(self.app, "_explicit_search_focus"):
                    self.app._explicit_search_focus = True
                if hasattr(self.app, "main_search_focused"):
                    self.app.main_search_focused = True

    def on_focus(self, event: events.Focus) -> None:
        widget_id = getattr(self, "id", "") or ""
        if "search" in widget_id:
            screen = getattr(self, "screen", None)
            target = screen if (screen and hasattr(screen, "_explicit_search_focus")) else self.app
            if not getattr(target, "_explicit_search_focus", False):
                self.blur()
                return
            target._explicit_search_focus = False

    def on_blur(self, event: events.Blur) -> None:
        widget_id = getattr(self, "id", "") or ""
        if widget_id == "main-search-input" and hasattr(self.app, "action_blur_main_search"):
            if getattr(self.app, "main_search_query", "") or getattr(self.app, "main_search_focused", False):
                self.app.action_blur_main_search()

class UndoableTextArea(TextArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history = [self.text]
        self._history_index = 0
        self._last_saved_value = self.text
        self._char_count = 0

    def _is_word_boundary(self, old_val: str, new_val: str) -> bool:
        if not old_val or not new_val:
            return False

        if len(new_val) > len(old_val):
            last_char = new_val[-1]
            return last_char in ' .,;:!?-\n\t'

        if len(old_val) - len(new_val) > 1:
            return True

        return False

    def _save_state(self):
        if self._last_saved_value == self.text:
            return

        is_boundary = self._is_word_boundary(self._last_saved_value, self.text)
        self._char_count += abs(len(self.text) - len(self._last_saved_value))

        if is_boundary or self._char_count >= 30:
            self._history = self._history[:self._history_index + 1]
            self._history.append(self.text)
            self._history_index += 1
            self._last_saved_value = self.text
            self._char_count = 0
            if len(self._history) > 50:
                self._history.pop(0)
                self._history_index -= 1

    def on_text_area_changed(self) -> None:
        self._save_state()

    def on_key(self, event) -> None:
        if event.key == "ctrl+z":
            event.prevent_default()
            event.stop()
            if self.text != self._history[self._history_index]:
                self._history = self._history[:self._history_index + 1]
                self._history.append(self.text)
                self._history_index += 1
            if self._history_index > 0:
                self._history_index -= 1
                self.text = self._history[self._history_index]
                self._last_saved_value = self.text
                self._char_count = 0
                try:
                    self.move_cursor_relative(rows=1000, columns=1000)
                except:
                    pass
        elif event.key == "ctrl+y":
            event.prevent_default()
            event.stop()
            if self._history_index < len(self._history) - 1:
                self._history_index += 1
                self.text = self._history[self._history_index]
                self._last_saved_value = self.text
                self._char_count = 0
                try:
                    self.move_cursor_relative(rows=1000, columns=1000)
                except:
                    pass
        elif event.key == "ctrl+a":
            event.prevent_default()
            event.stop()
            self.select_all()
        elif event.key == "ctrl+x":
            event.prevent_default()
            event.stop()
            if self.text:
                try:
                    import pyperclip
                    pyperclip.copy(self.text)
                except:
                    pass
                self.text = ""
                try:
                    self.move_cursor((0, 0))
                except:
                    pass

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS_SEMANA = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]

@dataclass
class Comment:
    id: int
    title: str
    description: str = ""
    url: Optional[str] = None
    image_path: Optional[str] = None
    file_path: Optional[str] = None
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m %H:%M")

@dataclass
class Subtask:
    id: int
    text: str
    done: bool = False
    status: str = "En progreso"
    created_at: str = ""
    due_date: Optional[str] = None
    comments: list = None
    tags: list = None
    priority: int = 0
    notes: list = None
    voice_notes: list = None
    canvas_list: list = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m %H:%M")
        if self.comments is None:
            self.comments = []
        if self.tags is None:
            self.tags = []
        if self.notes is None:
            self.notes = []
        if self.voice_notes is None:
            self.voice_notes = []
        if self.canvas_list is None:
            self.canvas_list = []
        if self.done:
            self.status = "Completado"
        elif self.status == "Completado":
            self.done = True
        elif not self.status:
            self.status = "En progreso"

    def set_status(self, new_status: str) -> None:
        self.status = new_status
        self.done = (new_status == "Completado")

    def toggle_done(self) -> None:
        if self.done:
            self.done = False
            self.status = "En progreso"
        else:
            self.done = True
            self.status = "Completado"

@dataclass
class Tag:
    id: int
    name: str
    created_at: str = ""

    def __post_init__(self):
        self.name = self.name[:30]
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m/%Y %H:%M")

@dataclass
class Note:
    id: int
    title: str
    description: str = ""
    url: Optional[str] = None
    image_path: Optional[str] = None
    file_path: Optional[str] = None
    created_at: str = ""
    tags: list = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        if self.tags is None:
            self.tags = []

@dataclass
class VoiceNote:
    id: int
    title: str
    audio_path: str
    description: str = ""
    duration: float = 0.0
    created_at: str = ""
    tags: list = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        if self.tags is None:
            self.tags = []

class AudioRecorder:
    def __init__(self, samplerate=44100, channels=1):
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._stream = None
        self.recording = False
        self.device = self._get_best_input_device()

    def _get_best_input_device(self):
        if not _HAS_SOUNDDEVICE:
            return None
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            candidates = []
            for i, d in enumerate(devices):
                if d.get("max_input_channels", 0) > 0:
                    name = d.get("name", "").lower()
                    score = 0
                    if "varios" in name or "realtek" in name:
                        score += 50
                    if "micrófono" in name or "microfono" in name:
                        score += 10
                    if "jabra" in name or "epos" in name:
                        score -= 30
                    candidates.append((score, i))

            candidates.sort(key=lambda x: x[0], reverse=True)
            if candidates:
                return candidates[0][1]

            return sd.default.device[0]
        except Exception:
            return None

    def _callback(self, indata, frames, time_info, status):
        if self.recording:
            self._frames.append(indata.copy())

    def start(self):
        if not _HAS_SOUNDDEVICE:
            return
        import sounddevice as sd
        self._frames = []
        self.recording = True
        self.device = self._get_best_input_device()
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            device=self.device,
            callback=self._callback
        )
        self._stream.start()

    def cancel(self):
        self.recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._frames = []

    def stop_and_export(self, mp3_path: str) -> float:
        self.recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if not self._frames or not _HAS_SOUNDDEVICE:
            return 0.0
        import numpy as np
        import soundfile as sf
        data = np.concatenate(self._frames, axis=0)
        if _HAS_PYDUB:
            try:
                from pydub import AudioSegment
                tmp_wav = mp3_path + ".tmp.wav"
                sf.write(tmp_wav, data, self.samplerate)
                AudioSegment.from_wav(tmp_wav).export(mp3_path, format="mp3", bitrate="128k")
                if os.path.exists(tmp_wav):
                    try: os.remove(tmp_wav)
                    except Exception: pass
                return len(data) / self.samplerate
            except Exception:
                pass
        try:
            sf.write(mp3_path, data, self.samplerate)
            return len(data) / self.samplerate
        except Exception as e:
            print(f"Error al exportar audio: {e}")
            return 0.0

class AudioPlayer:
    """play/pause/resume/stop/seek + posición/duración, con degradación."""
    def __init__(self):
        self._backend = None
        self._pb = None
        self.duration = 0.0
        self._sd_data = None
        self._sd_samplerate = 44100
        self._start_time = None
        self._pause_offset = 0.0
        self._is_playing = False
        self._is_paused = False

    def load(self, path: str) -> bool:
        if _HAS_SOUNDDEVICE:
            try:
                import soundfile as sf
                data, fs = sf.read(path)
                self._sd_data = data
                self._sd_samplerate = fs
                self.duration = len(data) / float(fs)
                self._start_time = None
                self._pause_offset = 0.0
                self._is_playing = False
                self._is_paused = False
                self._backend = "sounddevice"
                return True
            except Exception as e:
                print(f"sounddevice load warning: {e}")

        if _HAS_JUST_PLAYBACK:
            try:
                from just_playback import Playback
                self._pb = Playback()
                self._pb.load_file(path)
                self.duration = self._pb.duration
                self._backend = "just"
                return True
            except Exception:
                pass
        if _HAS_PYGAME:
            try:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(path)
                if _HAS_PYDUB:
                    try:
                        from pydub import AudioSegment
                        self.duration = len(AudioSegment.from_file(path)) / 1000.0
                    except Exception:
                        self.duration = 0.0
                self._backend = "pygame"
                return True
            except Exception:
                pass
        return False

    def play(self):
        if self._backend == "sounddevice" and self._sd_data is not None:
            import sounddevice as sd
            start_frame = int(self._pause_offset * self._sd_samplerate)
            if start_frame < len(self._sd_data):
                sd.play(self._sd_data[start_frame:], self._sd_samplerate)
            self._start_time = datetime.now()
            self._is_playing = True
            self._is_paused = False
        elif self._backend == "just" and self._pb:
            self._pb.play()
        elif self._backend == "pygame":
            import pygame
            pygame.mixer.music.play()

    def pause(self):
        if self._backend == "sounddevice" and self._is_playing:
            import sounddevice as sd
            sd.stop()
            if self._start_time:
                self._pause_offset += (datetime.now() - self._start_time).total_seconds()
            self._is_playing = False
            self._is_paused = True
        elif self._backend == "just" and self._pb:
            self._pb.pause()
        elif self._backend == "pygame":
            import pygame
            pygame.mixer.music.pause()

    def resume(self):
        if self._backend == "sounddevice" and self._is_paused:
            self.play()
        elif self._backend == "just" and self._pb:
            self._pb.resume()
        elif self._backend == "pygame":
            import pygame
            pygame.mixer.music.unpause()

    def stop(self):
        if self._backend == "sounddevice":
            import sounddevice as sd
            sd.stop()
            self._is_playing = False
            self._is_paused = False
            self._pause_offset = 0.0
            self._start_time = None
        elif self._backend == "just" and self._pb:
            self._pb.stop()
        elif self._backend == "pygame":
            import pygame
            pygame.mixer.music.stop()

    def seek(self, sec: float):
        target = max(0.0, min(self.duration, sec))
        if self._backend == "sounddevice":
            was_playing = self._is_playing
            if was_playing:
                import sounddevice as sd
                sd.stop()
            self._pause_offset = target
            if was_playing:
                self.play()
        elif self._backend == "just" and self._pb:
            self._pb.seek(target)

    @property
    def position(self) -> float:
        if self._backend == "sounddevice":
            if self._is_playing and self._start_time:
                pos = self._pause_offset + (datetime.now() - self._start_time).total_seconds()
                return min(self.duration, pos)
            return min(self.duration, self._pause_offset)
        elif self._backend == "just" and self._pb:
            return self._pb.curr_pos
        elif self._backend == "pygame":
            import pygame
            pos_ms = pygame.mixer.music.get_pos()
            return pos_ms / 1000.0 if pos_ms >= 0 else 0.0
        return 0.0

    @property
    def is_playing(self) -> bool:
        if self._backend == "sounddevice":
            return self._is_playing and self.position < self.duration
        elif self._backend == "just" and self._pb:
            return self._pb.playing
        elif self._backend == "pygame":
            import pygame
            return pygame.mixer.music.get_busy()
        return False

@dataclass
class Canvas:
    id: int
    title: str
    width: int = 50
    height: int = 20
    grid: list = None
    created_at: str = ""
    tags: list = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        if self.grid is None:
            self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        if self.tags is None:
            self.tags = []

@dataclass
class Task:
    id: int
    text: str
    done: bool = False
    status: str = "En progreso"
    created_at: str = ""
    group_id: Optional[int] = None
    due_date: Optional[str] = None
    comments: list = None
    tags: list = None
    priority: int = 0
    subtasks: list = None
    notes: list = None
    voice_notes: list = None
    canvas_list: list = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        if self.comments is None:
            self.comments = []
        if self.tags is None:
            self.tags = []
        if self.subtasks is None:
            self.subtasks = []
        if self.notes is None:
            self.notes = []
        if self.voice_notes is None:
            self.voice_notes = []
        if self.canvas_list is None:
            self.canvas_list = []
        if self.done:
            self.status = "Completado"
        elif self.status == "Completado":
            self.done = True
        elif not self.status:
            self.status = "En progreso"

    def set_status(self, new_status: str) -> None:
        self.status = new_status
        self.done = (new_status == "Completado")

    def toggle_done(self) -> None:
        if self.done:
            self.done = False
            self.status = "En progreso"
        else:
            self.done = True
            self.status = "Completado"

@dataclass
class Group:
    id: int
    name: str

class SubtasksModal(ModalScreen[list]):
    DEFAULT_CSS = """
    SubtasksModal { align: center middle; }
    SubtasksModal > VerticalScroll {
        width: 90; height: 38; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    SubtasksModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    SubtasksModal #search-input { width: 100%; margin-bottom: 1; }
    SubtasksModal #filter-status { width: 100%; height: 1; text-align: center; color: $accent; margin-bottom: 1; }
    SubtasksModal #subtasks-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    SubtasksModal .subtask-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        layout: horizontal;
    }
    SubtasksModal .subtask-item:hover { background: $boost; }
    SubtasksModal .subtask-item.selected { border: solid $accent; background: $surface-lighten-1; }
    SubtasksModal .subtask-item.done .subtask-text { text-style: strike; color: $text-muted; }
    SubtasksModal .subtask-checkbox { width: 4; height: 1; }
    SubtasksModal .subtask-priority { width: 3; height: 1; }
    SubtasksModal .urgent-indicator { width: 3; height: 1; color: $warning; text-style: bold; }
    SubtasksModal .subtask-text { width: 1fr; height: 1; }
    SubtasksModal .tag { background: #90EE90; color: #000000; }
    SubtasksModal .tag-separator { width: 1; }
    SubtasksModal .subtask-links { width: 4; height: 1; text-align: right; color: $accent; }
    SubtasksModal .subtask-images { width: 4; height: 1; text-align: right; color: $primary; }
    SubtasksModal .subtask-files { width: 4; height: 1; text-align: right; color: $warning; }
    SubtasksModal .subtask-comments { width: 5; height: 1; text-align: right; color: $primary; }
    SubtasksModal .subtask-date { width: 8; height: 1; text-align: right; color: $warning; }
    SubtasksModal .subtask-item.done .subtask-priority { color: $text-muted; }
    SubtasksModal .subtask-item.done .subtask-comments { color: $text-muted; }
    SubtasksModal .subtask-item.done .subtask-links { color: $text-muted; }
    SubtasksModal .subtask-item.done .subtask-images { color: $text-muted; }
    SubtasksModal .subtask-item.done .subtask-files { color: $text-muted; }
    SubtasksModal .subtask-item.done .subtask-date { color: $text-muted; }
    SubtasksModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    SubtasksModal .hint { width: 100%; height: auto; text-align: center; color: $text-muted; margin: 1 0; padding: 0 2; }
    SubtasksModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    SubtasksModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("a", "add_subtask", show=False),
        Binding("e", "edit_subtask", show=False),
        Binding("d", "delete_subtask", show=False),
        Binding("space", "toggle_subtask", show=False),
        Binding("f", "filter_subtasks", show=False),
        Binding("f5", "reset_filters", show=False),
        Binding("ctrl+f", "focus_search", show=False),
        Binding("/", "focus_search", show=False),
        Binding("tab", "blur_search", show=False),
    ]

    def __init__(self, subtasks: list, next_subtask_id: int, next_comment_id: int,
                 all_tags: list = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.subtasks = [Subtask(id=s.id, text=s.text, done=s.done,
                                created_at=s.created_at, due_date=s.due_date,
                                comments=s.comments if hasattr(s, 'comments') else [],
                                tags=s.tags if hasattr(s, 'tags') else [],
                                priority=s.priority if hasattr(s, 'priority') else 0,
                                notes=getattr(s, 'notes', []),
                                voice_notes=getattr(s, 'voice_notes', []),
                                canvas_list=getattr(s, 'canvas_list', []))
                        for s in subtasks]
        self.next_subtask_id = next_subtask_id
        self.next_comment_id = next_comment_id
        self.all_tags = all_tags or []
        self.selected_index = 0 if subtasks else -1
        self.search_query = ""
        self.search_focused = False
        self.filter_dates: list[str] = []
        self.filter_tag_ids: list[int] = []
        self.filter_statuses: list[str] = []
        self.filter_priorities: list[int] = []
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📋 Subtareas", classes="modal-title")
            yield UndoableInput(placeholder="🔍 Buscar subtareas (/) ...", id="search-input")
            yield Label("", id="filter-status")
            yield Container(id="subtasks-list")
            yield Label(
                "↑↓/k/j: Navegar | a: Añadir | e: Editar | d: Eliminar | /: Buscar | Tab: Salir búsqueda\n"
                "f: Filtrar | F5: Reset filtros | Espacio: Completar | Esc: Cerrar",
                classes="hint"
            )
            with Horizontal(classes="button-row"):
                yield Button("➕ Añadir", variant="primary", id="add")
                yield Button("✏️ Editar", variant="default", id="edit")
                yield Button("🗑️ Eliminar", variant="error", id="delete")
    
    async def on_mount(self) -> None:
        await self.refresh_subtasks_list()
        try:
            self.query_one("#search-input", Input).blur()
        except:
            pass

    def _filter_subtasks(self) -> list[Subtask]:
        filtered = self.subtasks

        if self.search_query:
            query_lower = self.search_query.lower()
            filtered = [s for s in filtered if query_lower in s.text.lower()]

        if self.filter_statuses:
            res = []
            for s in filtered:
                st = getattr(s, "status", "Completado" if s.done else "En progreso")
                if "completed" in self.filter_statuses and (s.done or st == "Completado"):
                    res.append(s)
                elif "in_progress" in self.filter_statuses and (not s.done and st == "En progreso"):
                    res.append(s)
                elif "on_hold" in self.filter_statuses and (not s.done and st == "En espera"):
                    res.append(s)
                elif "pending" in self.filter_statuses and not s.done:
                    res.append(s)
                elif "done" in self.filter_statuses and s.done:
                    res.append(s)
            filtered = res

        if self.filter_tag_ids:
            filtered = [s for s in filtered if s.tags and any(tag_id in s.tags for tag_id in self.filter_tag_ids)]

        if self.filter_priorities:
            filtered = [s for s in filtered if s.priority in self.filter_priorities]

        if self.filter_dates:
            filtered = [s for s in filtered if s.due_date in self.filter_dates]

        return filtered

    def _update_filter_status(self) -> None:
        filter_parts = []

        if self.search_query:
            filter_parts.append(f"🔍 '{self.search_query}'")

        if self.filter_statuses:
            if "done" in self.filter_statuses and "pending" not in self.filter_statuses:
                filter_parts.append("✅ Completadas")
            elif "pending" in self.filter_statuses and "done" not in self.filter_statuses:
                filter_parts.append("⏳ Pendientes")

        if self.filter_tag_ids:
            tag_names = []
            for tag_id in self.filter_tag_ids:
                tag = next((t for t in self.all_tags if t.id == tag_id), None)
                if tag:
                    tag_names.append(tag.name)
            if tag_names:
                filter_parts.append(f"🏷️ {', '.join(tag_names)}")

        if self.filter_priorities:
            priority_icons = {0: "Sin prioridad", 1: "🟢 Baja", 2: "🟡 Media", 3: "🔴 Alta"}
            priorities_str = ", ".join([priority_icons.get(p, "") for p in self.filter_priorities])
            filter_parts.append(f"⚡ {priorities_str}")

        if self.filter_dates:
            dates_str = ", ".join([d.split('-')[2] + "/" + d.split('-')[1] for d in self.filter_dates])
            filter_parts.append(f"📅 {dates_str}")

        filter_status_label = self.query_one("#filter-status", Label)
        if filter_parts:
            filter_status_label.update(f"Filtros activos: {' | '.join(filter_parts)}")
        else:
            filter_status_label.update("")

    def _get_ordered_subtasks(self) -> list[Subtask]:
        filtered = self._filter_subtasks()
        in_progress = [s for s in filtered if not s.done and getattr(s, 'status', 'En progreso') == 'En progreso']
        on_hold = [s for s in filtered if not s.done and getattr(s, 'status', 'En progreso') == 'En espera']
        completed = [s for s in filtered if s.done or getattr(s, 'status', 'En progreso') == 'Completado']
        return in_progress + on_hold + completed

    async def _render_subtask_row(self, subtask: Subtask, widget_id: str, is_selected: bool, container: Container) -> None:
        item = Horizontal(id=widget_id, classes="subtask-item")
        await container.mount(item)

        checkbox = "☑" if subtask.done else "☐"
        await item.mount(Label(checkbox, classes="subtask-checkbox"))

        priority_icons = {0: "  ", 1: "[green]■[/green]", 2: "[yellow]■[/yellow]", 3: "[red]■[/red]"}
        await item.mount(Label(priority_icons.get(subtask.priority, "  "), classes="subtask-priority"))

        urgent_icon = ""
        if not subtask.done and subtask.due_date:
            try:
                due_date_obj = datetime.strptime(subtask.due_date, "%Y-%m-%d").date()
                if due_date_obj == date.today():
                    urgent_icon = "⚠️ "
            except: pass
        await item.mount(Label(urgent_icon, classes="urgent-indicator"))

        await item.mount(Label(subtask.text, classes="subtask-text"))

        if subtask.tags:
            for tag_id in subtask.tags:
                tag = next((t for t in self.all_tags if t.id == tag_id), None)
                if tag:
                    tag_name = tag.name[:10] if len(tag.name) > 10 else tag.name
                    await item.mount(Label(f" {tag_name} ", classes="tag"))
                    await item.mount(Label(" ", classes="tag-separator"))

        links_count = sum(1 for c in subtask.comments if c.url)
        await item.mount(Label(f"🔗 {links_count}" if links_count > 0 else "", classes="subtask-links"))

        images_count = sum(1 for c in subtask.comments if c.image_path)
        await item.mount(Label(f"📷 {images_count}" if images_count > 0 else "", classes="subtask-images"))

        files_count = sum(1 for c in subtask.comments if c.file_path)
        await item.mount(Label(f"📎 {files_count}" if files_count > 0 else "", classes="subtask-files"))

        notes_count = len(getattr(subtask, 'notes', []))
        await item.mount(Label(f"📝 {notes_count}" if notes_count > 0 else "", classes="subtask-notes"))

        audios_count = len(getattr(subtask, 'voice_notes', []))
        await item.mount(Label(f"🎤 {audios_count}" if audios_count > 0 else "", classes="subtask-audios"))

        canvas_count = len(getattr(subtask, 'canvas_list', []))
        await item.mount(Label(f"🎨 {canvas_count}" if canvas_count > 0 else "", classes="subtask-canvas"))

        comments_count = len(subtask.comments)
        await item.mount(Label(f"💬 {comments_count}" if comments_count > 0 else "", classes="subtask-comments"))

        date_str = ""
        if subtask.due_date:
            try:
                d = datetime.strptime(subtask.due_date, "%Y-%m-%d")
                date_str = f"{d.day:02d}/{d.month:02d}"
            except: pass
        await item.mount(Label(date_str, classes="subtask-date"))

        if subtask.done:
            item.add_class("done")

        if is_selected:
            item.add_class("selected")

    async def refresh_subtasks_list(self) -> None:
        subtasks_list = self.query_one("#subtasks-list", Container)
        await subtasks_list.remove_children()

        self._update_filter_status()

        filtered_subtasks = self._filter_subtasks()
        ordered_subtasks = self._get_ordered_subtasks()

        if not self.subtasks:
            await subtasks_list.mount(Label("No hay subtareas. Pulsa 'a' para añadir una.", classes="empty-msg"))
            self.selected_index = -1
        elif not filtered_subtasks:
            await subtasks_list.mount(Label("No hay subtareas que coincidan con los filtros", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(ordered_subtasks):
                self.selected_index = max(0, len(ordered_subtasks) - 1)

            in_progress = [s for s in filtered_subtasks if not s.done and getattr(s, 'status', 'En progreso') == 'En progreso']
            on_hold = [s for s in filtered_subtasks if not s.done and getattr(s, 'status', 'En progreso') == 'En espera']
            completed = [s for s in filtered_subtasks if s.done or getattr(s, 'status', 'En progreso') == 'Completado']

            if in_progress:
                await subtasks_list.mount(Static("── En progreso ──", id="in-progress-separator"))
                for s in in_progress:
                    idx = filtered_subtasks.index(s)
                    is_sel = (ordered_subtasks.index(s) == self.selected_index)
                    await self._render_subtask_row(s, f"subtask-{idx}", is_sel, subtasks_list)

            if on_hold:
                await subtasks_list.mount(Static("── En espera ──", id="on-hold-separator"))
                for s in on_hold:
                    idx = filtered_subtasks.index(s)
                    is_sel = (ordered_subtasks.index(s) == self.selected_index)
                    await self._render_subtask_row(s, f"subtask-{idx}", is_sel, subtasks_list)

            if completed:
                await subtasks_list.mount(Static("── Completadas ──", id="completed-separator"))
                for s in completed:
                    idx = filtered_subtasks.index(s)
                    is_sel = (ordered_subtasks.index(s) == self.selected_index)
                    await self._render_subtask_row(s, f"subtask-{idx}", is_sel, subtasks_list)

            self.scroll_to_selected()
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            ordered = self._get_ordered_subtasks()
            if 0 <= self.selected_index < len(ordered):
                subtask = ordered[self.selected_index]
                filtered = self._filter_subtasks()
                if subtask in filtered:
                    orig_idx = filtered.index(subtask)
                    try:
                        item = self.query_one(f"#subtask-{orig_idx}", Horizontal)
                        item.scroll_visible()
                    except: pass
    
    def update_selection(self) -> None:
        filtered = self._filter_subtasks()
        ordered = self._get_ordered_subtasks()
        for idx, subtask in enumerate(ordered):
            try:
                orig_idx = filtered.index(subtask)
                item = self.query_one(f"#subtask-{orig_idx}", Horizontal)
                item.set_class(idx == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()

    def action_move_up(self) -> None:
        if self.search_focused:
            return
        ordered = self._get_ordered_subtasks()
        if ordered and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.search_focused:
            return
        ordered = self._get_ordered_subtasks()
        if ordered and self.selected_index < len(ordered) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_add_subtask(self) -> None:
        if self.search_focused:
            return
        def on_result(text: Optional[str]) -> None:
            if text:
                subtask = Subtask(id=self.next_subtask_id, text=text)
                self.next_subtask_id += 1
                self.subtasks.append(subtask)
                self.selected_index = len(self.subtasks) - 1
                self.call_later(self.refresh_subtasks_list)
        self.app.push_screen(InputModal("📋 Nueva Subtarea", placeholder="Descripción..."), on_result)
    
    def action_edit_subtask(self) -> None:
        if self.search_focused:
            return
        ordered = self._get_ordered_subtasks()
        if not ordered or self.selected_index < 0 or self.selected_index >= len(ordered):
            return
        subtask = ordered[self.selected_index]

        next_comment_id = self.next_comment_id
        if subtask.comments:
            next_comment_id = max(c.id for c in subtask.comments) + 1

        def on_result(result: Optional[dict]) -> None:
            if result:
                subtask.text = result["text"]
                if "status" in result:
                    subtask.set_status(result["status"])
                subtask.comments = result.get("comments", [])
                subtask.tags = result.get("tags", [])
                subtask.priority = result.get("priority", 0)
                subtask.due_date = result.get("due_date", "")
                subtask.notes = result.get("notes", [])
                subtask.voice_notes = result.get("voice_notes", [])
                subtask.canvas_list = result.get("canvas_list", [])
                if subtask.comments:
                    self.next_comment_id = max(c.id for c in subtask.comments) + 1
                self.call_later(self.refresh_subtasks_list)

        self.app.push_screen(
            EditSubtaskModal(subtask.text, subtask.comments, next_comment_id,
                           all_tags=self.all_tags, selected_tags=subtask.tags,
                           priority=subtask.priority, due_date=subtask.due_date,
                           notes=getattr(subtask, 'notes', []),
                           voice_notes=getattr(subtask, 'voice_notes', []),
                           canvas_list=getattr(subtask, 'canvas_list', []),
                           global_notes=getattr(self.app, 'notes', []),
                           global_voice_notes=getattr(self.app, 'voice_notes', []),
                           global_canvas_list=getattr(self.app, 'canvas_list', []),
                           status=getattr(subtask, 'status', 'En progreso')),
            on_result
        )
    
    def action_delete_subtask(self) -> None:
        if self.search_focused:
            return
        ordered = self._get_ordered_subtasks()
        if not ordered or self.selected_index < 0 or self.selected_index >= len(ordered):
            return
        subtask = ordered[self.selected_index]
        txt = subtask.text[:30] + "..." if len(subtask.text) > 30 else subtask.text
        def on_confirm(yes: bool) -> None:
            if yes:
                self.subtasks.remove(subtask)
                ordered = self._get_ordered_subtasks()
                if self.selected_index >= len(ordered) and self.selected_index > 0:
                    self.selected_index -= 1
                if not self.subtasks:
                    self.selected_index = -1
                self.call_later(self.refresh_subtasks_list)
        self.app.push_screen(ConfirmModal(f"¿Eliminar subtarea '{txt}'?"), on_confirm)

    def action_toggle_subtask(self) -> None:
        if self.search_focused:
            return
        ordered = self._get_ordered_subtasks()
        if not ordered or self.selected_index < 0 or self.selected_index >= len(ordered):
            return
        subtask = ordered[self.selected_index]
        subtask.done = not subtask.done
        self.call_later(self.refresh_subtasks_list)

    def action_filter_subtasks(self) -> None:
        if self.search_focused:
            return
        def on_result(filters: Optional[dict]) -> None:
            if filters is not None:
                self.filter_dates = filters.get("dates", [])
                self.filter_tag_ids = filters.get("tag_ids", [])
                self.filter_statuses = filters.get("statuses", [])
                self.filter_priorities = filters.get("priorities", [])
                self.selected_index = 0
                self.call_later(self.refresh_subtasks_list)

        unique_dates = sorted(set(s.due_date for s in self.subtasks if s.due_date))

        self.app.push_screen(
            FilterModal(
                current_date_filters=self.filter_dates,
                current_tag_filters=self.filter_tag_ids,
                current_status_filters=self.filter_statuses,
                current_priority_filters=self.filter_priorities,
                all_tags=self.all_tags,
                available_dates=unique_dates,
                title="🔍 Filtrar Subtareas"
            ),
            on_result
        )

    def action_reset_filters(self) -> None:
        self.search_query = ""
        self.filter_statuses = []
        self.filter_tag_ids = []
        self.filter_priorities = []
        self.filter_dates = []
        try:
            self.query_one("#search-input", Input).value = ""
        except: pass
        self.selected_index = 0
        self.call_later(self.refresh_subtasks_list)

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_subtasks_list)

    @on(Input.Changed, "#search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_subtasks_list()

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_close(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(self.subtasks)
    
    @on(Button.Pressed, "#add")
    def on_add(self) -> None:
        self.action_add_subtask()
    
    @on(Button.Pressed, "#edit")
    def on_edit(self) -> None:
        self.action_edit_subtask()
    
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None:
        self.action_delete_subtask()
    
    def action_close(self) -> None:
        self.dismiss(self.subtasks)

class UnscheduledItemsModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    UnscheduledItemsModal { align: center middle; }
    UnscheduledItemsModal > VerticalScroll {
        width: 80; height: 36; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    UnscheduledItemsModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    UnscheduledItemsModal .search-label { color: $text-muted; margin-bottom: 0; }
    UnscheduledItemsModal Input { width: 100%; margin-bottom: 1; }
    UnscheduledItemsModal .info-text { width: 100%; text-align: center; color: $text-muted; margin-bottom: 1; }
    UnscheduledItemsModal #items-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    UnscheduledItemsModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    UnscheduledItemsModal .item:hover { background: $boost; }
    UnscheduledItemsModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    UnscheduledItemsModal .item.checked { color: $success; }
    UnscheduledItemsModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    UnscheduledItemsModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    UnscheduledItemsModal .button-row { width: 100%; height: 3; align: center middle; }
    UnscheduledItemsModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_item", show=False),
        Binding("enter", "save", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
        Binding("/", "focus_search", show=False),
    ]
    
    def __init__(self, tasks: list[Task], all_groups: list[Group], **kwargs) -> None:
        super().__init__(**kwargs)
        self.all_groups = all_groups
        self.all_items = []
        
        for task in tasks:
            if task.due_date is None and not task.done:
                group_name = self._get_group_name(task.group_id)
                self.all_items.append(("task", task.id, None, task.text, group_name))
            
            for subtask in task.subtasks:
                if subtask.due_date is None and not subtask.done:
                    self.all_items.append(("subtask", task.id, subtask.id, subtask.text, task.text))
        
        self.selected_item_ids = []
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_items = []
        self.selected_index = 0 if self.all_items else -1

    def _get_filtered_items(self) -> list:
        if not self.search_query:
            return self.all_items
        q = self.search_query.lower()
        return [item for item in self.all_items if q in item[3].lower() or (item[4] and q in item[4].lower())]

    def _get_group_name(self, group_id: Optional[int]) -> str:
        if group_id is None:
            return "Sin grupo"
        group = next((g for g in self.all_groups if g.id == group_id), None)
        return group.name if group else "Sin grupo"

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📅 Asignar fecha desde calendario", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar tareas/subtareas...", id="ui-search-input")
            yield Container(id="items-list")
            yield Label("↑↓ Navegar | Espacio: Marcar/Desmarcar | /: Buscar | Enter: Asignar fecha | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Asignar fecha", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#ui-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        items_list = self.query_one("#items-list", Container)
        await items_list.remove_children()
        
        self.filtered_items = self._get_filtered_items()
        
        if not self.all_items:
            await items_list.mount(Label("No hay tareas ni subtareas sin fecha pendientes", classes="empty-msg"))
            self.selected_index = -1
            return
        elif not self.filtered_items:
            await items_list.mount(Label(f"No se encontraron elementos para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
            return
        
        if self.selected_index >= len(self.filtered_items) or self.selected_index < 0:
            self.selected_index = 0
            
        for i, item_data in enumerate(self.filtered_items):
            item_type, task_id, subtask_id, text, extra_info = item_data
            item_key = (task_id, subtask_id)
            checked = "☑" if item_key in self.selected_item_ids else "☐"
            
            if item_type == "task":
                prefix = "📋 Tarea:"
                extra = f" 📁 {extra_info}"
            else:
                prefix = "└─ 📋 Subtarea:"
                extra = f" (Tarea: {extra_info[:25]}...)" if len(extra_info) > 25 else f" (Tarea: {extra_info})"
            
            truncated_text = text[:35] + "..." if len(text) > 35 else text
            display_text = f"{checked}  {prefix} {truncated_text}{extra}"
            
            item_widget = Static(display_text, id=f"item-{i}", classes="item")
            await items_list.mount(item_widget)
            if item_key in self.selected_item_ids:
                item_widget.add_class("checked")
            if i == self.selected_index:
                item_widget.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#ui-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#ui-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#ui-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#ui-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.filtered_items and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.filtered_items and self.selected_index < len(self.filtered_items) - 1:
            self.selected_index += 1
            self.update_selection()

    def action_toggle_item(self) -> None:
        if self.search_focused: return
        if self.filtered_items and 0 <= self.selected_index < len(self.filtered_items):
            item_data = self.filtered_items[self.selected_index]
            item_key = (item_data[1], item_data[2])
            if item_key in self.selected_item_ids:
                self.selected_item_ids.remove(item_key)
            else:
                self.selected_item_ids.append(item_key)
            self.call_later(self.refresh_list)

    def update_selection(self) -> None:
        for i in range(len(self.filtered_items)):
            try:
                item = self.query_one(f"#item-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except Exception: pass

    def action_save(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        selected_tasks = []
        selected_subtasks = []
        for task_id, subtask_id in self.selected_item_ids:
            if subtask_id is None:
                selected_tasks.append(task_id)
            else:
                selected_subtasks.append((task_id, subtask_id))
        self.dismiss({"task_ids": selected_tasks, "subtask_ids": selected_subtasks})

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.action_cancel()
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()
        
class DayItemsModal(ModalScreen[Optional[tuple]]):
    DEFAULT_CSS = """
    DayItemsModal { align: center middle; }
    DayItemsModal > VerticalScroll {
        width: 80; height: 26; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    DayItemsModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    DayItemsModal .section-header { 
        width: 100%; 
        text-align: left; 
        text-style: bold; 
        color: $accent;
        margin: 1 0;
        padding: 0 1;
    }
    DayItemsModal #items-list { width: 100%; height: 1fr; overflow-y: auto; }
    DayItemsModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        layout: horizontal;
    }
    DayItemsModal .item:hover { background: $boost; }
    DayItemsModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    DayItemsModal .item-main { width: 1fr; height: 1; }
    DayItemsModal .item-info { width: auto; height: 1; text-align: right; color: $text-muted; }
    DayItemsModal .hint { width: 100%; text-align: center; color: $text-muted; margin-top: 1; }
    DayItemsModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "go_to_item", show=False),
        Binding("enter", "go_to_item", show=False),
    ]
    
    def __init__(self, tasks: list[tuple], subtasks: list[tuple], date_str: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tasks = tasks
        self.subtasks = subtasks
        self.date_str = date_str
        self.all_items = []
        
        for task, group_name in tasks:
            self.all_items.append(("task", task, group_name))
        for subtask, parent_task, group_name in subtasks:
            self.all_items.append(("subtask", (subtask, parent_task), group_name))
        
        self.selected_index = 0 if self.all_items else -1
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(f"📅 {self.date_str}", classes="modal-title")
            yield Container(id="items-list")
            yield Label("↑↓ Navegar | Espacio/Enter: Ir a la tarea | Esc: Cerrar", classes="hint")
    
    async def on_mount(self) -> None:
        items_list = self.query_one("#items-list", Container)
        
        if not self.all_items:
            await items_list.mount(Label("No hay tareas ni subtareas para este día", classes="empty-msg"))
            return
        
        current_index = 0
        
        if self.tasks:
            await items_list.mount(Static("📋 Tareas:", classes="section-header"))
            for task, group_name in self.tasks:
                checkbox = "☑" if task.done else "☐"
                item = Horizontal(id=f"item-{current_index}", classes="item")
                await items_list.mount(item)
                
                await item.mount(Label(f"{checkbox} {task.text}", classes="item-main"))
                await item.mount(Label(f"📁 {group_name}", classes="item-info"))
                
                if current_index == self.selected_index:
                    item.add_class("selected")
                current_index += 1
        
        if self.subtasks:
            await items_list.mount(Static("📝 Subtareas:", classes="section-header"))
            for subtask, parent_task, group_name in self.subtasks:
                checkbox = "☑" if subtask.done else "☐"
                parent_text = parent_task.text[:25] + "..." if len(parent_task.text) > 25 else parent_task.text
                item = Horizontal(id=f"item-{current_index}", classes="item")
                await items_list.mount(item)
                
                await item.mount(Label(f"{checkbox} ↳ {subtask.text}", classes="item-main"))
                await item.mount(Label(f"🔗 {parent_text}", classes="item-info"))
                
                if current_index == self.selected_index:
                    item.add_class("selected")
                current_index += 1
    
    def update_selection(self) -> None:
        for i in range(len(self.all_items)):
            try:
                item = self.query_one(f"#item-{i}", Horizontal)
                item.set_class(i == self.selected_index, "selected")
            except: pass
    
    def action_move_up(self) -> None:
        if self.all_items and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.all_items and self.selected_index < len(self.all_items) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_go_to_item(self) -> None:
        if self.all_items and self.selected_index >= 0:
            item_type, item_obj, info = self.all_items[self.selected_index]
            if item_type == "task":
                self.dismiss(("task", item_obj))
            else:
                subtask, parent_task = item_obj
                self.dismiss(("subtask", parent_task))
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class SubtaskReminderModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    SubtaskReminderModal { align: center middle; }
    SubtaskReminderModal > VerticalScroll {
        width: 50; height: auto; max-height: 20; border: thick $warning;
        background: $surface; padding: 1 2;
    }
    SubtaskReminderModal .modal-title { 
        text-align: center; text-style: bold; 
        width: 100%; height: auto;
        color: $warning;
        margin-bottom: 1;
    }
    SubtaskReminderModal .subtask-info {
        width: 100%; height: auto;
        padding: 1;
        background: $surface-lighten-1;
        border: solid $primary-background;
        margin-bottom: 1;
    }
    SubtaskReminderModal .subtask-text { 
        width: 100%; height: auto;
        text-align: center;
        margin: 0 0 1 0;
    }
    SubtaskReminderModal .parent-info {
        width: 100%; height: auto;
        text-align: center;
        color: $text-muted;
        margin-bottom: 0;
    }
    SubtaskReminderModal .button-row { 
        width: 100%; height: auto; 
        align: center middle;
        margin-top: 1;
    }
    SubtaskReminderModal Button { margin: 0 1; }
    """
    
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("enter", "close", show=False),
        Binding("space", "close", show=False),
    ]
    
    def __init__(self, subtask: Subtask, parent_text: str, group_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.subtask_data = subtask
        self.parent_text = parent_text
        self.group_name = group_name
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("⏰ Recordatorio de Subtarea", classes="modal-title")
            with Container(classes="subtask-info"):
                yield Label("La siguiente subtarea vence HOY:", classes="parent-info")
                yield Label(f"↳ {self.subtask_data.text}", classes="subtask-text")
                yield Label(f"🔗 Tarea: {self.parent_text}", classes="parent-info")
                yield Label(f"📁 Grupo: {self.group_name}", classes="parent-info")
            with Horizontal(classes="button-row"):
                yield Button("Entendido", variant="primary", id="ok")
    
    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self.dismiss(True)
    
    def action_close(self) -> None:
        self.dismiss(True)
    
    def on_key(self, event) -> None:
        if event.key not in ["escape", "enter", "space"]:
            event.prevent_default()
            event.stop()

class ImageViewerModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ImageViewerModal { align: center middle; }
    ImageViewerModal > VerticalScroll {
        width: 95%; 
        height: 95%; 
        border: thick $primary;
        background: $surface; 
        padding: 1;
    }
    ImageViewerModal .modal-title { 
        text-align: center; 
        text-style: bold; 
        width: 100%; 
        margin-bottom: 1; 
    }
    ImageViewerModal #image-container { 
        width: 100%; 
        height: 1fr; 
        overflow: auto;
        border: solid $primary-background;
        padding: 1;
        align: center middle;
        content-align: center middle;
    }
    ImageViewerModal .info-text {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    ImageViewerModal .button-row { 
        width: 100%; 
        height: auto; 
        align: center middle; 
        margin-top: 1;
    }
    ImageViewerModal Button { margin: 0 1; }
    """
    
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("q", "close", show=False),
        Binding("o", "open_external", "Abrir externa", show=True),
    ]
    
    def __init__(self, image_path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.image_path = image_path
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(f"📷 {Path(self.image_path).name}", classes="modal-title")
            yield Static(id="image-container")
            yield Static("", id="info-text", classes="info-text")
            with Horizontal(classes="button-row"):
                yield Button("📂 Abrir externa", variant="default", id="open")
                yield Button("Cerrar", variant="primary", id="close")
    
    def on_mount(self) -> None:
        image_static = self.query_one("#image-container", Static)
        info_static = self.query_one("#info-text", Static)
        
        term = os.environ.get('TERM', '').lower()
        term_program = os.environ.get('TERM_PROGRAM', '').lower()
        
        if 'kitty' in term or term_program == 'kitty':
            if self._try_kitty_protocol(image_static):
                info_static.update("✨ Kitty Protocol (calidad perfecta)")
                return
        
        if term_program == 'iterm.app':
            if self._try_iterm2_protocol(image_static):
                info_static.update("✨ iTerm2 Protocol (calidad perfecta)")
                return
        
        if self._terminal_supports_sixel():
            if self._try_sixel(image_static):
                info_static.update("✨ Sixel Protocol (alta calidad)")
                return
        
        if self._try_chafa(image_static):
            info_static.update("✨ Chafa (alta calidad)")
            return
        
        if self._try_rich_pixels(image_static):
            info_static.update("🎨 Vista previa básica (Presiona 'o' para alta calidad)")
            return
        
        image_static.update(
            f"📷 {Path(self.image_path).name}\n\n"
            f"Presiona 'o' o el botón 'Abrir externa'\n"
            f"para ver la imagen\n\n"
            f"Ruta: {self.image_path}"
        )
        info_static.update("ℹ️ Vista previa no disponible")
    
    def _terminal_supports_sixel(self) -> bool:
        term = os.environ.get('TERM', '').lower()
        return any(x in term for x in ['mlterm', 'mintty']) or \
               ('xterm' in term and shutil.which('img2sixel'))
    
    def _try_kitty_protocol(self, widget: Static) -> bool:
        try:
            from base64 import b64encode
            
            img = Image.open(self.image_path)
            max_size = (800, 600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            import io
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_data = buffer.getvalue()
            
            b64_data = b64encode(img_data).decode('ascii')
            kitty_cmd = f"\033_Ga=T,f=100;{b64_data}\033\\"
            
            from rich.text import Text
            widget.update(Text.from_ansi(kitty_cmd))
            return True
            
        except Exception:
            return False
    
    def _try_iterm2_protocol(self, widget: Static) -> bool:
        try:
            from base64 import b64encode
            
            with open(self.image_path, 'rb') as f:
                img_data = f.read()
            
            b64_data = b64encode(img_data).decode('ascii')
            iterm_cmd = f"\033]1337;File=inline=1:{b64_data}\007"
            
            from rich.text import Text
            widget.update(Text.from_ansi(iterm_cmd))
            return True
            
        except Exception:
            return False
    
    def _try_sixel(self, widget: Static) -> bool:
        if not shutil.which('img2sixel'):
            return False
        
        try:
            terminal_size = shutil.get_terminal_size()
            width = min(800, (terminal_size.columns - 10) * 8)
            
            result = subprocess.run(
                ['img2sixel', '-w', str(width), self.image_path],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                from rich.text import Text
                widget.update(Text.from_ansi(result.stdout.decode('utf-8', errors='ignore')))
                return True
                
        except Exception:
            pass
        
        return False
    
    def _try_chafa(self, widget: Static) -> bool:
        if not shutil.which('chafa'):
            return False
        
        try:
            terminal_size = shutil.get_terminal_size()
            width = min(100, terminal_size.columns - 10)
            height = min(50, terminal_size.lines - 15)
            
            result = subprocess.run(
                [
                    'chafa',
                    '--size', f'{width}x{height}',
                    '--format', 'symbols',
                    '--symbols', 'all',
                    '--color-space', 'rgb',
                    '--dither', 'none',
                    '--optimize', '9',
                    self.image_path
                ],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='utf-8'
            )
            
            if result.returncode == 0 and result.stdout:
                from rich.text import Text
                widget.update(Text.from_ansi(result.stdout))
                return True
        except Exception:
            pass
        
        return False
    
    def _try_rich_pixels(self, widget: Static) -> bool:
        try:
            terminal_size = shutil.get_terminal_size()

            target_width = min(60, terminal_size.columns - 20)
            target_height = min(30, terminal_size.lines - 10)
            
            pixels = Pixels.from_image_path(
                self.image_path,
                resize=(target_width, target_height)
            )
            
            widget.update(pixels)
            return True
            
        except Exception as e:
            return False
    
    def action_open_external(self) -> None:
        self._open_external()
    
    @on(Button.Pressed, "#open")
    def on_open_btn(self) -> None:
        self._open_external()
    
    def _open_external(self) -> None:
        system = platform.system()
        
        try:
            if system == 'Windows':
                subprocess.Popen(['start', '', self.image_path], shell=True)
                self.app.notify("📂 Abriendo imagen...", severity="information")
                
            elif system == 'Darwin':
                try:
                    subprocess.Popen(['open', self.image_path], 
                                   stderr=subprocess.PIPE)
                    self.app.notify("📂 Abriendo imagen...", severity="information")
                except:
                    self._open_with_ranger()
                
            elif system == 'Linux':
                if self._try_gui_viewer():
                    self.app.notify("📂 Abriendo imagen...", severity="information")
                else:
                    self._open_with_ranger()
            
        except Exception as e:
            self.app.notify(f"❌ Error: {str(e)}", severity="error")
            self._open_with_ranger()
    
    def _try_gui_viewer(self) -> bool:
        viewers = ['xdg-open', 'eog', 'feh', 'gwenview', 'display', 'gthumb', 'ristretto']
        
        for viewer in viewers:
            if shutil.which(viewer):
                try:
                    subprocess.Popen(
                        [viewer, self.image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return True
                except:
                    continue
        
        return False
    
    def _open_with_ranger(self) -> None:
        if shutil.which('ranger'):
            try:
                self.app.notify("📁 Abriendo con Ranger...", severity="information")
                
                self.app.exit()
                
                subprocess.run(['ranger', '--selectfile', self.image_path])
                
            except Exception as e:
                print(f"Error al abrir Ranger: {e}")
        else:
            self.app.notify(
                "⚠️ No hay visor gráfico ni Ranger disponible",
                severity="warning",
                timeout=3
            )
            self.app.notify(
                f"📁 Ruta: {self.image_path}",
                severity="information",
                timeout=10
            )
    
    @on(Button.Pressed, "#close")
    def on_close_btn(self) -> None:
        self.dismiss(True)
    
    def action_close(self) -> None:
        self.dismiss(True)

class EditSubtaskModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    EditSubtaskModal { align: center middle; }
    EditSubtaskModal > VerticalScroll {
        width: 78; height: auto; max-height: 90%; border: thick $primary;
        background: $surface; padding: 1 2; overflow-y: auto;
    }
    EditSubtaskModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    EditSubtaskModal .section-label { margin-top: 1; color: $text-muted; }
    EditSubtaskModal Input { width: 100%; margin-bottom: 1; }
    EditSubtaskModal .info-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditSubtaskModal .info-display { width: 1fr; padding: 0 1; }
    EditSubtaskModal .comments-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditSubtaskModal .comments-display { width: 1fr; padding: 0 1; }
    EditSubtaskModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    EditSubtaskModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]

    def __init__(self, subtask_text: str, comments: list[Comment] = None,
                 next_comment_id: int = 1, all_tags: list = None,
                 selected_tags: list = None, priority: int = 0, due_date: str = "",
                 notes: list[Note] = None, voice_notes: list[VoiceNote] = None, canvas_list: list[Canvas] = None,
                 next_note_id: int = 1, next_voice_note_id: int = 1, next_canvas_id: int = 1,
                 global_notes: list = None, global_voice_notes: list = None, global_canvas_list: list = None,
                 status: str = "En progreso", **kwargs) -> None:
        super().__init__(**kwargs)
        self.subtask_text = subtask_text
        self.comments = comments or []
        self.next_comment_id = next_comment_id
        self.all_tags = all_tags or []
        self.selected_tags = selected_tags or []
        self.priority = priority
        self.due_date = due_date
        self.notes = list(notes) if notes else []
        self.voice_notes = list(voice_notes) if voice_notes else []
        self.canvas_list = list(canvas_list) if canvas_list else []
        self.next_note_id = next_note_id
        self.next_voice_note_id = next_voice_note_id
        self.next_canvas_id = next_canvas_id
        self.global_notes = global_notes or []
        self.global_voice_notes = global_voice_notes or []
        self.global_canvas_list = global_canvas_list or []
        self.status = status if status in ("En progreso", "En espera", "Completado") else "En progreso"
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("✏️ Editar Subtarea", classes="modal-title")
            yield Label("Texto:", classes="section-label")
            yield UndoableInput(value=self.subtask_text, id="subtask-input")

            yield Label("Estado:", classes="section-label")
            with Horizontal(classes="info-row"):
                yield Label(self._format_status(), id="status-display", classes="info-display")
                yield Button("🔄 Cambiar", id="manage-status")

            yield Label("Etiquetas:", classes="section-label")
            with Horizontal(classes="info-row"):
                yield Label(self._format_tags(), id="tags-display", classes="info-display")
                yield Button("🏷️ Editar", id="manage-tags")

            yield Label("Prioridad:", classes="section-label")
            with Horizontal(classes="info-row"):
                yield Label(self._format_priority(), id="priority-display", classes="info-display")
                yield Button("⚡ Cambiar", id="manage-priority")

            yield Label("Fecha límite:", classes="section-label")
            with Horizontal(classes="info-row"):
                yield Label(self._format_due_date(), id="due-date-display", classes="info-display")
                yield Button("📅 Cambiar", id="manage-due-date")

            yield Label("Comentarios:", classes="section-label")
            with Horizontal(classes="comments-row"):
                yield Label(self._format_comments(), id="comments-display", classes="comments-display")
                yield Button("💬 Gestionar", id="manage-comments")

            yield Label("Notas:", classes="section-label")
            with Horizontal(classes="info-row"):
                yield Label(self._format_notes(), id="notes-display", classes="info-display")
                yield Button("📌 Seleccionar", id="select-notes")

            yield Label("Audios:", classes="section-label")
            with Horizontal(classes="info-row"):
                yield Label(self._format_voice_notes(), id="voice-notes-display", classes="info-display")
                yield Button("📌 Seleccionar", id="select-voice-notes")

            yield Label("Pizarras:", classes="section-label")
            with Horizontal(classes="info-row"):
                yield Label(self._format_canvas(), id="canvas-display", classes="info-display")
                yield Button("📌 Seleccionar", id="select-canvas")

            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    def _format_status(self) -> str:
        icons = {"En progreso": "🔄 En progreso", "En espera": "⏳ En espera", "Completado": "✅ Completado"}
        return icons.get(self.status, "🔄 En progreso")

    @on(Button.Pressed, "#manage-status")
    def on_manage_status(self) -> None:
        def on_result(res: Optional[str]) -> None:
            if res:
                self.status = res
                self.query_one("#status-display", Label).update(self._format_status())
        self.app.push_screen(StatusPickerModal(self.status), on_result)
    
    def _format_tags(self) -> str:
        if not self.selected_tags:
            return "Sin etiquetas"
        tag_names = []
        for tag_id in self.selected_tags:
            tag = next((t for t in self.all_tags if t.id == tag_id), None)
            if tag:
                tag_names.append(tag.name)
        if not tag_names:
            return "Sin etiquetas"
        return " | ".join(tag_names)

    def _format_priority(self) -> str:
        if self.priority == 0:
            return "Sin prioridad"
        priority_names = {1: "🟢 Baja", 2: "🟡 Media", 3: "🔴 Alta"}
        return priority_names.get(self.priority, "Sin prioridad")

    def _format_due_date(self) -> str:
        if not self.due_date:
            return "Sin fecha"
        return f"📅 {self.due_date}"

    def _format_comments(self) -> str:
        count = len(self.comments)
        if count == 0:
            return "Sin comentarios"
        elif count == 1:
            return "💬 1 comentario"
        else:
            return f"💬 {count} comentarios"

    def _format_notes(self) -> str:
        count = len(self.notes)
        if count == 0: return "Sin notas"
        elif count == 1: return "📝 1 nota"
        else: return f"📝 {count} notas"

    def _format_voice_notes(self) -> str:
        count = len(self.voice_notes)
        if count == 0: return "Sin audios"
        elif count == 1: return "🎤 1 audio"
        else: return f"🎤 {count} audios"

    def _format_canvas(self) -> str:
        count = len(self.canvas_list)
        if count == 0: return "Sin pizarras"
        elif count == 1: return "🎨 1 pizarra"
        else: return f"🎨 {count} pizarras"

    def on_mount(self) -> None:
        self.query_one("#subtask-input", Input).focus()

    @on(Button.Pressed, "#manage-tags")
    def on_manage_tags(self) -> None:
        def on_result(selected_tag_ids: list[int]) -> None:
            if selected_tag_ids is not None:
                self.selected_tags = selected_tag_ids
                self.query_one("#tags-display", Label).update(self._format_tags())
        self.app.push_screen(TagPickerModal(self.all_tags, self.selected_tags), on_result)

    @on(Button.Pressed, "#manage-priority")
    def on_manage_priority(self) -> None:
        def on_result(priority: Optional[int]) -> None:
            if priority is not None:
                self.priority = priority
                self.query_one("#priority-display", Label).update(self._format_priority())
        self.app.push_screen(PriorityPickerModal(self.priority), on_result)

    @on(Button.Pressed, "#manage-due-date")
    def on_manage_due_date(self) -> None:
        def on_result(date_str: Optional[str]) -> None:
            if date_str is not None:
                self.due_date = date_str
                self.query_one("#due-date-display", Label).update(self._format_due_date())
        self.app.push_screen(DatePickerModal(self.due_date), on_result)

    @on(Button.Pressed, "#manage-comments")
    def on_manage_comments(self) -> None:
        def on_result(updated_comments: list[Comment]) -> None:
            self.comments = updated_comments
            if self.comments:
                self.next_comment_id = max(c.id for c in self.comments) + 1
            self.query_one("#comments-display", Label).update(self._format_comments())
        self.app.push_screen(CommentsModal(self.comments, self.next_comment_id), on_result)

    @on(Button.Pressed, "#select-notes")
    def on_select_notes(self) -> None:
        def on_result(result: Optional[list[Note]]) -> None:
            if result is not None:
                self.notes = result
                if self.notes:
                    self.next_note_id = max((n.id for n in self.notes), default=0) + 1
                self.query_one("#notes-display", Label).update(self._format_notes())
        global_notes = self.global_notes or getattr(self.app, "notes", [])
        current_ids = [n.id for n in self.notes]
        self.app.push_screen(GlobalNotesPickerModal(global_notes, selected_note_ids=current_ids), on_result)

    @on(Button.Pressed, "#select-voice-notes")
    def on_select_voice_notes(self) -> None:
        def on_result(result: Optional[list[VoiceNote]]) -> None:
            if result is not None:
                self.voice_notes = result
                if self.voice_notes:
                    self.next_voice_note_id = max((v.id for v in self.voice_notes), default=0) + 1
                self.query_one("#voice-notes-display", Label).update(self._format_voice_notes())
        global_vn = self.global_voice_notes or getattr(self.app, "voice_notes", [])
        current_ids = [v.id for v in self.voice_notes]
        self.app.push_screen(GlobalVoiceNotesPickerModal(global_vn, selected_vn_ids=current_ids), on_result)

    @on(Button.Pressed, "#select-canvas")
    def on_select_canvas(self) -> None:
        def on_result(result: Optional[list[Canvas]]) -> None:
            if result is not None:
                self.canvas_list = result
                if self.canvas_list:
                    self.next_canvas_id = max((c.id for c in self.canvas_list), default=0) + 1
                self.query_one("#canvas-display", Label).update(self._format_canvas())
        global_canvas = self.global_canvas_list or getattr(self.app, "canvas_list", [])
        current_ids = [c.id for c in self.canvas_list]
        self.app.push_screen(GlobalCanvasPickerModal(global_canvas, selected_canvas_ids=current_ids), on_result)

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.action_save()

    def action_save(self) -> None:
        text = self.query_one("#subtask-input", Input).value.strip()
        if not text:
            self.app.notify("El texto de la subtarea no puede estar vacío", severity="warning")
            return

        self.dismiss({
            "text": text,
            "status": self.status,
            "comments": self.comments,
            "tags": self.selected_tags,
            "priority": self.priority,
            "due_date": self.due_date,
            "notes": self.notes,
            "voice_notes": self.voice_notes,
            "canvas_list": self.canvas_list
        })
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Input.Submitted)
    def on_submit(self) -> None:
        self.on_save()
    
    def action_cancel(self) -> None:
        self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()

class SubtaskRowWidget(Static):
    DEFAULT_CSS = """
    SubtaskRowWidget {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    SubtaskRowWidget:hover { background: $boost; }
    SubtaskRowWidget.selected { border: solid $accent; background: $surface-lighten-1; }
    SubtaskRowWidget.done .subtask-text { text-style: strike; color: $text-muted; }
    SubtaskRowWidget .subtask-checkbox { width: 4; height: 1; }
    SubtaskRowWidget .subtask-priority { width: 3; height: 1; }
    SubtaskRowWidget .subtask-parent { width: auto; max-width: 25; height: 1; color: $accent; margin-right: 1; text-style: bold; }
    SubtaskRowWidget .subtask-text { width: 1fr; height: 1; }
    SubtaskRowWidget .subtask-notes { width: 5; height: 1; text-align: right; color: $success; }
    SubtaskRowWidget .subtask-audios { width: 5; height: 1; text-align: right; color: $primary; }
    SubtaskRowWidget .subtask-canvas { width: 5; height: 1; text-align: right; color: $warning; }
    SubtaskRowWidget .subtask-comments { width: 5; height: 1; text-align: right; color: $primary; }
    SubtaskRowWidget .subtask-date { width: 8; height: 1; text-align: right; color: $warning; }
    SubtaskRowWidget .subtask-status { width: 14; height: 1; text-align: right; color: $accent; }
    SubtaskRowWidget.done .subtask-status { color: $text-muted; }
    """

    def __init__(self, subtask: Subtask, parent_task: Task = None, all_tags: list = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.subtask = subtask
        self.parent_task = parent_task
        self.all_tags = all_tags or []
        self._selected = False

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        self.set_class(value, "selected")

    def compose(self) -> ComposeResult:
        checkbox = "☑" if self.subtask.done else "☐"
        yield Label(checkbox, classes="subtask-checkbox")

        priority_icons = {0: "  ", 1: "[green]■[/green]", 2: "[yellow]■[/yellow]", 3: "[red]■[/red]"}
        yield Label(priority_icons.get(self.subtask.priority, "  "), classes="subtask-priority")

        if self.parent_task:
            p_txt = self.parent_task.text[:18] + "..." if len(self.parent_task.text) > 18 else self.parent_task.text
            yield Label(f"📁 {p_txt}: ", classes="subtask-parent")

        yield Label(self.subtask.text, classes="subtask-text")

        if self.subtask.tags:
            for tag_id in self.subtask.tags:
                tag = next((t for t in self.all_tags if t.id == tag_id), None)
                if tag:
                    t_name = tag.name[:10] if len(tag.name) > 10 else tag.name
                    yield Label(f" {t_name} ", classes="tag")
                    yield Label(" ", classes="tag-separator")

        notes_count = len(getattr(self.subtask, 'notes', []))
        yield Label(f"📝{notes_count}" if notes_count > 0 else "", classes="subtask-notes")

        audios_count = len(getattr(self.subtask, 'voice_notes', []))
        yield Label(f"🎤{audios_count}" if audios_count > 0 else "", classes="subtask-audios")

        canvas_count = len(getattr(self.subtask, 'canvas_list', []))
        yield Label(f"🎨{canvas_count}" if canvas_count > 0 else "", classes="subtask-canvas")

        comments_count = len(self.subtask.comments)
        yield Label(f"💬{comments_count}" if comments_count > 0 else "", classes="subtask-comments")

        date_str = ""
        if self.subtask.due_date:
            try:
                d = datetime.strptime(self.subtask.due_date, "%Y-%m-%d")
                date_str = f"{d.day:02d}/{d.month:02d}"
            except: pass
        yield Label(date_str, classes="subtask-date")

        st_text = "⏳ En espera" if getattr(self.subtask, "status", "") == "En espera" else ("✅ Completado" if self.subtask.done else "🔄 En progreso")
        yield Label(st_text, classes="subtask-status")

    def on_mount(self) -> None:
        if self.subtask.done:
            self.add_class("done")

    def toggle_done(self) -> None:
        self.subtask.toggle_done()
        self.set_class(self.subtask.done, "done")
        try:
            checkbox_label = self.query_one(".subtask-checkbox", Label)
            checkbox_label.update("☑" if self.subtask.done else "☐")
            status_label = self.query_one(".subtask-status", Label)
            status_label.update("✅ Completado" if self.subtask.done else "🔄 En progreso")
        except Exception:
            pass

class TaskWidget(Static):
    DEFAULT_CSS = """
    TaskWidget {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    TaskWidget:hover { background: $boost; }
    TaskWidget.selected {
        border: solid $accent;
        background: $surface-lighten-1;
    }
    TaskWidget .checkbox { width: 4; height: 1; }
    TaskWidget .priority { width: 3; height: 1; }
    TaskWidget .urgent-indicator {
        width: 3; 
        height: 1; 
        color: $warning;
        text-style: bold;
    }
    TaskWidget .task-text { width: 1fr; height: 1; }
    TaskWidget .tag { background: #90EE90; color: #000000; }
    TaskWidget .tag-separator { width: 1; }
    TaskWidget .task-subtasks { width: 7; height: 1; text-align: right; color: $accent; }
    TaskWidget .task-links { width: 4; height: 1; text-align: right; color: $accent; }
    TaskWidget .task-images { width: 4; height: 1; text-align: right; color: $primary; }
    TaskWidget .task-files { width: 4; height: 1; text-align: right; color: $warning; }
    TaskWidget .task-comments { width: 5; height: 1; text-align: right; color: $primary; }
    TaskWidget .task-notes { width: 5; height: 1; text-align: right; color: $accent; }
    TaskWidget .task-audios { width: 5; height: 1; text-align: right; color: $success; }
    TaskWidget .task-group { width: 20; height: 1; text-align: right; color: $text-muted; }
    TaskWidget .task-date { width: 8; height: 1; text-align: right; color: $warning; }
    TaskWidget .task-time { width: 17; height: 1; text-align: right; color: $text-muted; }
    TaskWidget .task-status { width: 14; height: 1; text-align: right; color: $accent; }
    TaskWidget.done .task-status { color: $text-muted; }
    TaskWidget.done .task-text { text-style: strike; color: $text-muted; }
    TaskWidget.done .checkbox { color: $success; }
    TaskWidget.done .task-date { color: $text-muted; }
    TaskWidget.done .task-comments { color: $text-muted; }
    TaskWidget.done .task-notes { color: $text-muted; }
    TaskWidget.done .task-audios { color: $text-muted; }
    TaskWidget.done .task-links { color: $text-muted; }
    TaskWidget.done .task-images { color: $text-muted; }
    TaskWidget.done .task-files { color: $text-muted; }
    TaskWidget.done .task-subtasks { color: $text-muted; }
    TaskWidget.done .task-group { color: $text-muted; }
    TaskWidget.done .priority { color: $text-muted; }
    """
    
    def __init__(self, task_data: Task, all_tags: list[Tag] = None, all_groups: list[Group] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.task_data = task_data
        self.all_tags = all_tags or []
        self.all_groups = all_groups or []
        self._selected = False
    
    def compose(self) -> ComposeResult:
        checkbox = "☑" if self.task_data.done else "☐"
        yield Label(checkbox, classes="checkbox")
        
        priority_icons = {
            0: "  ",
            1: "[green]■[/green]",
            2: "[yellow]■[/yellow]",
            3: "[red]■[/red]"
        }
        priority_icon = priority_icons.get(self.task_data.priority, "  ")
        yield Label(priority_icon, classes="priority")
        
        urgent_icon = ""
        if not self.task_data.done and self.task_data.due_date:
            try:
                due_date = datetime.strptime(self.task_data.due_date, "%Y-%m-%d").date()
                if due_date == date.today():
                    urgent_icon = "⚠️ "
            except: pass
        yield Label(urgent_icon, classes="urgent-indicator")
        
        yield Label(self.task_data.text, classes="task-text")
        
        if self.task_data.tags:
            for tag_id in self.task_data.tags:
                tag = next((t for t in self.all_tags if t.id == tag_id), None)
                if tag:
                    tag_name = tag.name[:10] if len(tag.name) > 10 else tag.name
                    yield Label(f" {tag_name} ", classes="tag")
                    yield Label(" ", classes="tag-separator")
        
        if self.task_data.subtasks:
            done_count = sum(1 for s in self.task_data.subtasks if s.done)
            total_count = len(self.task_data.subtasks)
            subtasks_str = f"📋 {done_count}/{total_count}"
        else:
            subtasks_str = ""
        yield Label(subtasks_str, classes="task-subtasks")
        
        links_count = sum(1 for c in self.task_data.comments if c.url)
        links_str = f"🔗 {links_count}" if links_count > 0 else ""
        yield Label(links_str, classes="task-links")

        images_count = sum(1 for c in self.task_data.comments if c.image_path)
        images_str = f"📷 {images_count}" if images_count > 0 else ""
        yield Label(images_str, classes="task-images")

        files_count = sum(1 for c in self.task_data.comments if c.file_path)
        files_str = f"📎 {files_count}" if files_count > 0 else ""
        yield Label(files_str, classes="task-files")

        comments_str = f"💬 {len(self.task_data.comments)}" if self.task_data.comments else ""
        yield Label(comments_str, classes="task-comments")

        notes_str = f"📝 {len(self.task_data.notes)}" if self.task_data.notes else ""
        yield Label(notes_str, classes="task-notes")

        audios_str = f"🎤 {len(self.task_data.voice_notes)}" if self.task_data.voice_notes else ""
        yield Label(audios_str, classes="task-audios")

        canvas_list = getattr(self.task_data, 'canvas_list', None)
        canvas_str = f"🎨 {len(canvas_list)}" if canvas_list else ""
        yield Label(canvas_str, classes="task-notes")
        
        group_str = self._format_group_name()
        yield Label(group_str, classes="task-group")
        
        date_str = ""
        if self.task_data.due_date:
            try:
                d = datetime.strptime(self.task_data.due_date, "%Y-%m-%d")
                date_str = f"📅 {d.day:02d}/{d.month:02d}"
            except: pass
        yield Label(date_str, classes="task-date")
        yield Label(format_datetime_display(self.task_data.created_at), classes="task-time")
        status_str = "⏳ En espera" if getattr(self.task_data, "status", "") == "En espera" else ("✅ Completado" if self.task_data.done else "🔄 En progreso")
        yield Label(status_str, classes="task-status")
    
    def _format_group_name(self) -> str:
        if self.task_data.group_id is None:
            return "Grupo: Sin grupo "
        
        group = next((g for g in self.all_groups if g.id == self.task_data.group_id), None)
        if group:
            group_name = group.name[:12] if len(group.name) > 12 else group.name
            return f"Grupo: {group_name} "
        return "Grupo: Sin grupo "
    
    @property
    def selected(self) -> bool:
        return self._selected
    
    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        self.set_class(value, "selected")
    
    def toggle_done(self) -> None:
        self.task_data.toggle_done()
        self.set_class(self.task_data.done, "done")
        try:
            self.query_one(".checkbox", Label).update("☑" if self.task_data.done else "☐")
            self.query_one(".task-status", Label).update("✅ Completado" if self.task_data.done else "🔄 En progreso")
        except Exception:
            pass
    
    def on_mount(self) -> None:
        if self.task_data.done:
            self.add_class("done")

    def on_click(self) -> None:
        if self.app and hasattr(self.app, "_select_task_by_data"):
            self.app._select_task_by_data(self.task_data)

def format_datetime_display(dt_str: str) -> str:
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        pass

    try:
        dt = datetime.strptime(dt_str, "%d/%m/%Y %H:%M")
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        pass

    try:
        dt = datetime.strptime(dt_str, "%d/%m %H:%M")
        dt = dt.replace(year=datetime.now().year)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        pass

    return dt_str


class NoteWidget(Static):
    DEFAULT_CSS = """
    NoteWidget {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    NoteWidget:hover { background: $boost; }
    NoteWidget.selected {
        border: solid $accent;
        background: $surface-lighten-1;
    }
    NoteWidget .note-icon { width: 4; height: 1; }
    NoteWidget .note-title { width: 1fr; height: 1; }
    NoteWidget .tag { background: #90EE90; color: #000000; }
    NoteWidget .tag-separator { width: 1; }
    NoteWidget .note-link { width: 4; height: 1; text-align: right; color: $accent; }
    NoteWidget .note-image { width: 4; height: 1; text-align: right; color: $primary; }
    NoteWidget .note-file { width: 4; height: 1; text-align: right; color: $warning; }
    NoteWidget .note-time { width: 17; height: 1; text-align: right; color: $text-muted; }
    """

    def __init__(self, note_data: Note, all_tags: list[Tag] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.note_data = note_data
        self.all_tags = all_tags or []
        self._selected = False

    def compose(self) -> ComposeResult:
        yield Label("📝", classes="note-icon")
        yield Label(self.note_data.title, classes="note-title")

        if self.note_data.tags:
            for tag_id in self.note_data.tags:
                tag = next((t for t in self.all_tags if t.id == tag_id), None)
                if tag:
                    tag_name = tag.name[:10] if len(tag.name) > 10 else tag.name
                    yield Label(f" {tag_name} ", classes="tag")
                    yield Label(" ", classes="tag-separator")

        link_str = "🔗" if self.note_data.url else ""
        yield Label(link_str, classes="note-link")

        image_str = "📷" if self.note_data.image_path else ""
        yield Label(image_str, classes="note-image")

        file_str = "📎" if self.note_data.file_path else ""
        yield Label(file_str, classes="note-file")

        yield Label(format_datetime_display(self.note_data.created_at), classes="note-time")

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        self.set_class(value, "selected")

    def on_click(self) -> None:
        if self.app and hasattr(self.app, "_select_note_by_data"):
            self.app._select_note_by_data(self.note_data)

class VoiceNoteWidget(Static):
    DEFAULT_CSS = """
    VoiceNoteWidget {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    VoiceNoteWidget:hover { background: $boost; }
    VoiceNoteWidget.selected {
        border: solid $accent;
        background: $surface-lighten-1;
    }
    VoiceNoteWidget .vn-icon { width: 4; height: 1; }
    VoiceNoteWidget .vn-title { width: 1fr; height: 1; }
    VoiceNoteWidget .tag { background: #90EE90; color: #000000; }
    VoiceNoteWidget .tag-separator { width: 1; }
    VoiceNoteWidget .vn-duration { width: 10; height: 1; text-align: right; color: $accent; }
    VoiceNoteWidget .vn-audio { width: 4; height: 1; text-align: right; color: $success; }
    VoiceNoteWidget .vn-time { width: 12; height: 1; text-align: right; color: $text-muted; }
    """

    def __init__(self, voice_note_data: VoiceNote, all_tags: list[Tag] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.voice_note_data = voice_note_data
        self.all_tags = all_tags or []
        self._selected = False

    def compose(self) -> ComposeResult:
        yield Label("🎤", classes="vn-icon")
        yield Label(self.voice_note_data.title, classes="vn-title")

        if self.voice_note_data.tags:
            for tag_id in self.voice_note_data.tags:
                tag = next((t for t in self.all_tags if t.id == tag_id), None)
                if tag:
                    tag_name = tag.name[:10] if len(tag.name) > 10 else tag.name
                    yield Label(f" {tag_name} ", classes="tag")
                    yield Label(" ", classes="tag-separator")

        dur = int(self.voice_note_data.duration)
        mins, secs = divmod(dur, 60)
        dur_str = f"🎵 {mins:02d}:{secs:02d}" if self.voice_note_data.duration > 0 else ""
        yield Label(dur_str, classes="vn-duration")

        audio_str = "🔊" if self.voice_note_data.audio_path else ""
        yield Label(audio_str, classes="vn-audio")

        yield Label(format_datetime_display(self.voice_note_data.created_at), classes="vn-time")

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        self.set_class(value, "selected")

    def on_click(self) -> None:
        if self.app and hasattr(self.app, "_select_voice_note_by_data"):
            self.app._select_voice_note_by_data(self.voice_note_data)

class CanvasWidget(Static):
    DEFAULT_CSS = """
    CanvasWidget {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    CanvasWidget:hover { background: $boost; }
    CanvasWidget.selected {
        border: solid $accent;
        background: $surface-lighten-1;
    }
    CanvasWidget .canvas-icon { width: 4; height: 1; }
    CanvasWidget .canvas-title { width: 1fr; height: 1; }
    CanvasWidget .tag { background: #90EE90; color: #000000; }
    CanvasWidget .tag-separator { width: 1; }
    CanvasWidget .canvas-size { width: 12; height: 1; text-align: right; color: $text-muted; }
    CanvasWidget .canvas-time { width: 17; height: 1; text-align: right; color: $text-muted; }
    """

    def __init__(self, canvas_data: Canvas, all_tags: list[Tag] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.canvas_data = canvas_data
        self.all_tags = all_tags or []
        self._selected = False

    def compose(self) -> ComposeResult:
        yield Label("🎨", classes="canvas-icon")
        yield Label(self.canvas_data.title, classes="canvas-title")

        if self.canvas_data.tags:
            for tag_id in self.canvas_data.tags:
                tag = next((t for t in self.all_tags if t.id == tag_id), None)
                if tag:
                    tag_name = tag.name[:10] if len(tag.name) > 10 else tag.name
                    yield Label(f" {tag_name} ", classes="tag")
                    yield Label(" ", classes="tag-separator")

        size_str = f"{self.canvas_data.width}x{self.canvas_data.height}"
        yield Label(size_str, classes="canvas-size")

        yield Label(format_datetime_display(self.canvas_data.created_at), classes="canvas-time")

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        self.set_class(value, "selected")

    def on_click(self) -> None:
        if self.app and hasattr(self.app, "_select_canvas_by_data"):
            self.app._select_canvas_by_data(self.canvas_data)


class TagWidget(Static):
    DEFAULT_CSS = """
    TagWidget {
        width: 100%;
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
        margin-bottom: 1;
        layout: horizontal;
    }
    TagWidget:hover { background: $boost; }
    TagWidget.selected {
        border: solid $accent;
        background: $surface-lighten-1;
    }
    TagWidget .tag-icon { width: 4; height: 1; }
    TagWidget .tag-name { width: 1fr; height: 1; text-style: bold; color: #90EE90; }
    TagWidget .tag-count { width: 20; height: 1; text-align: right; color: $text-muted; }
    TagWidget .tag-time { width: 17; height: 1; text-align: right; color: $text-muted; }
    """

    def __init__(self, tag_data: Tag, task_count: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tag_data = tag_data
        self.task_count = task_count
        self._selected = False

    def compose(self) -> ComposeResult:
        yield Label("🏷️", classes="tag-icon")
        yield Label(self.tag_data.name, classes="tag-name")
        count_str = f"{self.task_count} tarea(s)"
        yield Label(count_str, classes="tag-count")
        yield Label(format_datetime_display(self.tag_data.created_at), classes="tag-time")

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        if value:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    def on_click(self) -> None:
        if self.app and hasattr(self.app, "_select_tag_by_data"):
            self.app._select_tag_by_data(self.tag_data)

class CanvasEditorModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    CanvasEditorModal { align: center middle; }
    CanvasEditorModal > VerticalScroll {
        width: 90%; max-width: 120; height: 90%;
        border: thick $primary;
        background: $surface; padding: 1 2;
    }
    CanvasEditorModal .modal-title {
        text-align: center; text-style: bold;
        width: 100%; margin-bottom: 1;
    }
    CanvasEditorModal .section-label {
        margin-top: 1; margin-bottom: 0;
        color: $text-muted;
    }
    CanvasEditorModal #title-input {
        width: 100%;
        margin-bottom: 1;
    }
    CanvasEditorModal .tools-row {
        width: 100%; height: auto;
        align: left middle; margin-bottom: 1;
        layout: horizontal;
    }
    CanvasEditorModal .colors-row {
        width: 100%; height: auto;
        align: left middle; margin-bottom: 1;
        layout: horizontal;
    }
    CanvasEditorModal .canvas-container {
        width: 100%; height: auto;
        border: solid $primary;
        padding: 0;
        margin-bottom: 1;
        background: #000000;
    }
    CanvasEditorModal #canvas-display {
        width: 100%;
        height: auto;
    }
    CanvasEditorModal .button-row {
        width: 100%; height: auto;
        align: center middle; margin-top: 1;
    }
    CanvasEditorModal Button { margin: 0 1; }
    CanvasEditorModal .tool-button {
        min-width: 12;
    }
    CanvasEditorModal .tool-button.active {
        background: $accent;
    }
    CanvasEditorModal .color-button {
        min-width: 8;
    }
    CanvasEditorModal .tags-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; layout: horizontal; }
    CanvasEditorModal .tags-display { width: 1fr; padding: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]

    def __init__(self, canvas_data: Canvas = None, all_tags: list[Tag] = None, selected_tag_ids: list[int] = None, selected_task_ids: list[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.canvas_data = canvas_data or Canvas(id=0, title="Nueva Pizarra", width=50, height=20)
        self.all_tags = all_tags or []
        self.selected_tag_ids = selected_tag_ids if selected_tag_ids is not None else (list(self.canvas_data.tags) if self.canvas_data and self.canvas_data.tags else [])
        self.selected_task_ids = selected_task_ids or []
        self.current_tool = "draw"
        self.current_color = "[white]█[/white]"
        self.is_drawing = False
        self.color_map = {
            "white": "[white]█[/white]",
            "red": "[red]█[/red]",
            "blue": "[blue]█[/blue]",
            "green": "[green]█[/green]",
            "yellow": "[yellow]█[/yellow]",
            "magenta": "[magenta]█[/magenta]",
            "cyan": "[cyan]█[/cyan]"
        }

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🎨 Editar Pizarra", classes="modal-title")

            yield Label("Título:", classes="section-label")
            yield UndoableInput(value=self.canvas_data.title, id="title-input")

            yield Label("Etiquetas:", classes="section-label")
            with Horizontal(classes="tags-row"):
                yield Label(self._format_tags(), id="tags-display", classes="tags-display")
                yield Button("🏷️ Seleccionar", id="select-tags")

            yield Label("Tareas asociadas (opcional):", classes="section-label")
            with Horizontal(classes="tags-row"):
                yield Label(self._format_tasks(), id="task-display", classes="tags-display")
                yield Button("📌 Seleccionar", id="select-task")

            yield Label("Herramientas:", classes="section-label")
            with Horizontal(classes="tools-row"):
                yield Button("✏️ Dibujar", id="tool-draw", classes="tool-button active")
                yield Button("🗑️ Borrar", id="tool-erase", classes="tool-button")
                yield Button("🧹 Limpiar", id="tool-clear", classes="tool-button")

            yield Label("Colores:", classes="section-label")
            with Horizontal(classes="colors-row"):
                yield Button("⬜ Blanco", id="color-white", classes="color-button")
                yield Button("🟥 Rojo", id="color-red", classes="color-button")
                yield Button("🟦 Azul", id="color-blue", classes="color-button")
                yield Button("🟩 Verde", id="color-green", classes="color-button")
                yield Button("🟨 Amarillo", id="color-yellow", classes="color-button")
                yield Button("🟪 Magenta", id="color-magenta", classes="color-button")
                yield Button("🟦 Cian", id="color-cyan", classes="color-button")

            yield Label("Canvas (Click y arrastra para dibujar):", classes="section-label")
            yield Container(Static("", id="canvas-display"), classes="canvas-container")

            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        self.query_one("#title-input", Input).focus()
        self.render_canvas()

    def render_canvas(self) -> None:
        lines = []
        for row in self.canvas_data.grid:
            line = ""
            for cell in row:
                if cell == " ":
                    line += "  "
                else:
                    line += cell + cell
            lines.append(line)

        canvas_text = "\n".join(lines)
        self.query_one("#canvas-display", Static).update(canvas_text)

    @on(Button.Pressed, "#tool-draw")
    def on_tool_draw(self) -> None:
        self.current_tool = "draw"
        self.query_one("#tool-draw", Button).add_class("active")
        self.query_one("#tool-erase", Button).remove_class("active")

    @on(Button.Pressed, "#tool-erase")
    def on_tool_erase(self) -> None:
        self.current_tool = "erase"
        self.query_one("#tool-erase", Button).add_class("active")
        self.query_one("#tool-draw", Button).remove_class("active")

    @on(Button.Pressed, "#tool-clear")
    def on_tool_clear(self) -> None:
        self.canvas_data.grid = [[" " for _ in range(self.canvas_data.width)]
                                  for _ in range(self.canvas_data.height)]
        self.render_canvas()

    @on(Button.Pressed, "#color-white")
    def on_color_white(self) -> None:
        self.current_color = self.color_map["white"]

    @on(Button.Pressed, "#color-red")
    def on_color_red(self) -> None:
        self.current_color = self.color_map["red"]

    @on(Button.Pressed, "#color-blue")
    def on_color_blue(self) -> None:
        self.current_color = self.color_map["blue"]

    @on(Button.Pressed, "#color-green")
    def on_color_green(self) -> None:
        self.current_color = self.color_map["green"]

    @on(Button.Pressed, "#color-yellow")
    def on_color_yellow(self) -> None:
        self.current_color = self.color_map["yellow"]

    @on(Button.Pressed, "#color-magenta")
    def on_color_magenta(self) -> None:
        self.current_color = self.color_map["magenta"]

    @on(Button.Pressed, "#color-cyan")
    def on_color_cyan(self) -> None:
        self.current_color = self.color_map["cyan"]

    def on_mouse_down(self, event) -> None:
        canvas_widget = self.query_one("#canvas-display", Static)
        if canvas_widget.region.contains(event.screen_x, event.screen_y):
            self.is_drawing = True
            self._draw_at_position(event)

    def on_mouse_move(self, event) -> None:
        if self.is_drawing:
            self._draw_at_position(event)

    def on_mouse_up(self, event) -> None:
        self.is_drawing = False

    def _draw_at_position(self, event) -> None:
        canvas_widget = self.query_one("#canvas-display", Static)
        region = canvas_widget.region

        if not region.contains(event.screen_x, event.screen_y):
            return

        rel_x = event.screen_x - region.x
        rel_y = event.screen_y - region.y
        pixel_x = rel_x // 2

        if 0 <= rel_y < self.canvas_data.height and 0 <= pixel_x < self.canvas_data.width:
            if self.current_tool == "draw":
                self.canvas_data.grid[rel_y][pixel_x] = self.current_color
            elif self.current_tool == "erase":
                self.canvas_data.grid[rel_y][pixel_x] = " "

            self.render_canvas()

    def _format_tags(self) -> str:
        if not self.selected_tag_ids:
            return "Sin etiquetas"
        names = [t.name for tid in self.selected_tag_ids for t in self.all_tags if t.id == tid]
        return f"🏷️ {', '.join(names)}" if names else "Sin etiquetas"

    def _format_tasks(self) -> str:
        if not self.selected_task_ids:
            return "Sin tareas asociadas"
        all_tasks = getattr(self.app, "tasks", [])
        names = []
        for tid in self.selected_task_ids:
            task = next((t for t in all_tasks if t.id == tid), None)
            if task:
                txt = task.text[:25] + "..." if len(task.text) > 25 else task.text
                names.append(txt)
        return f"📌 {', '.join(names)}" if names else "Sin tareas asociadas"

    @on(Button.Pressed, "#select-tags")
    def on_select_tags(self) -> None:
        def on_tags_selected(result: Optional[list[int]]) -> None:
            if result is not None:
                self.selected_tag_ids = result
                self.query_one("#tags-display", Label).update(self._format_tags())
        self.app.push_screen(TagPickerModal(all_tags=self.all_tags, selected_tag_ids=self.selected_tag_ids), on_tags_selected)

    @on(Button.Pressed, "#select-task")
    def on_select_task(self) -> None:
        def on_tasks_selected(result: Optional[list[int]]) -> None:
            if result is not None:
                self.selected_task_ids = result
                self.query_one("#task-display", Label).update(self._format_tasks())
        tasks = getattr(self.app, "tasks", [])
        self.app.push_screen(MultiTaskPickerModal(tasks=tasks, selected_task_ids=self.selected_task_ids), on_tasks_selected)

    def action_save(self) -> None:
        title = self.query_one("#title-input", Input).value.strip()

        if not title:
            self.app.notify("El título es obligatorio", severity="error", timeout=2)
            return

        self.canvas_data.title = title
        self.canvas_data.tags = list(self.selected_tag_ids)
        self.dismiss({
            "canvas": self.canvas_data,
            "title": title,
            "grid": self.canvas_data.grid,
            "width": self.canvas_data.width,
            "height": self.canvas_data.height,
            "tags": self.selected_tag_ids,
            "target_task_ids": self.selected_task_ids
        })

    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)

class StatusPickerModal(ModalScreen[Optional[str]]):
    DEFAULT_CSS = """
    StatusPickerModal { align: center middle; }
    StatusPickerModal > VerticalScroll {
        width: 40; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    StatusPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    StatusPickerModal #status-picker-list { width: 100%; height: auto; padding: 1; }
    StatusPickerModal .status-picker-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        content-align: center middle;
    }
    StatusPickerModal .status-picker-item:hover { background: $boost; }
    StatusPickerModal .status-picker-item.selected { border: solid $accent; background: $surface-lighten-1; }
    StatusPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    StatusPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    StatusPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("enter", "select", show=False),
    ]

    def __init__(self, current_status: str = "En progreso", **kwargs) -> None:
        super().__init__(**kwargs)
        self.statuses = [
            ("🔄 En progreso", "En progreso"),
            ("⏳ En espera", "En espera"),
            ("✅ Completado", "Completado")
        ]
        self.current_status = current_status
        self.selected_index = 0
        for i, (_, val) in enumerate(self.statuses):
            if val == current_status:
                self.selected_index = i
                break

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🔄 Seleccionar Estado", classes="modal-title")
            yield Container(id="status-picker-list")
            yield Label("↑↓ Navegar | Enter: Seleccionar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Seleccionar", variant="primary", id="select")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_list()

    async def refresh_list(self) -> None:
        container = self.query_one("#status-picker-list", Container)
        await container.remove_children()
        for i, (label, val) in enumerate(self.statuses):
            item = Static(label, id=f"status-opt-{i}", classes="status-picker-item")
            await container.mount(item)
            if i == self.selected_index:
                item.add_class("selected")

    def update_selection(self) -> None:
        for i in range(len(self.statuses)):
            try:
                item = self.query_one(f"#status-opt-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass

    def action_move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.selected_index < len(self.statuses) - 1:
            self.selected_index += 1
            self.update_selection()

    @on(Button.Pressed, "#select")
    def on_select_btn(self) -> None:
        self.action_select()

    def action_select(self) -> None:
        selected_val = self.statuses[self.selected_index][1]
        self.dismiss(selected_val)

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_click(self, event: events.Click) -> None:
        for i in range(len(self.statuses)):
            try:
                item = self.query_one(f"#status-opt-{i}", Static)
                if event.widget == item:
                    self.selected_index = i
                    self.action_select()
                    break
            except Exception:
                pass

class PriorityPickerModal(ModalScreen[Optional[int]]):
    DEFAULT_CSS = """
    PriorityPickerModal { align: center middle; }
    PriorityPickerModal > VerticalScroll {
        width: 40; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    PriorityPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    PriorityPickerModal #priority-list { width: 100%; height: auto; padding: 1; }
    PriorityPickerModal .priority-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        content-align: center middle;
    }
    PriorityPickerModal .priority-item:hover { background: $boost; }
    PriorityPickerModal .priority-item.selected { border: solid $accent; background: $surface-lighten-1; }
    PriorityPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    PriorityPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    PriorityPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("enter", "select", show=False),
    ]
    
    def __init__(self, current_priority: int = 0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_priority = current_priority
        self.selected_index = current_priority
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("⭐ Seleccionar Prioridad", classes="modal-title")
            yield Container(id="priority-list")
            yield Label("↑↓ Navegar | Enter: Seleccionar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Seleccionar", variant="primary", id="select")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        await self.refresh_list()
    
    async def refresh_list(self) -> None:
        priority_list = self.query_one("#priority-list", Container)
        await priority_list.remove_children()
        
        priorities = [
            ("   Sin prioridad", 0),
            ("[green]■[/green]  Baja", 1),
            ("[yellow]■[/yellow]  Media", 2),
            ("[red]■[/red]  Alta", 3)
        ]
        
        for i, (text, value) in enumerate(priorities):
            item = Static(text, id=f"priority-{i}", classes="priority-item")
            await priority_list.mount(item)
            if i == self.selected_index:
                item.add_class("selected")
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#priority-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(4):
            try:
                item = self.query_one(f"#priority-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.selected_index < 3:
            self.selected_index += 1
            self.update_selection()
    
    def action_select(self) -> None:
        self.dismiss(self.selected_index)
    
    @on(Button.Pressed, "#select")
    def on_select_btn(self) -> None:
        self.action_select()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class InputModal(ModalScreen[Optional[str]]):
    DEFAULT_CSS = """
    InputModal { align: center middle; }
    InputModal > VerticalScroll {
        width: 60; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    InputModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    InputModal Input { width: 100%; margin-bottom: 1; }
    InputModal .button-row { width: 100%; height: auto; align: center middle; }
    InputModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]
    
    def __init__(self, title: str = "", initial_text: str = "", placeholder: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.title_text = title
        self.initial_text = initial_text
        self.placeholder_text = placeholder
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(self.title_text, classes="modal-title")
            yield UndoableInput(value=self.initial_text, placeholder=self.placeholder_text, id="modal-input")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()
    
    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Input.Submitted)
    def on_submit(self) -> None:
        self.on_save()
    
    def action_cancel(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)
    
    def action_save(self) -> None:
        text = self.query_one("#modal-input", Input).value.strip()
        self.dismiss(text if text else None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()

class ReminderModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ReminderModal { align: center middle; }
    ReminderModal > VerticalScroll {
        width: 50; height: auto; max-height: 20; border: thick $warning;
        background: $surface; padding: 1 2;
    }
    ReminderModal .modal-title { 
        text-align: center; text-style: bold; 
        width: 100%; height: auto;
        color: $warning;
        margin-bottom: 1;
    }
    ReminderModal .task-info {
        width: 100%; height: auto;
        padding: 1;
        background: $surface-lighten-1;
        border: solid $primary-background;
        margin-bottom: 1;
    }
    ReminderModal .task-text { 
        width: 100%; height: auto;
        text-align: center;
        margin: 0 0 1 0;
    }
    ReminderModal .group-info {
        width: 100%; height: auto;
        text-align: center;
        color: $text-muted;
        margin-bottom: 0;
    }
    ReminderModal .button-row { 
        width: 100%; height: auto; 
        align: center middle;
        margin-top: 1;
    }
    ReminderModal Button { margin: 0 1; }
    """
    
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("enter", "close", show=False),
        Binding("space", "close", show=False),
    ]
    
    def __init__(self, task: Task, group_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.task_data = task
        self.group_name = group_name
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("⏰ Recordatorio de Tarea", classes="modal-title")
            with Container(classes="task-info"):
                yield Label("La siguiente tarea vence HOY:", classes="group-info")
                yield Label(self.task_data.text, classes="task-text")
                yield Label(f"📁 Grupo: {self.group_name}", classes="group-info")
            with Horizontal(classes="button-row"):
                yield Button("Entendido", variant="primary", id="ok")
    
    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self.dismiss(True)
    
    def action_close(self) -> None:
        self.dismiss(True)
    
    def on_key(self, event) -> None:
        if event.key not in ["escape", "enter", "space"]:
            event.prevent_default()
            event.stop()

class GroupPickerModal(ModalScreen[Optional[int]]):
    DEFAULT_CSS = """
    GroupPickerModal { align: center middle; }
    GroupPickerModal > VerticalScroll {
        width: 55; height: auto; max-height: 25; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    GroupPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    GroupPickerModal .search-label { color: $text-muted; margin-bottom: 0; }
    GroupPickerModal Input { width: 100%; margin-bottom: 1; }
    GroupPickerModal #groups-list { width: 100%; height: auto; max-height: 12; overflow-y: auto; }
    GroupPickerModal .group-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        content-align: left middle;
    }
    GroupPickerModal .group-item:hover { background: $boost; }
    GroupPickerModal .group-item.selected { border: solid $accent; background: $surface-lighten-1; }
    GroupPickerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    GroupPickerModal .hint { width: 100%; text-align: center; color: $text-muted; margin-top: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("enter", "select_group", show=False),
        Binding("/", "focus_search", show=False),
    ]
    
    def __init__(self, groups: list[Group], current_group_id: Optional[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.groups = groups
        self.current_group_id = current_group_id
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_items: list[tuple[str, Optional[int]]] = []
        self.selected_index = 0
    
    def _get_filtered_items(self) -> list[tuple[str, Optional[int]]]:
        all_items: list[tuple[str, Optional[int]]] = [("📋 Sin grupo", None)] + [(f"📁 {g.name}", g.id) for g in self.groups]
        if not self.search_query:
            return all_items
        q = self.search_query.lower()
        return [item for item in all_items if q in item[0].lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📁 Seleccionar Grupo", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar grupo...", id="group-search-input")
            yield Container(id="groups-list")
            yield Label("↑↓ Navegar | Enter: Seleccionar | /: Buscar | Esc: Cancelar", classes="hint")
    
    async def on_mount(self) -> None:
        await self.refresh_groups_list()
        try:
            self.query_one("#group-search-input", Input).blur()
        except:
            pass

    async def refresh_groups_list(self) -> None:
        groups_list = self.query_one("#groups-list", Container)
        await groups_list.remove_children()
        
        self.filtered_items = self._get_filtered_items()
        
        if not self.filtered_items:
            await groups_list.mount(Label(f"No se encontraron grupos para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_items) or self.selected_index < 0:
                self.selected_index = 0
            
            for i, (label, gid) in enumerate(self.filtered_items):
                item = Static(label, id=f"group-item-{i}", classes="group-item")
                await groups_list.mount(item)
                if i == self.selected_index:
                    item.add_class("selected")
    
    def update_selection(self) -> None:
        for i in range(len(self.filtered_items)):
            try:
                item = self.query_one(f"#group-item-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
    
    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            inp = self.query_one("#group-search-input", Input)
            inp.focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#group-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.call_later(self.refresh_groups_list)

    @on(Input.Changed, "#group-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_groups_list()

    @on(Input.Submitted, "#group-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.selected_index < len(self.filtered_items) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_select_group(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        if self.filtered_items and 0 <= self.selected_index < len(self.filtered_items):
            self.dismiss(self.filtered_items[self.selected_index][1])

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(self.current_group_id)

class CommentEditModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    CommentEditModal { align: center middle; }
    CommentEditModal > VerticalScroll {
        width: 82; height: 50; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    CommentEditModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    CommentEditModal .section-label { margin-top: 1; margin-bottom: 0; color: $text-muted; }
    CommentEditModal #title-input {
        width: 100%;
        margin-bottom: 0;
    }
    CommentEditModal #description-input {
        width: 100%;
        height: 8;
        margin-bottom: 0;
        border: solid $primary;
        padding: 1;
    }
    CommentEditModal Input { width: 100%; margin-bottom: 0; }
    CommentEditModal .image-info {
        width: 100%;
        padding: 1;
        background: $surface-lighten-1;
        border: solid $primary-background;
        margin-bottom: 0;
        color: $success;
    }
    CommentEditModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 2; }
    CommentEditModal .image-button-row {
        width: 100%;
        height: auto;
        align: left middle;
        margin-bottom: 0;
        layout: horizontal;
    }
    CommentEditModal Button { margin: 0 1; }
    CommentEditModal #image-info-container { margin-bottom: 0; }
    CommentEditModal #file-info-container { margin-bottom: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]
    
    def __init__(self, modal_title: str = "💬 Comentario", initial_title: str = "",
                 initial_description: str = "", initial_url: str = "", initial_image: str = "",
                 initial_file: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.modal_title = modal_title
        self.initial_title = initial_title
        self.initial_description = initial_description
        self.initial_url = initial_url or ""
        self.current_image_path = initial_image or ""
        self.current_file_path = initial_file or ""
        self.images_dir = Path.home() / "todo" / "images"
        self.images_dir.mkdir(exist_ok=True, parents=True)
        self.files_dir = Path.home() / "todo" / "files"
        self.files_dir.mkdir(exist_ok=True, parents=True)
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(self.modal_title, classes="modal-title")
            yield Label("Título del comentario:", classes="section-label")
            yield UndoableInput(value=self.initial_title, placeholder="Título breve...", id="title-input")
            yield Label("Descripción (opcional - Enter para nueva línea):", classes="section-label")
            yield UndoableTextArea(self.initial_description, id="description-input", show_line_numbers=False)
            yield Label("Enlace (opcional):", classes="section-label")
            yield UndoableInput(value=self.initial_url, placeholder="https://ejemplo.com ", id="url-input")
            yield Label("Imagen (opcional):", classes="section-label")
            yield Horizontal(id="image-button-row", classes="image-button-row")
            yield Container(id="image-info-container")
            yield Label("Archivo adjunto (opcional):", classes="section-label")
            yield Horizontal(id="file-button-row", classes="image-button-row")
            yield Container(id="file-info-container")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        self.query_one("#title-input", Input).focus()
        await self._update_image_buttons()
        await self._update_file_buttons()
    
    async def _update_image_buttons(self) -> None:
        button_row = self.query_one("#image-button-row", Horizontal)
        await button_row.remove_children()
        
        await button_row.mount(Button("📋 Pegar", variant="default", id="paste-image"))
        await button_row.mount(Button("📁 Examinar", variant="default", id="browse-image"))
        await button_row.mount(Button("✏️ Ruta", variant="default", id="path-image"))
        
        if self.current_image_path:
            await button_row.mount(Button("🗑️ Eliminar", variant="error", id="remove-image"))
        
        info_container = self.query_one("#image-info-container", Container)
        await info_container.remove_children()
        
        if self.current_image_path:
            await info_container.mount(
                Label(f"📷 Imagen: {Path(self.current_image_path).name}", 
                      id="image-info", classes="image-info")
            )

    async def _update_file_buttons(self) -> None:
        button_row = self.query_one("#file-button-row", Horizontal)
        await button_row.remove_children()

        await button_row.mount(Button("📁 Examinar archivo", variant="default", id="browse-file"))

        if self.current_file_path:
            await button_row.mount(Button("🗑️ Eliminar", variant="error", id="remove-file"))

        info_container = self.query_one("#file-info-container", Container)
        await info_container.remove_children()

        if self.current_file_path:
            file_path = Path(self.current_file_path)
            file_size = file_path.stat().st_size if file_path.exists() else 0
            size_str = self._format_file_size(file_size)
            await info_container.mount(
                Label(f"📎 Archivo: {file_path.name} ({size_str})",
                      id="file-info", classes="image-info")
            )

    def _format_file_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _save_image_from_clipboard(self) -> Optional[str]:
        try:
            from PIL import ImageGrab
            image = ImageGrab.grabclipboard()
            if image and isinstance(image, Image.Image):
                filename = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                filepath = self.images_dir / filename
                image.save(filepath)
                return str(filepath)
            else:
                try:
                    clipboard_text = pyperclip.paste()
                    if clipboard_text and Path(clipboard_text).exists():
                        if Path(clipboard_text).suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                            return self._copy_image_to_storage(clipboard_text)
                except:
                    pass
            return None
        except Exception as e:
            print(f"Error al pegar imagen: {e}")
            return None
    
    def _copy_image_to_storage(self, source_path: str) -> Optional[str]:
        try:
            source = Path(source_path)
            if not source.exists():
                return None
            
            if source.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                return None
            
            filename = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}{source.suffix}"
            filepath = self.images_dir / filename
            shutil.copy2(source, filepath)
            return str(filepath)
        except Exception as e:
            print(f"Error al copiar imagen: {e}")
            return None
    
    def _browse_image(self) -> Optional[str]:
        try:
            system = platform.system()

            if system == "Windows":
                ps_script = '''
                Add-Type -AssemblyName System.Windows.Forms
                $FileBrowser = New-Object System.Windows.Forms.OpenFileDialog -Property @{
                    Filter = 'Imágenes (*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp)|*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp|Todos los archivos (*.*)|*.*'
                    Title = 'Seleccionar imagen'
                }
                $null = $FileBrowser.ShowDialog()
                Write-Output $FileBrowser.FileName
                '''

                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                filepath = result.stdout.strip()
                return filepath if filepath else None

            elif system == "Darwin":
                script = '''
                set theFile to choose file with prompt "Seleccionar imagen" of type {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
                return POSIX path of theFile
                '''

                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                filepath = result.stdout.strip()
                return filepath if filepath else None

            else:
                try:
                    result = subprocess.run(
                        [
                            "zenity", "--file-selection",
                            "--title=Seleccionar imagen",
                            "--file-filter=Imágenes | *.png *.jpg *.jpeg *.gif *.bmp *.webp",
                            "--file-filter=Todos los archivos | *"
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    filepath = result.stdout.strip()
                    return filepath if filepath else None
                except FileNotFoundError:
                    try:
                        result = subprocess.run(
                            [
                                "kdialog", "--getopenfilename", ".",
                                "*.png *.jpg *.jpeg *.gif *.bmp *.webp|Imágenes"
                            ],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        filepath = result.stdout.strip()
                        return filepath if filepath else None
                    except FileNotFoundError:
                        print("No hay explorador de archivos nativo disponible (zenity/kdialog)")
                        return None

        except subprocess.TimeoutExpired:
            print("Tiempo de espera agotado al seleccionar archivo")
            return None
        except Exception as e:
            print(f"Error al abrir explorador nativo: {e}")
            return None

    def _browse_file(self) -> Optional[str]:
        try:
            system = platform.system()

            if system == "Windows":
                ps_script = '''
                Add-Type -AssemblyName System.Windows.Forms
                $FileBrowser = New-Object System.Windows.Forms.OpenFileDialog -Property @{
                    Filter = 'Todos los archivos (*.*)|*.*'
                    Title = 'Seleccionar archivo'
                }
                $null = $FileBrowser.ShowDialog()
                Write-Output $FileBrowser.FileName
                '''

                result = subprocess.run(
                    ["powershell", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                filepath = result.stdout.strip()
                return filepath if filepath else None

            elif system == "Darwin":
                script = 'set theFile to choose file with prompt "Seleccionar archivo"\nreturn POSIX path of theFile'

                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                filepath = result.stdout.strip()
                return filepath if filepath else None

            else:
                try:
                    result = subprocess.run(
                        ["zenity", "--file-selection", "--title=Seleccionar archivo"],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    filepath = result.stdout.strip()
                    return filepath if filepath else None
                except FileNotFoundError:
                    try:
                        result = subprocess.run(
                            ["kdialog", "--getopenfilename", "."],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        filepath = result.stdout.strip()
                        return filepath if filepath else None
                    except FileNotFoundError:
                        print("No hay explorador de archivos nativo disponible")
                        return None

        except subprocess.TimeoutExpired:
            print("Tiempo de espera agotado al seleccionar archivo")
            return None
        except Exception as e:
            print(f"Error al abrir explorador nativo: {e}")
            return None

    def _copy_file_to_storage(self, source_path: str) -> Optional[str]:
        try:
            source = Path(source_path)
            if not source.exists():
                return None

            filename = f"{source.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{source.suffix}"
            filepath = self.files_dir / filename
            shutil.copy2(source, filepath)
            return str(filepath)
        except Exception as e:
            print(f"Error al copiar archivo: {e}")
            return None

    @on(Button.Pressed, "#paste-image")
    async def on_paste_image(self) -> None:
        image_path = self._save_image_from_clipboard()
        if image_path:
            self.current_image_path = image_path
            await self._update_image_buttons()
            self.app.notify("📷 Imagen pegada correctamente", severity="information")
        else:
            self.app.notify("⚠️ No hay imagen en el portapapeles", severity="warning")
    
    @on(Button.Pressed, "#browse-image")
    async def on_browse_image(self) -> None:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            image_path = await loop.run_in_executor(executor, self._browse_image)

        if image_path:
            copied_path = self._copy_image_to_storage(image_path)
            if copied_path:
                self.current_image_path = copied_path
                await self._update_image_buttons()
                self.app.notify("📷 Imagen seleccionada", severity="information")

        try:
            self.query_one("#text-input", TextArea).focus()
        except:
            pass
    
    @on(Button.Pressed, "#path-image")
    def on_path_image(self) -> None:
        async def on_result(path: Optional[str]) -> None:
            if path:
                if Path(path).exists():
                    image_path = self._copy_image_to_storage(path)
                    if image_path:
                        self.current_image_path = image_path
                        await self._update_image_buttons()
                        self.app.notify("📷 Imagen añadida", severity="information")
                    else:
                        self.app.notify("❌ Formato de imagen no válido", severity="error")
                else:
                    self.app.notify("❌ Ruta no existe", severity="error")
        self.app.push_screen(
            InputModal("📷 Ruta de la imagen", placeholder="/ruta/a/imagen.png"),
            on_result
        )
    
    @on(Button.Pressed, "#remove-image")
    async def on_remove_image(self) -> None:
        self.current_image_path = ""
        await self._update_image_buttons()
        self.app.notify("🗑️ Imagen eliminada", severity="information")

    @on(Button.Pressed, "#browse-file")
    async def on_browse_file(self) -> None:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            file_path = await loop.run_in_executor(executor, self._browse_file)

        if file_path:
            copied_path = self._copy_file_to_storage(file_path)
            if copied_path:
                self.current_file_path = copied_path
                await self._update_file_buttons()
                self.app.notify("📎 Archivo adjuntado", severity="information")

        try:
            self.query_one("#text-input", TextArea).focus()
        except:
            pass

    @on(Button.Pressed, "#remove-file")
    async def on_remove_file(self) -> None:
        self.current_file_path = ""
        await self._update_file_buttons()
        self.app.notify("🗑️ Archivo eliminado", severity="information")

    def action_save(self) -> None:
        try:
            text_area = self.query_one("#text-input", TextArea)
            text_area.blur()
        except:
            pass
        
        self.call_later(self._real_save)
    
    def _real_save(self) -> None:
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", TextArea).text.strip()
        url = self.query_one("#url-input", Input).value.strip()

        if not title:
            self.app.notify("El título del comentario no puede estar vacío", severity="warning")
            return

        if url and not (url.startswith("http://") or url.startswith("https://")):
            self.app.notify("La URL debe comenzar con http:// o https://", severity="warning")
            return

        self.dismiss({
            "title": title,
            "description": description,
            "url": url if url else None,
            "image_path": self.current_image_path if self.current_image_path else None,
            "file_path": self.current_file_path if self.current_file_path else None
        })
    
    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()
            return
        
        if event.key == "ctrl+enter":
            event.prevent_default()
            event.stop()
            text_area = self.query_one("#description-input", TextArea)
            current_text = text_area.text
            cursor_pos = text_area.cursor
            new_text = current_text[:cursor_pos] + "\n" + current_text[cursor_pos:]
            text_area.text = new_text
            text_area.cursor = cursor_pos + 1
            return
    
    def on_destroy(self) -> None:
        pass

class MultiTaskPickerModal(ModalScreen[Optional[list[int]]]):
    DEFAULT_CSS = """
    MultiTaskPickerModal { align: center middle; }
    MultiTaskPickerModal > VerticalScroll {
        width: 78; height: 36; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    MultiTaskPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    MultiTaskPickerModal .search-label { color: $text-muted; margin-bottom: 0; }
    MultiTaskPickerModal Input { width: 100%; margin-bottom: 1; }
    MultiTaskPickerModal #task-picker-list { width: 100%; height: 18; overflow-y: auto; border: solid $primary-background; padding: 1; }
    MultiTaskPickerModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    MultiTaskPickerModal .item:hover { background: $boost; }
    MultiTaskPickerModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    MultiTaskPickerModal .item.checked { color: $success; }
    MultiTaskPickerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    MultiTaskPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    MultiTaskPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    MultiTaskPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_select", show=False),
        Binding("enter", "save", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, tasks: list[Task], selected_task_ids: list[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tasks = tasks or []
        self.selected_task_ids = set(selected_task_ids or [])
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_tasks: list[Task] = []
        self.selected_index = 0 if self.tasks else -1

    def _get_filtered_tasks(self) -> list[Task]:
        if not self.search_query:
            return self.tasks
        q = self.search_query.lower()
        return [t for t in self.tasks if q in t.text.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📌 Seleccionar Tareas Asociadas", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar tareas...", id="mtp-search-input")
            yield Container(id="task-picker-list")
            yield Label("↑↓/k/j: Navegar | Espacio: Marcar | /: Buscar | Enter/Guardar: Aceptar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Desmarcar Todas", variant="warning", id="clear-all")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#mtp-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        container = self.query_one("#task-picker-list", Container)
        await container.remove_children()
        
        self.filtered_tasks = self._get_filtered_tasks()
        
        if not self.tasks:
            await container.mount(Label("No hay tareas disponibles.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_tasks:
            await container.mount(Label(f"No se encontraron tareas para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_tasks) or self.selected_index < 0:
                self.selected_index = 0
            for i, t in enumerate(self.filtered_tasks):
                txt = t.text[:40] + "..." if len(t.text) > 40 else t.text
                checked = "☑" if t.id in self.selected_task_ids else "☐"
                item = Static(f"{checked}  {txt}", id=f"mtp-{i}", classes="item")
                await container.mount(item)
                if t.id in self.selected_task_ids:
                    item.add_class("checked")
                if i == self.selected_index:
                    item.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#mtp-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#mtp-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#mtp-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#mtp-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.filtered_tasks and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.filtered_tasks and self.selected_index < len(self.filtered_tasks) - 1:
            self.selected_index += 1
            self.update_selection()

    def action_toggle_select(self) -> None:
        if self.search_focused: return
        if self.filtered_tasks and 0 <= self.selected_index < len(self.filtered_tasks):
            tid = self.filtered_tasks[self.selected_index].id
            if tid in self.selected_task_ids:
                self.selected_task_ids.remove(tid)
            else:
                self.selected_task_ids.add(tid)
            self.call_later(self.refresh_list)

    def update_selection(self) -> None:
        for i in range(len(self.filtered_tasks)):
            try:
                item = self.query_one(f"#mtp-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except Exception: pass

    def action_save(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        self.dismiss(list(self.selected_task_ids))

    @on(Button.Pressed, "#clear-all")
    def on_clear_all(self) -> None:
        self.selected_task_ids.clear()
        self.update_selection()

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)


class TaskPickerModal(ModalScreen[Optional[Task]]):
    DEFAULT_CSS = """
    TaskPickerModal { align: center middle; }
    TaskPickerModal > VerticalScroll {
        width: 75; height: 34; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    TaskPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    TaskPickerModal .search-label { color: $text-muted; margin-bottom: 0; }
    TaskPickerModal Input { width: 100%; margin-bottom: 1; }
    TaskPickerModal #task-picker-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    TaskPickerModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    TaskPickerModal .item:hover { background: $boost; }
    TaskPickerModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    TaskPickerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    TaskPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    TaskPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    TaskPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("enter", "select", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, tasks: list[Task], selected_task_id: Optional[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tasks = tasks or []
        self.selected_task_id = selected_task_id
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_tasks: list[Task] = []
        self.selected_index = 0 if self.tasks else -1
        if selected_task_id:
            for idx, t in enumerate(self.tasks):
                if t.id == selected_task_id:
                    self.selected_index = idx
                    break

    def _get_filtered_tasks(self) -> list[Task]:
        if not self.search_query:
            return self.tasks
        q = self.search_query.lower()
        return [t for t in self.tasks if q in t.text.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📌 Seleccionar Tarea", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar tareas...", id="tp-search-input")
            yield Container(id="task-picker-list")
            yield Label("↑↓ Navegar | /: Buscar | Enter: Seleccionar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Seleccionar", variant="primary", id="select")
                yield Button("Sin Tarea", variant="warning", id="none")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#tp-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        container = self.query_one("#task-picker-list", Container)
        await container.remove_children()
        
        self.filtered_tasks = self._get_filtered_tasks()
        
        if not self.tasks:
            await container.mount(Label("No hay tareas disponibles.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_tasks:
            await container.mount(Label(f"No se encontraron tareas para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_tasks) or self.selected_index < 0:
                self.selected_index = 0
            for i, t in enumerate(self.filtered_tasks):
                txt = t.text[:40] + "..." if len(t.text) > 40 else t.text
                checked = "📌 " if t.id == self.selected_task_id else "   "
                item = Static(f"{checked}{txt}", id=f"tp-{i}", classes="item")
                await container.mount(item)
                if i == self.selected_index:
                    item.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#tp-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#tp-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#tp-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#tp-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.filtered_tasks and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.filtered_tasks and self.selected_index < len(self.filtered_tasks) - 1:
            self.selected_index += 1
            self.update_selection()

    def update_selection(self) -> None:
        for i in range(len(self.filtered_tasks)):
            try:
                item = self.query_one(f"#tp-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except Exception: pass

    @on(Button.Pressed, "#select")
    def on_select(self) -> None:
        self.action_select()

    def action_select(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        if self.filtered_tasks and 0 <= self.selected_index < len(self.filtered_tasks):
            self.dismiss(self.filtered_tasks[self.selected_index])
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#none")
    def on_none(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)


class GlobalNotesPickerModal(ModalScreen[Optional[list[Note]]]):
    DEFAULT_CSS = """
    GlobalNotesPickerModal { align: center middle; }
    GlobalNotesPickerModal > VerticalScroll {
        width: 75; height: 34; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    GlobalNotesPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    GlobalNotesPickerModal .search-label { color: $text-muted; margin-bottom: 0; }
    GlobalNotesPickerModal Input { width: 100%; margin-bottom: 1; }
    GlobalNotesPickerModal #gn-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    GlobalNotesPickerModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    GlobalNotesPickerModal .item:hover { background: $boost; }
    GlobalNotesPickerModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    GlobalNotesPickerModal .item.checked { color: $success; }
    GlobalNotesPickerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    GlobalNotesPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    GlobalNotesPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    GlobalNotesPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_item", show=False),
        Binding("enter", "save", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, global_notes: list[Note], selected_note_ids: list[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.global_notes = global_notes or []
        self.selected_note_ids = set(selected_note_ids or [])
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_notes: list[Note] = []
        self.selected_index = 0 if self.global_notes else -1

    def _get_filtered_notes(self) -> list[Note]:
        if not self.search_query:
            return self.global_notes
        q = self.search_query.lower()
        return [n for n in self.global_notes if q in n.title.lower() or q in n.description.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🌐 Seleccionar Notas Globales", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar notas...", id="gn-search-input")
            yield Container(id="gn-list")
            yield Label("↑↓ Navegar | Espacio: Marcar | /: Buscar | Enter: Guardar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Seleccionar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#gn-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        container = self.query_one("#gn-list", Container)
        await container.remove_children()
        
        self.filtered_notes = self._get_filtered_notes()
        
        if not self.global_notes:
            await container.mount(Label("No hay notas globales disponibles.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_notes:
            await container.mount(Label(f"No se encontraron notas para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_notes) or self.selected_index < 0:
                self.selected_index = 0
            
            for i, n in enumerate(self.filtered_notes):
                checked = "☑" if n.id in self.selected_note_ids else "☐"
                item = Static(f"{checked}  📝 {n.title}", id=f"gn-{i}", classes="item")
                await container.mount(item)
                if n.id in self.selected_note_ids:
                    item.add_class("checked")
                if i == self.selected_index:
                    item.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#gn-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#gn-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#gn-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#gn-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.filtered_notes and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.filtered_notes and self.selected_index < len(self.filtered_notes) - 1:
            self.selected_index += 1
            self.update_selection()

    def update_selection(self) -> None:
        for i in range(len(self.filtered_notes)):
            try:
                item = self.query_one(f"#gn-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except Exception: pass

    def action_toggle_item(self) -> None:
        if self.search_focused: return
        if self.filtered_notes and 0 <= self.selected_index < len(self.filtered_notes):
            n = self.filtered_notes[self.selected_index]
            if n.id in self.selected_note_ids:
                self.selected_note_ids.remove(n.id)
            else:
                self.selected_note_ids.add(n.id)
            self.call_later(self.refresh_list)

    def action_save(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        selected = [n for n in self.global_notes if n.id in self.selected_note_ids]
        self.dismiss(selected)

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)

    def action_toggle_item(self) -> None:
        if self.global_notes and 0 <= self.selected_index < len(self.global_notes):
            if self.selected_index in self.selected_indices:
                self.selected_indices.remove(self.selected_index)
            else:
                self.selected_indices.add(self.selected_index)
            self.call_later(self.refresh_list)

    def update_selection(self) -> None:
        for i in range(len(self.global_notes)):
            try:
                item = self.query_one(f"#gn-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except Exception: pass
        self.scroll_to_selected()

    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#gn-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass

    def action_save(self) -> None:
        if self.selected_indices:
            self.dismiss([self.global_notes[i] for i in sorted(self.selected_indices)])
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)



class NoteEditModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    NoteEditModal { align: center middle; }
    NoteEditModal > VerticalScroll {
        width: 82; height: 50; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    NoteEditModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    NoteEditModal .section-label { margin-top: 1; margin-bottom: 0; color: $text-muted; }
    NoteEditModal #title-input {
        width: 100%;
        margin-bottom: 0;
    }
    NoteEditModal #description-input {
        width: 100%;
        height: 8;
        margin-bottom: 0;
        border: solid $primary;
        padding: 1;
    }
    NoteEditModal Input { width: 100%; margin-bottom: 0; }
    NoteEditModal .image-info {
        width: 100%;
        padding: 1;
        background: $surface-lighten-1;
        border: solid $primary-background;
        margin-bottom: 0;
        color: $success;
    }
    NoteEditModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 2; }
    NoteEditModal .image-button-row {
        width: 100%;
        height: auto;
        align: left middle;
        margin-bottom: 0;
        layout: horizontal;
    }
    NoteEditModal .tags-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    NoteEditModal .tags-display { width: 1fr; padding: 0 1; }
    NoteEditModal Button { margin: 0 1; }
    NoteEditModal #image-info-container { margin-bottom: 0; }
    NoteEditModal #file-info-container { margin-bottom: 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]

    def __init__(self, modal_title: str = "📝 Nota", initial_title: str = "",
                 initial_description: str = "", initial_url: str = "", initial_image: str = "",
                 initial_file: str = "", all_tags: list[Tag] = None, selected_tag_ids: list[int] = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.modal_title = modal_title
        self.initial_title = initial_title
        self.initial_description = initial_description
        self.initial_url = initial_url or ""
        self.current_image_path = initial_image or ""
        self.current_file_path = initial_file or ""
        self.all_tags = all_tags or []
        self.selected_tag_ids = list(selected_tag_ids) if selected_tag_ids else []
        self.images_dir = Path.home() / "todo" / "images"
        self.images_dir.mkdir(exist_ok=True, parents=True)
        self.files_dir = Path.home() / "todo" / "files"
        self.files_dir.mkdir(exist_ok=True, parents=True)

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(self.modal_title, classes="modal-title")
            yield Label("Título de la nota:", classes="section-label")
            yield UndoableInput(value=self.initial_title, placeholder="Título breve...", id="title-input")
            yield Label("Descripción (opcional - Enter para nueva línea):", classes="section-label")
            yield UndoableTextArea(self.initial_description, id="description-input", show_line_numbers=False)
            yield Label("Enlace (opcional):", classes="section-label")
            yield UndoableInput(value=self.initial_url, placeholder="https://ejemplo.com ", id="url-input")
            yield Label("Imagen (opcional):", classes="section-label")
            yield Horizontal(id="image-button-row", classes="image-button-row")
            yield Container(id="image-info-container")
            yield Label("Archivo adjunto (opcional):", classes="section-label")
            yield Horizontal(id="file-button-row", classes="image-button-row")
            yield Container(id="file-info-container")
            yield Label("Etiquetas:", classes="section-label")
            with Horizontal(classes="tags-row"):
                yield Label(self._format_tags(), id="tags-display", classes="tags-display")
                yield Button("🏷️ Seleccionar", id="select-tags")
            yield Label("Tareas asociadas (opcional):", classes="section-label")
            with Horizontal(classes="tags-row"):
                yield Label(self._format_tasks(), id="task-display", classes="tags-display")
                yield Button("📌 Seleccionar", id="select-task")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def _format_tags(self) -> str:
        if not self.selected_tag_ids:
            return "Sin etiquetas"
        tag_names = []
        for tag_id in self.selected_tag_ids:
            tag = next((t for t in self.all_tags if t.id == tag_id), None)
            if tag:
                tag_names.append(tag.name)
        return ", ".join(tag_names) if tag_names else "Sin etiquetas"

    def _format_tasks(self) -> str:
        selected_tasks = getattr(self, "selected_tasks", [])
        if not selected_tasks:
            return "Sin tareas asociadas"
        all_tasks = getattr(self.app, "tasks", [])
        names = []
        for tid in selected_tasks:
            task = next((t for t in all_tasks if t.id == tid), None)
            if task:
                txt = task.text[:25] + "..." if len(task.text) > 25 else task.text
                names.append(txt)
        return f"📌 {', '.join(names)}" if names else "Sin tareas asociadas"

    @on(Button.Pressed, "#select-task")
    def on_select_task(self) -> None:
        def on_tasks_selected(result) -> None:
            if result is not None:
                self.selected_tasks = result
                self.query_one("#task-display", Label).update(self._format_tasks())
        tasks = getattr(self.app, "tasks", [])
        current_ids = getattr(self, "selected_tasks", [])
        self.app.push_screen(MultiTaskPickerModal(tasks=tasks, selected_task_ids=current_ids), on_tasks_selected)

    async def on_mount(self) -> None:
        if not hasattr(self, "selected_tasks"):
            self.selected_tasks = []
        self.query_one("#title-input", Input).focus()
        await self._update_image_buttons()
        await self._update_file_buttons()

    async def _update_image_buttons(self) -> None:
        button_row = self.query_one("#image-button-row", Horizontal)
        await button_row.remove_children()

        await button_row.mount(Button("📋 Pegar", variant="default", id="paste-image"))
        await button_row.mount(Button("📁 Examinar", variant="default", id="browse-image"))
        await button_row.mount(Button("✏️ Ruta", variant="default", id="path-image"))

        if self.current_image_path:
            await button_row.mount(Button("🗑️ Eliminar", variant="error", id="remove-image"))

        info_container = self.query_one("#image-info-container", Container)
        await info_container.remove_children()

        if self.current_image_path:
            await info_container.mount(Label(f"✓ {Path(self.current_image_path).name}", classes="image-info"))

    async def _update_file_buttons(self) -> None:
        button_row = self.query_one("#file-button-row", Horizontal)
        await button_row.remove_children()

        await button_row.mount(Button("📁 Examinar", variant="default", id="browse-file"))
        await button_row.mount(Button("✏️ Ruta", variant="default", id="path-file"))

        if self.current_file_path:
            await button_row.mount(Button("🗑️ Eliminar", variant="error", id="remove-file"))

        info_container = self.query_one("#file-info-container", Container)
        await info_container.remove_children()

        if self.current_file_path:
            await info_container.mount(Label(f"✓ {Path(self.current_file_path).name}", classes="image-info"))

    @on(Button.Pressed, "#select-tags")
    async def on_select_tags(self) -> None:
        def on_tags_selected(result: Optional[list[int]]) -> None:
            if result is not None:
                self.selected_tag_ids = result
                self.query_one("#tags-display", Label).update(self._format_tags())

        self.app.push_screen(TagPickerModal(all_tags=self.all_tags, selected_tag_ids=self.selected_tag_ids), on_tags_selected)

    @on(Button.Pressed, "#paste-image")
    async def on_paste_image(self) -> None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"note_image_{timestamp}.png"
                filepath = self.images_dir / filename
                img.save(str(filepath))
                self.current_image_path = str(filepath)
                await self._update_image_buttons()
                self.app.notify("✓ Imagen pegada desde el portapapeles", severity="information", timeout=2)
            else:
                self.app.notify("No hay imagen en el portapapeles", severity="warning", timeout=2)
        except ImportError:
            self.app.notify("Instala 'pillow' para usar esta función: pip install pillow", severity="error", timeout=3)
        except Exception as e:
            self.app.notify(f"Error al pegar imagen: {e}", severity="error", timeout=3)

    @on(Button.Pressed, "#browse-image")
    async def on_browse_image(self) -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            filepath = filedialog.askopenfilename(
                title="Seleccionar imagen",
                filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Todos", "*.*")]
            )
            root.destroy()

            if filepath:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = Path(filepath).suffix
                new_filename = f"note_image_{timestamp}{ext}"
                new_filepath = self.images_dir / new_filename
                import shutil
                shutil.copy2(filepath, new_filepath)
                self.current_image_path = str(new_filepath)
                await self._update_image_buttons()
                self.app.notify(f"✓ Imagen añadida", severity="information", timeout=2)
        except Exception as e:
            self.app.notify(f"Error al seleccionar imagen: {e}", severity="error", timeout=3)

    @on(Button.Pressed, "#path-image")
    async def on_path_image(self) -> None:
        def on_input(path: Optional[str]) -> None:
            if path and Path(path).exists():
                self.current_image_path = path
                self.app.call_later(self._update_image_buttons)
                self.app.notify("✓ Ruta de imagen establecida", severity="information", timeout=2)
            elif path:
                self.app.notify("La ruta no existe", severity="error", timeout=2)

        self.app.push_screen(InputModal("Ruta de la imagen", placeholder="/ruta/a/imagen.png"), on_input)

    @on(Button.Pressed, "#remove-image")
    async def on_remove_image(self) -> None:
        self.current_image_path = ""
        await self._update_image_buttons()
        self.app.notify("Imagen eliminada", severity="information", timeout=2)

    @on(Button.Pressed, "#browse-file")
    async def on_browse_file(self) -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            filepath = filedialog.askopenfilename(
                title="Seleccionar archivo",
                filetypes=[("Todos", "*.*")]
            )
            root.destroy()

            if filepath:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = Path(filepath).suffix
                safe_name = Path(filepath).stem[:30]
                new_filename = f"note_file_{timestamp}_{safe_name}{ext}"
                new_filepath = self.files_dir / new_filename
                import shutil
                shutil.copy2(filepath, new_filepath)
                self.current_file_path = str(new_filepath)
                await self._update_file_buttons()
                self.app.notify(f"✓ Archivo añadido", severity="information", timeout=2)
        except Exception as e:
            self.app.notify(f"Error al seleccionar archivo: {e}", severity="error", timeout=3)

    @on(Button.Pressed, "#path-file")
    async def on_path_file(self) -> None:
        def on_input(path: Optional[str]) -> None:
            if path and Path(path).exists():
                self.current_file_path = path
                self.app.call_later(self._update_file_buttons)
                self.app.notify("✓ Ruta de archivo establecida", severity="information", timeout=2)
            elif path:
                self.app.notify("La ruta no existe", severity="error", timeout=2)

        self.app.push_screen(InputModal("Ruta del archivo", placeholder="/ruta/a/archivo.pdf"), on_input)

    @on(Button.Pressed, "#remove-file")
    async def on_remove_file(self) -> None:
        self.current_file_path = ""
        await self._update_file_buttons()
        self.app.notify("Archivo eliminado", severity="information", timeout=2)

    def action_save(self) -> None:
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", TextArea).text.strip()
        url = self.query_one("#url-input", Input).value.strip()

        if not title:
            self.app.notify("El título es obligatorio", severity="error", timeout=2)
            return

        self.dismiss({
            "title": title,
            "description": description,
            "url": url if url else None,
            "image_path": self.current_image_path if self.current_image_path else None,
            "file_path": self.current_file_path if self.current_file_path else None,
            "tags": self.selected_tag_ids,
            "target_task_ids": list(getattr(self, "selected_tasks", []))
        })

    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()
            return

        if event.key == "ctrl+enter":
            event.prevent_default()
            event.stop()
            text_area = self.query_one("#description-input", TextArea)
            current_text = text_area.text
            cursor_line, cursor_col = text_area.cursor_location
            lines = current_text.split('\n')
            if cursor_line < len(lines):
                line = lines[cursor_line]
                new_line = line[:cursor_col] + '\n' + line[cursor_col:]
                lines[cursor_line] = new_line
                text_area.text = '\n'.join(lines)
            return

    def on_destroy(self) -> None:
        pass

class RecordAudioModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    RecordAudioModal { align: center middle; }
    RecordAudioModal > VerticalScroll {
        width: 60; height: 22; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    RecordAudioModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    RecordAudioModal .timer-display { text-align: center; text-style: bold; color: $warning; width: 100%; margin: 1 0; }
    RecordAudioModal .status-label { text-align: center; color: $accent; width: 100%; margin-bottom: 1; }
    RecordAudioModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    RecordAudioModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.recorder = AudioRecorder()
        self.start_time = None
        self.timer = None
        self.audios_dir = Path.home() / "todo" / "audios"
        self.audios_dir.mkdir(exist_ok=True, parents=True)

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("⏺ Grabar Nota de Voz", classes="modal-title")
            yield Label("00:00", id="timer-display", classes="timer-display")
            yield Label("Pulsa 'Grabar' para empezar...", id="status-label", classes="status-label")
            with Horizontal(classes="button-row"):
                yield Button("⏺ Grabar", variant="error", id="btn-record")
                yield Button("⏹ Detener", variant="primary", id="btn-stop")
                yield Button("✖ Cancelar", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#btn-stop", Button).disabled = True

    def _update_audio_timer(self) -> None:
        if self.recorder.recording and self.start_time:
            elapsed = int((datetime.now() - self.start_time).total_seconds())
            mins, secs = divmod(elapsed, 60)
            self.query_one("#timer-display", Label).update(f"{mins:02d}:{secs:02d}")

    @on(Button.Pressed, "#btn-record")
    def on_start_recording(self) -> None:
        if not _HAS_SOUNDDEVICE:
            self.app.notify("Grabación no disponible: falta el paquete 'sounddevice'", severity="error", timeout=4)
            return
        try:
            self.recorder.start()
            self.start_time = datetime.now()
            self.query_one("#btn-record", Button).disabled = True
            self.query_one("#btn-stop", Button).disabled = False
            self.query_one("#status-label", Label).update("⏺ Grabando audio desde el micrófono...")
            self.timer = self.set_interval(0.2, self._update_audio_timer)
        except Exception as e:
            self.app.notify(f"Error al acceder al micrófono: {e}", severity="error", timeout=4)

    @on(Button.Pressed, "#btn-stop")
    def on_stop_recording(self) -> None:
        if not self.recorder.recording:
            return
        if self.timer:
            self.timer.stop()
        self.query_one("#btn-stop", Button).disabled = True
        self.query_one("#btn-cancel", Button).disabled = True
        self.query_one("#status-label", Label).update("⏳ Procesando y guardando audio a MP3…")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mp3_path = str(self.audios_dir / f"voz_{timestamp}.mp3")
        self._export_in_thread(mp3_path)

    @work(thread=True)
    def _export_in_thread(self, mp3_path: str) -> None:
        duration = self.recorder.stop_and_export(mp3_path)
        self.app.call_later(self._finish_export, mp3_path, duration)

    def _finish_export(self, mp3_path: str, duration: float) -> None:
        if duration > 0 and os.path.exists(mp3_path):
            self.dismiss({"audio_path": mp3_path, "duration": duration})
        else:
            self.app.notify("No se capturó audio o falló la exportación", severity="error", timeout=3)
            self.dismiss(None)

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        if self.timer:
            self.timer.stop()
        self.recorder.cancel()
        self.dismiss(None)


class AudioPlayerModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    AudioPlayerModal { align: center middle; }
    AudioPlayerModal > VerticalScroll {
        width: 72; height: auto; max-height: 24; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    AudioPlayerModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    AudioPlayerModal .time-label { text-align: center; text-style: bold; color: $accent; width: 100%; margin: 1 0; }
    AudioPlayerModal .progress-bar { text-align: center; color: $success; width: 100%; margin-bottom: 1; }
    AudioPlayerModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; layout: horizontal; }
    AudioPlayerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("q", "close", show=False),
        Binding("space", "toggle_play", show=False),
    ]

    def __init__(self, title: str, audio_path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.audio_title = title
        self.audio_path = audio_path
        self.player = AudioPlayer()
        self.timer = None

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(f"🔊 {self.audio_title}", classes="modal-title")
            yield Label("00:00 / 00:00", id="time-label", classes="time-label")
            yield Label("[====================]", id="progress-bar", classes="progress-bar")
            with Horizontal(classes="button-row"):
                yield Button("▶ Play", variant="primary", id="btn-play")
                yield Button("⏸ Pausa", variant="default", id="btn-pause")
                yield Button("⏹ Stop", variant="error", id="btn-stop")
            with Horizontal(classes="button-row"):
                yield Button("⏪ -5s", variant="default", id="btn-rewind")
                yield Button("⏩ +5s", variant="default", id="btn-forward")
                yield Button("✖ Cerrar", variant="default", id="btn-close")

    def on_mount(self) -> None:
        if not self.audio_path or not os.path.exists(self.audio_path) or not self.player.load(self.audio_path):
            self._open_external_fallback()
            return
        self.player.play()
        self.timer = self.set_interval(0.25, self._update_ui)

    def _open_external_fallback(self) -> None:
        if self.audio_path and os.path.exists(self.audio_path):
            self.app.notify(f"🔊 Abriendo '{self.audio_title}' en el reproductor del sistema...", severity="information", timeout=3)
            try:
                if platform.system() == "Windows":
                    os.startfile(self.audio_path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", self.audio_path])
                else:
                    subprocess.Popen(["xdg-open", self.audio_path])
            except Exception as e:
                self.app.notify(f"Error al abrir archivo de audio: {e}", severity="error", timeout=3)
        else:
            self.app.notify("El archivo de audio no existe", severity="error", timeout=3)
        self.dismiss(True)

    def _update_ui(self) -> None:
        pos = self.player.position
        dur = self.player.duration
        pos_m, pos_s = divmod(int(pos), 60)
        dur_m, dur_s = divmod(int(dur), 60)
        self.query_one("#time-label", Label).update(f"{pos_m:02d}:{pos_s:02d} / {dur_m:02d}:{dur_s:02d}")

        bar_len = 20
        ratio = (pos / dur) if dur > 0 else 0.0
        filled = int(ratio * bar_len)
        bar = "[" + "=" * filled + " " * (bar_len - filled) + "]"
        self.query_one("#progress-bar", Label).update(bar)

        if not self.player.is_playing and pos >= dur and dur > 0:
            self.query_one("#btn-play", Button).label = "▶ Play"

    @on(Button.Pressed, "#btn-play")
    def on_play_btn(self) -> None:
        if self.player.is_playing:
            self.player.pause()
            self.query_one("#btn-play", Button).label = "▶ Play"
        else:
            if self.player._backend == "pygame" and self.player.position == 0:
                self.player.play()
            else:
                self.player.resume() if self.player.position > 0 else self.player.play()
            self.query_one("#btn-play", Button).label = "⏸ Pausa"

    @on(Button.Pressed, "#btn-pause")
    def on_pause_btn(self) -> None:
        self.player.pause()
        self.query_one("#btn-play", Button).label = "▶ Play"

    @on(Button.Pressed, "#btn-stop")
    def on_stop_btn(self) -> None:
        self.player.stop()
        self.query_one("#btn-play", Button).label = "▶ Play"
        self._update_ui()

    @on(Button.Pressed, "#btn-rewind")
    def on_rewind(self) -> None:
        self.player.seek(self.player.position - 5.0)

    @on(Button.Pressed, "#btn-forward")
    def on_forward(self) -> None:
        self.player.seek(self.player.position + 5.0)

    @on(Button.Pressed, "#btn-close")
    def on_close_btn(self) -> None:
        self.action_close()

    def action_toggle_play(self) -> None:
        self.on_play_btn()

    def on_unmount(self) -> None:
        if self.timer:
            self.timer.stop()
        self.player.stop()

    def action_close(self) -> None:
        if self.timer:
            self.timer.stop()
        self.player.stop()
        self.dismiss(True)


class VoiceNoteEditModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    VoiceNoteEditModal { align: center middle; }
    VoiceNoteEditModal > VerticalScroll {
        width: 90%; max-width: 100; height: 90%; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    VoiceNoteEditModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    VoiceNoteEditModal .section-label { margin-top: 1; margin-bottom: 0; color: $text-muted; }
    VoiceNoteEditModal Input { width: 100%; margin-bottom: 0; }
    VoiceNoteEditModal #description-input { width: 100%; height: 5; border: solid $primary; padding: 1; }
    VoiceNoteEditModal .audio-info { width: 100%; padding: 1; background: $surface-lighten-1; border: solid $primary-background; color: $success; }
    VoiceNoteEditModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 2; }
    VoiceNoteEditModal .audio-button-row { width: 100%; height: auto; align: left middle; layout: horizontal; margin-bottom: 1; }
    VoiceNoteEditModal .tags-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; layout: horizontal; }
    VoiceNoteEditModal .tags-display { width: 1fr; padding: 0 1; }
    VoiceNoteEditModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]

    def __init__(self, modal_title: str = "🎤 Nota de Voz", initial_title: str = "",
                 initial_description: str = "", initial_audio: str = "", initial_duration: float = 0.0,
                 all_tags: list[Tag] = None, selected_tag_ids: list[int] = None, selected_tasks: list[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.modal_title = modal_title
        self.initial_title = initial_title
        self.initial_description = initial_description
        self.current_audio_path = initial_audio or ""
        self.current_duration = initial_duration
        self.all_tags = all_tags or []
        self.selected_tag_ids = list(selected_tag_ids) if selected_tag_ids else []
        self.selected_tasks = list(selected_tasks) if selected_tasks else []
        self.audios_dir = Path.home() / "todo" / "audios"
        self.audios_dir.mkdir(exist_ok=True, parents=True)

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(self.modal_title, classes="modal-title")
            yield Label("Título:", classes="section-label")
            yield UndoableInput(value=self.initial_title, placeholder="Título de la nota de voz...", id="title-input")
            yield Label("Descripción (opcional):", classes="section-label")
            yield UndoableTextArea(self.initial_description, id="description-input", show_line_numbers=False)
            yield Label("Etiquetas:", classes="section-label")
            with Horizontal(classes="tags-row"):
                yield Label(self._format_tags(), id="tags-display", classes="tags-display")
                yield Button("🏷️ Seleccionar", id="select-tags")
            yield Label("Tareas asociadas (opcional):", classes="section-label")
            with Horizontal(classes="tags-row"):
                yield Label(self._format_tasks(), id="task-display", classes="tags-display")
                yield Button("📌 Seleccionar", id="select-task")
            yield Label("Audio:", classes="section-label")
            with Horizontal(id="audio-button-row", classes="tools-row"):
                pass
            yield Container(id="audio-info-container")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        if not hasattr(self, "selected_tasks"):
            self.selected_tasks = []
        self.query_one("#title-input", Input).focus()
        await self._update_audio_buttons()

    def _format_tags(self) -> str:
        if not self.selected_tag_ids:
            return "Sin etiquetas"
        names = [t.name for tid in self.selected_tag_ids for t in self.all_tags if t.id == tid]
        return f"🏷️ {', '.join(names)}" if names else "Sin etiquetas"

    def _format_tasks(self) -> str:
        selected_tasks = getattr(self, "selected_tasks", [])
        if not selected_tasks:
            return "Sin tareas asociadas"
        all_tasks = getattr(self.app, "tasks", [])
        names = []
        for tid in selected_tasks:
            task = next((t for t in all_tasks if t.id == tid), None)
            if task:
                txt = task.text[:25] + "..." if len(task.text) > 25 else task.text
                names.append(txt)
        return f"📌 {', '.join(names)}" if names else "Sin tareas asociadas"

    @on(Button.Pressed, "#select-task")
    def on_select_task(self) -> None:
        def on_tasks_selected(result) -> None:
            if result is not None:
                self.selected_tasks = result
                self.query_one("#task-display", Label).update(self._format_tasks())
        tasks = getattr(self.app, "tasks", [])
        current_ids = getattr(self, "selected_tasks", [])
        self.app.push_screen(MultiTaskPickerModal(tasks=tasks, selected_task_ids=current_ids), on_tasks_selected)

    async def _update_audio_buttons(self) -> None:
        button_row = self.query_one("#audio-button-row", Horizontal)
        await button_row.remove_children()

        await button_row.mount(Button("⏺ Grabar", variant="error", id="record-audio"))
        await button_row.mount(Button("📁 Importar", variant="default", id="import-audio"))

        if self.current_audio_path:
            await button_row.mount(Button("▶ Escuchar", variant="success", id="play-audio"))
            await button_row.mount(Button("🗑️ Quitar", variant="warning", id="remove-audio"))

        info_container = self.query_one("#audio-info-container", Container)
        await info_container.remove_children()

        if self.current_audio_path:
            dur = int(self.current_duration)
            mins, secs = divmod(dur, 60)
            name = Path(self.current_audio_path).name
            await info_container.mount(
                Label(f"🔊 Audio: {name} ({mins:02d}:{secs:02d})", classes="audio-info")
            )

    @on(Button.Pressed, "#select-tags")
    def on_select_tags(self) -> None:
        def on_tags_selected(result: Optional[list[int]]) -> None:
            if result is not None:
                self.selected_tag_ids = result
                self.query_one("#tags-display", Label).update(self._format_tags())
        self.app.push_screen(TagPickerModal(all_tags=self.all_tags, selected_tag_ids=self.selected_tag_ids), on_tags_selected)

    @on(Button.Pressed, "#record-audio")
    def on_record_audio(self) -> None:
        def on_record_result(result: Optional[dict]) -> None:
            if result:
                self.current_audio_path = result["audio_path"]
                self.current_duration = result["duration"]
                self.run_worker(self._update_audio_buttons())
        self.app.push_screen(RecordAudioModal(), on_record_result)

    @on(Button.Pressed, "#import-audio")
    async def on_import_audio(self) -> None:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            file_path = await loop.run_in_executor(executor, self._browse_audio_file)

        if file_path and os.path.exists(file_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = Path(file_path).suffix or ".mp3"
            dest = self.audios_dir / f"voz_imp_{timestamp}{ext}"
            shutil.copy2(file_path, dest)
            self.current_audio_path = str(dest)
            if _HAS_PYDUB:
                try:
                    from pydub import AudioSegment
                    self.current_duration = len(AudioSegment.from_file(str(dest))) / 1000.0
                except Exception:
                    self.current_duration = 0.0
            else:
                self.current_duration = 0.0
            await self._update_audio_buttons()
            self.app.notify("🎤 Audio importado correctamente", severity="information")

    def _browse_audio_file(self) -> Optional[str]:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            file_path = filedialog.askopenfilename(
                title="Seleccionar archivo MP3",
                filetypes=[
                    ("Archivos MP3", "*.mp3"),
                    ("Archivos de audio", "*.mp3 *.wav *.ogg *.m4a"),
                    ("Todos los archivos", "*.*")
                ]
            )
            root.destroy()
            if file_path:
                return file_path
        except Exception: pass
        try:
            system = platform.system()
            if system == "Windows":
                ps_script = '''
                Add-Type -AssemblyName System.Windows.Forms
                $FileBrowser = New-Object System.Windows.Forms.OpenFileDialog -Property @{
                    Filter = 'Archivos MP3 (*.mp3)|*.mp3|Archivos de audio (*.mp3;*.wav;*.ogg;*.m4a)|*.mp3;*.wav;*.ogg;*.m4a|Todos (*.*)|*.*'
                    Title = 'Seleccionar archivo MP3'
                }
                $null = $FileBrowser.ShowDialog()
                Write-Output $FileBrowser.FileName
                '''
                res = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=300)
                path = res.stdout.strip()
                return path if path else None
            elif system == "Darwin":
                script = 'set theFile to choose file with prompt "Seleccionar audio MP3"\nreturn POSIX path of theFile'
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
                path = res.stdout.strip()
                return path if path else None
            else:
                try:
                    res = subprocess.run(["zenity", "--file-selection", "--title=Seleccionar audio MP3", "--file-filter=*.mp3"], capture_output=True, text=True, timeout=300)
                    return res.stdout.strip() or None
                except FileNotFoundError:
                    return None
        except Exception:
            return None

    @on(Button.Pressed, "#play-audio")
    def on_play_audio(self) -> None:
        if self.current_audio_path and os.path.exists(self.current_audio_path):
            title = self.query_one("#title-input", Input).value.strip() or self.initial_title or "Audio"
            self.app.push_screen(AudioPlayerModal(title, self.current_audio_path))
        else:
            self.app.notify("El archivo de audio no existe", severity="error", timeout=2)

    @on(Button.Pressed, "#remove-audio")
    async def on_remove_audio(self) -> None:
        self.current_audio_path = ""
        self.current_duration = 0.0
        await self._update_audio_buttons()
        self.app.notify("Audio quitado", severity="information")

    def action_save(self) -> None:
        title = self.query_one("#title-input", Input).value.strip()
        description = self.query_one("#description-input", TextArea).text.strip()
        if not title:
            self.app.notify("El título es obligatorio", severity="error", timeout=2)
            return
        self.dismiss({
            "title": title,
            "description": description,
            "audio_path": self.current_audio_path,
            "duration": self.current_duration,
            "tags": self.selected_tag_ids,
            "target_task_ids": list(getattr(self, "selected_tasks", []))
        })

    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TaskNotesModal(ModalScreen[list[Note]]):
    DEFAULT_CSS = """
    TaskNotesModal { align: center middle; }
    TaskNotesModal > VerticalScroll {
        width: 82; height: 42; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    TaskNotesModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    TaskNotesModal .search-label { color: $text-muted; margin-bottom: 0; }
    TaskNotesModal Input { width: 100%; margin-bottom: 1; }
    TaskNotesModal #notes-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    TaskNotesModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    TaskNotesModal .hint { width: 100%; height: auto; text-align: center; color: $text-muted; margin: 1 0; }
    TaskNotesModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    TaskNotesModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("a", "add_note", show=False),
        Binding("e", "edit_note", show=False),
        Binding("d", "delete_note", show=False),
        Binding("enter", "view_note", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, notes: list[Note], next_note_id: int, global_notes: list[Note] = None, all_tags: list[Tag] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.notes = [Note(id=n.id, title=n.title, description=n.description, url=n.url,
                           image_path=n.image_path, file_path=n.file_path, created_at=n.created_at,
                           tags=list(n.tags) if n.tags else []) for n in notes]
        self.next_note_id = next_note_id
        self.global_notes = global_notes or []
        self.all_tags = all_tags or []
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_notes: list[Note] = []
        self.selected_index = 0 if notes else -1

    def _get_filtered_notes(self) -> list[Note]:
        if not self.search_query:
            return self.notes
        q = self.search_query.lower()
        return [n for n in self.notes if q in n.title.lower() or q in n.description.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📝 Notas de la Tarea", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar notas...", id="task-notes-search-input")
            yield Container(id="notes-list")
            yield Label("↑↓/k/j: Navegar | a: Añadir | e: Editar | d: Eliminar | /: Buscar | Enter: Ver | Esc: Cerrar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("➕ Añadir", variant="primary", id="add")
                yield Button("📌 Existentes", variant="warning", id="select-existing")
                yield Button("👁️ Ver", variant="default", id="view")
                yield Button("✏️ Editar", variant="default", id="edit")
                yield Button("🗑️ Eliminar", variant="error", id="delete")

    async def on_mount(self) -> None:
        await self.refresh_notes_list()
        try:
            self.query_one("#task-notes-search-input", Input).blur()
        except: pass

    async def refresh_notes_list(self) -> None:
        notes_list = self.query_one("#notes-list", Container)
        await notes_list.remove_children()
        
        self.filtered_notes = self._get_filtered_notes()
        
        if not self.notes:
            await notes_list.mount(Label("No hay notas embebidas. Pulsa 'a' para añadir una.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_notes:
            await notes_list.mount(Label(f"No se encontraron notas para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_notes) or self.selected_index < 0:
                self.selected_index = max(0, len(self.filtered_notes) - 1)
            for i, note in enumerate(self.filtered_notes):
                w = NoteWidget(note, all_tags=self.all_tags, id=f"t-note-{i}")
                await notes_list.mount(w)
                if i == self.selected_index:
                    w.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#task-notes-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#task-notes-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_notes_list)

    @on(Button.Pressed, "#select-existing")
    def on_select_existing(self) -> None:
        def on_result(result: Optional[list[Note]]) -> None:
            if result is not None:
                self.notes = result
                if self.notes:
                    self.next_note_id = max((n.id for n in self.notes), default=0) + 1
                self.call_later(self.refresh_notes_list)
        global_notes = self.global_notes or getattr(self.app, "notes", [])
        current_ids = [n.id for n in self.notes]
        self.app.push_screen(GlobalNotesPickerModal(global_notes, selected_note_ids=current_ids), on_result)

    @on(Input.Changed, "#task-notes-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_notes_list()

    @on(Input.Submitted, "#task-notes-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_close(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(self.notes)

    def action_move_up(self) -> None:
        if self.notes and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.notes and self.selected_index < len(self.notes) - 1:
            self.selected_index += 1
            self.update_selection()

    def update_selection(self) -> None:
        for i in range(len(self.notes)):
            try:
                w = self.query_one(f"#t-note-{i}", NoteWidget)
                w.set_class(i == self.selected_index, "selected")
            except: pass

    def action_add_note(self) -> None:
        def on_result(result: Optional[dict]) -> None:
            if result:
                note = Note(
                    id=self.next_note_id,
                    title=result["title"],
                    description=result.get("description", ""),
                    url=result.get("url"),
                    image_path=result.get("image_path"),
                    file_path=result.get("file_path"),
                    tags=result.get("tags", [])
                )
                self.next_note_id += 1
                self.notes.append(note)
                self.selected_index = len(self.notes) - 1
                self.call_later(self.refresh_notes_list)
        self.app.push_screen(NoteEditModal(modal_title="📝 Nueva Nota de Tarea", all_tags=self.all_tags), on_result)

    def action_edit_note(self) -> None:
        if not self.notes or self.selected_index < 0 or self.selected_index >= len(self.notes):
            return
        note = self.notes[self.selected_index]
        def on_result(result: Optional[dict]) -> None:
            if result:
                note.title = result["title"]
                note.description = result.get("description", "")
                note.url = result.get("url")
                note.image_path = result.get("image_path")
                note.file_path = result.get("file_path")
                note.tags = result.get("tags", [])
                self.call_later(self.refresh_notes_list)
        self.app.push_screen(NoteEditModal(
            modal_title="📝 Editar Nota de Tarea",
            initial_title=note.title,
            initial_description=note.description,
            initial_url=note.url or "",
            initial_image=note.image_path or "",
            initial_file=note.file_path or "",
            all_tags=self.all_tags,
            selected_tag_ids=note.tags
        ), on_result)

    def action_view_note(self) -> None:
        if not self.notes or self.selected_index < 0 or self.selected_index >= len(self.notes):
            return
        note = self.notes[self.selected_index]
        content_lines = [f"[bold]{note.title}[/bold]", ""]
        if note.description: content_lines.extend([note.description, ""])
        if note.url: content_lines.append(f"🔗 Enlace: {note.url}")
        if note.image_path: content_lines.append(f"📷 Imagen: {note.image_path}")
        if note.file_path: content_lines.append(f"📎 Archivo: {note.file_path}")
        content = "\n".join(content_lines)
        self.app.push_screen(InputModal("📝 Ver Nota", placeholder=content), lambda x: None)

    def action_delete_note(self) -> None:
        if not self.notes or self.selected_index < 0 or self.selected_index >= len(self.notes):
            return
        note = self.notes[self.selected_index]
        txt = note.title[:30] + "..." if len(note.title) > 30 else note.title
        def on_confirm(yes: bool) -> None:
            if yes:
                self.notes.remove(note)
                if self.selected_index >= len(self.notes) and self.selected_index > 0:
                    self.selected_index -= 1
                if not self.notes:
                    self.selected_index = -1
                self.call_later(self.refresh_notes_list)
        self.app.push_screen(ConfirmModal(f"¿Eliminar nota '{txt}'?"), on_confirm)

    @on(Button.Pressed, "#add")
    def on_add(self) -> None: self.action_add_note()
    @on(Button.Pressed, "#edit")
    def on_edit(self) -> None: self.action_edit_note()
    @on(Button.Pressed, "#view")
    def on_view(self) -> None: self.action_view_note()
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None: self.action_delete_note()
    def action_close(self) -> None: self.dismiss(self.notes)


class VoiceNotesModal(ModalScreen[list[VoiceNote]]):
    DEFAULT_CSS = """
    VoiceNotesModal { align: center middle; }
    VoiceNotesModal > VerticalScroll {
        width: 82; height: 42; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    VoiceNotesModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    VoiceNotesModal .search-label { color: $text-muted; margin-bottom: 0; }
    VoiceNotesModal Input { width: 100%; margin-bottom: 1; }
    VoiceNotesModal #voice-notes-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    VoiceNotesModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    VoiceNotesModal .hint { width: 100%; height: auto; text-align: center; color: $text-muted; margin: 1 0; }
    VoiceNotesModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    VoiceNotesModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("r", "record_audio", show=False),
        Binding("e", "edit_audio", show=False),
        Binding("d", "delete_audio", show=False),
        Binding("enter", "play_audio", show=False),
        Binding("p", "play_audio", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, voice_notes: list[VoiceNote], next_voice_note_id: int,
                 global_voice_notes: list[VoiceNote] = None, all_tags: list[Tag] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.voice_notes = [VoiceNote(id=v.id, title=v.title, audio_path=v.audio_path,
                                      description=v.description, duration=v.duration,
                                      created_at=v.created_at, tags=list(v.tags) if v.tags else [])
                            for v in voice_notes]
        self.next_voice_note_id = next_voice_note_id
        self.global_voice_notes = global_voice_notes or []
        self.all_tags = all_tags or []
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_voice_notes: list[VoiceNote] = []
        self.selected_index = 0 if voice_notes else -1

    def _get_filtered_voice_notes(self) -> list[VoiceNote]:
        if not self.search_query:
            return self.voice_notes
        q = self.search_query.lower()
        return [v for v in self.voice_notes if q in v.title.lower() or q in v.description.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🎤 Audios de la Tarea", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar audios...", id="vn-search-input")
            yield Container(id="voice-notes-list")
            yield Label("↑↓/k/j: Navegar | r: Grabar | e: Editar | d: Eliminar | /: Buscar | Enter/p: Reproducir | Esc: Cerrar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("⏺ Añadir/Grabar", variant="primary", id="add")
                yield Button("📌 Existentes", variant="warning", id="select-existing")
                yield Button("▶ Reproducir", variant="success", id="play")
                yield Button("✏️ Editar", variant="default", id="edit")
                yield Button("🗑️ Eliminar", variant="error", id="delete")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#vn-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        vn_list = self.query_one("#voice-notes-list", Container)
        await vn_list.remove_children()
        
        self.filtered_voice_notes = self._get_filtered_voice_notes()
        
        if not self.voice_notes:
            await vn_list.mount(Label("No hay audios embebidos. Pulsa 'Añadir/Grabar' para crear uno.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_voice_notes:
            await vn_list.mount(Label(f"No se encontraron audios para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_voice_notes) or self.selected_index < 0:
                self.selected_index = max(0, len(self.filtered_voice_notes) - 1)
            for i, vn in enumerate(self.filtered_voice_notes):
                w = VoiceNoteWidget(vn, all_tags=self.all_tags, id=f"vn-item-{i}")
                await vn_list.mount(w)
                if i == self.selected_index:
                    w.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#vn-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#vn-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#vn-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#vn-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_close(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(self.voice_notes)

    def action_move_up(self) -> None:
        if self.voice_notes and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.voice_notes and self.selected_index < len(self.voice_notes) - 1:
            self.selected_index += 1
            self.update_selection()

    def update_selection(self) -> None:
        for i in range(len(self.voice_notes)):
            try:
                w = self.query_one(f"#t-vn-{i}", VoiceNoteWidget)
                w.set_class(i == self.selected_index, "selected")
            except: pass

    def action_record_audio(self) -> None:
        def on_result(result: Optional[dict]) -> None:
            if result:
                vn = VoiceNote(
                    id=self.next_voice_note_id,
                    title=result["title"],
                    audio_path=result.get("audio_path", ""),
                    description=result.get("description", ""),
                    duration=result.get("duration", 0.0),
                    tags=result.get("tags", [])
                )
                self.next_voice_note_id += 1
                self.voice_notes.append(vn)
                self.selected_index = len(self.voice_notes) - 1
                self.call_later(self.refresh_list)
        self.app.push_screen(VoiceNoteEditModal(modal_title="🎤 Nuevo Audio de Tarea", all_tags=self.all_tags), on_result)

    def action_edit_audio(self) -> None:
        if not self.voice_notes or self.selected_index < 0 or self.selected_index >= len(self.voice_notes):
            return
        vn = self.voice_notes[self.selected_index]
        def on_result(result: Optional[dict]) -> None:
            if result:
                vn.title = result["title"]
                vn.description = result.get("description", "")
                vn.audio_path = result.get("audio_path", "")
                vn.duration = result.get("duration", 0.0)
                vn.tags = result.get("tags", [])
                self.call_later(self.refresh_list)
        self.app.push_screen(VoiceNoteEditModal(
            modal_title="🎤 Editar Audio de Tarea",
            initial_title=vn.title,
            initial_description=vn.description,
            initial_audio=vn.audio_path,
            initial_duration=vn.duration,
            all_tags=self.all_tags,
            selected_tag_ids=vn.tags
        ), on_result)

    def action_play_audio(self) -> None:
        if not self.voice_notes or self.selected_index < 0 or self.selected_index >= len(self.voice_notes):
            return
        vn = self.voice_notes[self.selected_index]
        self.app.push_screen(AudioPlayerModal(vn.title, vn.audio_path))

    def action_delete_audio(self) -> None:
        if not self.voice_notes or self.selected_index < 0 or self.selected_index >= len(self.voice_notes):
            return
        vn = self.voice_notes[self.selected_index]
        txt = vn.title[:30] + "..." if len(vn.title) > 30 else vn.title
        def on_confirm(yes: bool) -> None:
            if yes:
                if vn.audio_path and os.path.exists(vn.audio_path):
                    try: os.remove(vn.audio_path)
                    except Exception: pass
                self.voice_notes.remove(vn)
                if self.selected_index >= len(self.voice_notes) and self.selected_index > 0:
                    self.selected_index -= 1
                if not self.voice_notes:
                    self.selected_index = -1
                self.call_later(self.refresh_list)
        self.app.push_screen(ConfirmModal(f"¿Eliminar audio '{txt}'?"), on_confirm)



    @on(Button.Pressed, "#add")
    def on_add(self) -> None: self.action_record_audio()
    @on(Button.Pressed, "#play")
    def on_play(self) -> None: self.action_play_audio()
    @on(Button.Pressed, "#edit")
    def on_edit(self) -> None: self.action_edit_audio()
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None: self.action_delete_audio()
    def action_close(self) -> None: self.dismiss(self.voice_notes)


class GlobalVoiceNotesPickerModal(ModalScreen[Optional[list[VoiceNote]]]):
    DEFAULT_CSS = """
    GlobalVoiceNotesPickerModal { align: center middle; }
    GlobalVoiceNotesPickerModal > VerticalScroll {
        width: 75; height: 34; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    GlobalVoiceNotesPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    GlobalVoiceNotesPickerModal .search-label { color: $text-muted; margin-bottom: 0; }
    GlobalVoiceNotesPickerModal Input { width: 100%; margin-bottom: 1; }
    GlobalVoiceNotesPickerModal #gvn-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    GlobalVoiceNotesPickerModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    GlobalVoiceNotesPickerModal .item:hover { background: $boost; }
    GlobalVoiceNotesPickerModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    GlobalVoiceNotesPickerModal .item.checked { color: $success; }
    GlobalVoiceNotesPickerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    GlobalVoiceNotesPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    GlobalVoiceNotesPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    GlobalVoiceNotesPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_item", show=False),
        Binding("enter", "save", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, global_voice_notes: list[VoiceNote], selected_vn_ids: list[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.global_voice_notes = global_voice_notes or []
        self.selected_vn_ids = set(selected_vn_ids or [])
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_voice_notes: list[VoiceNote] = []
        self.selected_index = 0 if self.global_voice_notes else -1

    def _get_filtered_voice_notes(self) -> list[VoiceNote]:
        if not self.search_query:
            return self.global_voice_notes
        q = self.search_query.lower()
        return [v for v in self.global_voice_notes if q in v.title.lower() or q in v.description.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🌐 Seleccionar Audios Globales", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar audios...", id="gvn-search-input")
            yield Container(id="gvn-list")
            yield Label("↑↓ Navegar | Espacio: Marcar | /: Buscar | Enter: Guardar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Seleccionar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#gvn-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        container = self.query_one("#gvn-list", Container)
        await container.remove_children()
        
        self.filtered_voice_notes = self._get_filtered_voice_notes()
        
        if not self.global_voice_notes:
            await container.mount(Label("No hay audios globales disponibles.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_voice_notes:
            await container.mount(Label(f"No se encontraron audios para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_voice_notes) or self.selected_index < 0:
                self.selected_index = 0
            
            for i, vn in enumerate(self.filtered_voice_notes):
                dur = int(vn.duration)
                m, s = divmod(dur, 60)
                checked = "☑" if vn.id in self.selected_vn_ids else "☐"
                item = Static(f"{checked}  🎤 {vn.title} ({m:02d}:{s:02d})", id=f"gvn-{i}", classes="item")
                await container.mount(item)
                if vn.id in self.selected_vn_ids:
                    item.add_class("checked")
                if i == self.selected_index:
                    item.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#gvn-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#gvn-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#gvn-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#gvn-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.filtered_voice_notes and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.filtered_voice_notes and self.selected_index < len(self.filtered_voice_notes) - 1:
            self.selected_index += 1
            self.update_selection()

    def action_toggle_item(self) -> None:
        if self.search_focused: return
        if self.filtered_voice_notes and 0 <= self.selected_index < len(self.filtered_voice_notes):
            vn = self.filtered_voice_notes[self.selected_index]
            if vn.id in self.selected_vn_ids:
                self.selected_vn_ids.remove(vn.id)
            else:
                self.selected_vn_ids.add(vn.id)
            self.call_later(self.refresh_list)

    def update_selection(self) -> None:
        for i in range(len(self.filtered_voice_notes)):
            try:
                item = self.query_one(f"#gvn-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except Exception: pass

    def action_save(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        selected = [vn for vn in self.global_voice_notes if vn.id in self.selected_vn_ids]
        self.dismiss(selected)

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)
        self.scroll_to_selected()

    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#gvn-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass

    def action_save(self) -> None:
        if self.selected_indices:
            self.dismiss([self.global_voice_notes[i] for i in sorted(self.selected_indices)])
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)




class GlobalCanvasPickerModal(ModalScreen[Optional[list[Canvas]]]):
    DEFAULT_CSS = """
    GlobalCanvasPickerModal { align: center middle; }
    GlobalCanvasPickerModal > VerticalScroll {
        width: 75; height: 34; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    GlobalCanvasPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    GlobalCanvasPickerModal .search-label { color: $text-muted; margin-bottom: 0; }
    GlobalCanvasPickerModal Input { width: 100%; margin-bottom: 1; }
    GlobalCanvasPickerModal #gc-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    GlobalCanvasPickerModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    GlobalCanvasPickerModal .item:hover { background: $boost; }
    GlobalCanvasPickerModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    GlobalCanvasPickerModal .item.checked { color: $success; }
    GlobalCanvasPickerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    GlobalCanvasPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    GlobalCanvasPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    GlobalCanvasPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_item", show=False),
        Binding("enter", "save", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, global_canvas_list: list[Canvas], selected_canvas_ids: list[int] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.global_canvas_list = global_canvas_list or []
        self.selected_canvas_ids = set(selected_canvas_ids or [])
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_canvas: list[Canvas] = []
        self.selected_index = 0 if self.global_canvas_list else -1

    def _get_filtered_canvas(self) -> list[Canvas]:
        if not self.search_query:
            return self.global_canvas_list
        q = self.search_query.lower()
        return [c for c in self.global_canvas_list if q in c.title.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🎨 Seleccionar Pizarras Globales", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar pizarras...", id="gc-search-input")
            yield Container(id="gc-list")
            yield Label("↑↓ Navegar | Espacio: Marcar | /: Buscar | Enter: Guardar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Seleccionar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#gc-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        container = self.query_one("#gc-list", Container)
        await container.remove_children()
        
        self.filtered_canvas = self._get_filtered_canvas()
        
        if not self.global_canvas_list:
            await container.mount(Label("No hay pizarras globales disponibles.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_canvas:
            await container.mount(Label(f"No se encontraron pizarras para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_canvas) or self.selected_index < 0:
                self.selected_index = 0
            
            for i, c in enumerate(self.filtered_canvas):
                checked = "☑" if c.id in self.selected_canvas_ids else "☐"
                item = Static(f"{checked}  🎨 {c.title}", id=f"gc-{i}", classes="item")
                await container.mount(item)
                if c.id in self.selected_canvas_ids:
                    item.add_class("checked")
                if i == self.selected_index:
                    item.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#gc-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#gc-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#gc-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#gc-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.filtered_canvas and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.filtered_canvas and self.selected_index < len(self.filtered_canvas) - 1:
            self.selected_index += 1
            self.update_selection()

    def action_toggle_item(self) -> None:
        if self.search_focused: return
        if self.filtered_canvas and 0 <= self.selected_index < len(self.filtered_canvas):
            c = self.filtered_canvas[self.selected_index]
            if c.id in self.selected_canvas_ids:
                self.selected_canvas_ids.remove(c.id)
            else:
                self.selected_canvas_ids.add(c.id)
            self.call_later(self.refresh_list)

    def update_selection(self) -> None:
        for i in range(len(self.filtered_canvas)):
            try:
                item = self.query_one(f"#gc-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except Exception: pass

    def action_save(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        selected = [c for c in self.global_canvas_list if c.id in self.selected_canvas_ids]
        self.dismiss(selected)

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)



class TaskCanvasModal(ModalScreen[list[Canvas]]):
    DEFAULT_CSS = """
    TaskCanvasModal { align: center middle; }
    TaskCanvasModal > VerticalScroll {
        width: 82; height: 42; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    TaskCanvasModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    TaskCanvasModal .search-label { color: $text-muted; margin-bottom: 0; }
    TaskCanvasModal Input { width: 100%; margin-bottom: 1; }
    TaskCanvasModal #canvas-list { width: 100%; height: 16; overflow-y: auto; border: solid $primary-background; padding: 1; }
    TaskCanvasModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    TaskCanvasModal .hint { width: 100%; height: auto; text-align: center; color: $text-muted; margin: 1 0; }
    TaskCanvasModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    TaskCanvasModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("a", "add_canvas", show=False),
        Binding("e", "edit_canvas", show=False),
        Binding("d", "delete_canvas", show=False),
        Binding("enter", "edit_canvas", show=False),
        Binding("/", "focus_search", show=False),
    ]

    def __init__(self, canvas_list: list[Canvas], next_canvas_id: int,
                 global_canvas_list: list[Canvas] = None, all_tags: list[Tag] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.canvas_list = [Canvas(id=c.id, title=c.title, width=c.width, height=c.height,
                                   grid=[list(r) for r in c.grid], created_at=c.created_at,
                                   tags=list(c.tags) if c.tags else []) for c in canvas_list]
        self.next_canvas_id = next_canvas_id
        self.global_canvas_list = global_canvas_list or []
        self.all_tags = all_tags or []
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_canvas: list[Canvas] = []
        self.selected_index = 0 if canvas_list else -1

    def _get_filtered_canvas(self) -> list[Canvas]:
        if not self.search_query:
            return self.canvas_list
        q = self.search_query.lower()
        return [c for c in self.canvas_list if q in c.title.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🎨 Pizarras de la Tarea", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar pizarras...", id="task-canvas-search-input")
            yield Container(id="canvas-list")
            yield Label("↑↓/k/j: Navegar | a: Crear | e/Enter: Editar | d: Eliminar | /: Buscar | Esc: Cerrar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("➕ Crear Pizarra", variant="primary", id="add")
                yield Button("📌 Existentes", variant="warning", id="select-existing")
                yield Button("✏️ Editar", variant="default", id="edit")
                yield Button("🗑️ Eliminar", variant="error", id="delete")

    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#task-canvas-search-input", Input).blur()
        except: pass

    async def refresh_list(self) -> None:
        container = self.query_one("#canvas-list", Container)
        await container.remove_children()
        
        self.filtered_canvas = self._get_filtered_canvas()
        
        if not self.canvas_list:
            await container.mount(Label("No hay pizarras asociadas. Pulsa 'Crear Pizarra' para añadir una.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_canvas:
            await container.mount(Label(f"No se encontraron pizarras para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_canvas) or self.selected_index < 0:
                self.selected_index = max(0, len(self.filtered_canvas) - 1)
            for i, c in enumerate(self.filtered_canvas):
                w = CanvasWidget(c, id=f"t-cv-{i}")
                await container.mount(w)
                if i == self.selected_index:
                    w.selected = True

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#task-canvas-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#task-canvas-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Button.Pressed, "#select-existing")
    def on_select_existing(self) -> None:
        def on_result(result: Optional[list[Canvas]]) -> None:
            if result is not None:
                self.canvas_list = result
                if self.canvas_list:
                    self.next_canvas_id = max((c.id for c in self.canvas_list), default=0) + 1
                self.call_later(self.refresh_list)
        global_canvas = self.global_canvas_list or getattr(self.app, "canvas_list", [])
        current_ids = [c.id for c in self.canvas_list]
        self.app.push_screen(GlobalCanvasPickerModal(global_canvas, selected_canvas_ids=current_ids), on_result)

    @on(Input.Changed, "#task-canvas-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#task-canvas-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_close(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(self.canvas_list)

    def action_move_up(self) -> None:
        if self.canvas_list and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()

    def action_move_down(self) -> None:
        if self.canvas_list and self.selected_index < len(self.canvas_list) - 1:
            self.selected_index += 1
            self.update_selection()

    def update_selection(self) -> None:
        for i in range(len(self.canvas_list)):
            try:
                w = self.query_one(f"#t-cv-{i}", CanvasWidget)
                w.selected = (i == self.selected_index)
            except: pass

    def action_add_canvas(self) -> None:
        c = Canvas(id=self.next_canvas_id, title=f"Pizarra {self.next_canvas_id}", width=50, height=20)
        self.next_canvas_id += 1
        def on_result(result: Optional[dict]) -> None:
            if result:
                new_canvas = result.get("canvas")
                if new_canvas:
                    new_canvas.id = c.id
                else:
                    new_canvas = Canvas(
                        id=c.id,
                        title=result.get("title", c.title),
                        width=result.get("width", c.width),
                        height=result.get("height", c.height),
                        grid=result.get("grid", c.grid)
                    )
                self.canvas_list.append(new_canvas)
                self.selected_index = len(self.canvas_list) - 1
                self.call_later(self.refresh_list)
        self.app.push_screen(CanvasEditorModal(c), on_result)

    def action_edit_canvas(self) -> None:
        if not self.canvas_list or self.selected_index < 0 or self.selected_index >= len(self.canvas_list):
            return
        c = self.canvas_list[self.selected_index]
        def on_result(result: Optional[dict]) -> None:
            if result:
                new_c = result.get("canvas")
                if new_c:
                    c.title = new_c.title
                    c.grid = new_c.grid
                else:
                    c.title = result.get("title", c.title)
                    c.grid = result.get("grid", c.grid)
                self.call_later(self.refresh_list)
        self.app.push_screen(CanvasEditorModal(c), on_result)

    def action_delete_canvas(self) -> None:
        if not self.canvas_list or self.selected_index < 0 or self.selected_index >= len(self.canvas_list):
            return
        c = self.canvas_list[self.selected_index]
        def on_confirm(yes: bool) -> None:
            if yes:
                self.canvas_list.remove(c)
                if self.selected_index >= len(self.canvas_list) and self.selected_index > 0:
                    self.selected_index -= 1
                if not self.canvas_list:
                    self.selected_index = -1
                self.call_later(self.refresh_list)
        self.app.push_screen(ConfirmModal(f"¿Eliminar pizarra '{c.title}'?"), on_confirm)



    @on(Button.Pressed, "#add")
    def on_add(self) -> None: self.action_add_canvas()
    @on(Button.Pressed, "#edit")
    def on_edit(self) -> None: self.action_edit_canvas()
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None: self.action_delete_canvas()
    def action_close(self) -> None: self.dismiss(self.canvas_list)


class CommentsModal(ModalScreen[list[Comment]]):
    DEFAULT_CSS = """
    CommentsModal { align: center middle; }
    CommentsModal > VerticalScroll {
        width: 82; height: 30; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    CommentsModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    CommentsModal #comments-list { width: 100%; height: 14; overflow-y: auto; border: solid $primary-background; padding: 1; }
    CommentsModal .comment-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    CommentsModal .comment-item:hover { background: $boost; }
    CommentsModal .comment-item.selected { border: solid $accent; background: $surface-lighten-1; }
    CommentsModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    CommentsModal .hint { width: 100%; height: auto; text-align: center; color: $text-muted; margin: 1 0; }
    CommentsModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    CommentsModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("a", "add_comment", show=False),
        Binding("e", "edit_comment", show=False),
        Binding("d", "delete_comment", show=False),
        Binding("ctrl+o", "open_link", show=False),
        Binding("enter", "open_link", show=False),
        Binding("v", "view_image", show=False),
        Binding("f", "open_file", show=False),
    ]
    
    def __init__(self, comments: list[Comment], next_comment_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.comments = [Comment(id=c.id, title=c.title, description=c.description,
                                url=c.url, image_path=c.image_path, file_path=c.file_path,
                                created_at=c.created_at)
                        for c in comments]
        self.next_comment_id = next_comment_id
        self.selected_index = 0 if comments else -1
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("💬 Comentarios", classes="modal-title")
            yield Container(id="comments-list")
            yield Label("↑↓ Navegar | a: Añadir | e: Editar | d: Eliminar | Enter: Abrir enlace | v: Ver imagen | f: Abrir archivo | Esc: Cerrar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("➕ Añadir", variant="primary", id="add")
                yield Button("✏️ Editar", variant="default", id="edit")
                yield Button("🗑️ Eliminar", variant="error", id="delete")
    
    async def on_mount(self) -> None:
        await self.refresh_comments_list()
    
    def _truncate_comment_preview(self, text: str, max_length: int = 50) -> str:
        single_line = text.replace('\n', ' ').replace('\r', ' ')
        single_line = ' '.join(single_line.split())
        
        if len(single_line) <= max_length:
            return single_line
        return single_line[:max_length] + "..."
    
    async def refresh_comments_list(self) -> None:
        comments_list = self.query_one("#comments-list", Container)
        await comments_list.remove_children()
        
        if not self.comments:
            await comments_list.mount(Label("No hay comentarios. Pulsa 'a' para añadir uno.", classes="empty-msg"))
            self.selected_index = -1
        else:
            for i, comment in enumerate(self.comments):
                preview_text = self._truncate_comment_preview(comment.title, 35)

                link_icon = " 🔗" if comment.url else ""
                image_icon = " 📷" if comment.image_path else ""
                file_icon = " 📎" if comment.file_path else ""
                display_text = f"{preview_text}{link_icon}{image_icon}{file_icon}  [{comment.created_at}]"

                item = Static(display_text, id=f"comment-{i}", classes="comment-item")
                await comments_list.mount(item)
                if i == self.selected_index:
                    item.add_class("selected")
            self.scroll_to_selected()
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#comment-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.comments)):
            try:
                item = self.query_one(f"#comment-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.comments and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.comments and self.selected_index < len(self.comments) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_add_comment(self) -> None:
        def on_result(result: Optional[dict]) -> None:
            if result and result.get("title"):
                comment = Comment(
                    id=self.next_comment_id,
                    title=result["title"],
                    description=result.get("description", ""),
                    url=result.get("url"),
                    image_path=result.get("image_path"),
                    file_path=result.get("file_path")
                )
                self.next_comment_id += 1
                self.comments.append(comment)
                self.selected_index = len(self.comments) - 1
                self.call_later(self.refresh_comments_list)
        self.app.push_screen(CommentEditModal("💬 Nuevo Comentario"), on_result)
    
    def action_edit_comment(self) -> None:
        if not self.comments or self.selected_index < 0:
            return
        comment = self.comments[self.selected_index]
        def on_result(result: Optional[dict]) -> None:
            if result and result.get("title"):
                comment.title = result["title"]
                comment.description = result.get("description", "")
                comment.url = result.get("url")
                comment.image_path = result.get("image_path")
                comment.file_path = result.get("file_path")
                self.call_later(self.refresh_comments_list)
        self.app.push_screen(
            CommentEditModal("✏️ Editar Comentario", initial_title=comment.title,
                           initial_description=comment.description,
                           initial_url=comment.url, initial_image=comment.image_path,
                           initial_file=comment.file_path or ""),
            on_result
        )
    
    def action_delete_comment(self) -> None:
        if not self.comments or self.selected_index < 0:
            return
        comment = self.comments[self.selected_index]
        txt = self._truncate_comment_preview(comment.title, 30)
        
        def on_confirm(yes: bool) -> None:
            if yes:
                if comment.image_path and Path(comment.image_path).exists():
                    try:
                        Path(comment.image_path).unlink()
                    except:
                        pass

                if comment.file_path and Path(comment.file_path).exists():
                    try:
                        Path(comment.file_path).unlink()
                    except:
                        pass

                self.comments.pop(self.selected_index)
                if self.selected_index >= len(self.comments) and self.selected_index > 0:
                    self.selected_index -= 1
                if not self.comments:
                    self.selected_index = -1
                self.call_later(self.refresh_comments_list)
        self.app.push_screen(ConfirmModal(f"¿Eliminar comentario '{txt}'?"), on_confirm)
    
    def action_open_link(self) -> None:
        if not self.comments or self.selected_index < 0:
            return
        comment = self.comments[self.selected_index]
        if comment.url:
            try:
                webbrowser.open(comment.url)
                self.app.notify(f"Abriendo: {comment.url}", severity="information")
            except Exception as e:
                self.app.notify(f"Error al abrir enlace: {str(e)}", severity="error")
        else:
            self.app.notify("Este comentario no tiene enlace", severity="warning")
    
    def action_view_image(self) -> None:
        if not self.comments or self.selected_index < 0:
            return
        comment = self.comments[self.selected_index]
        if comment.image_path:
            if Path(comment.image_path).exists():
                self.app.push_screen(ImageViewerModal(comment.image_path))
            else:
                self.app.notify("❌ Imagen no encontrada", severity="error")
        else:
            self.app.notify("Este comentario no tiene imagen", severity="warning")

    def action_open_file(self) -> None:
        if not self.comments or self.selected_index < 0:
            return
        comment = self.comments[self.selected_index]
        if comment.file_path:
            file_path = Path(comment.file_path)
            if file_path.exists():
                try:
                    system = platform.system()
                    if system == "Windows":
                        os.startfile(str(file_path))
                    elif system == "Darwin":
                        subprocess.run(["open", str(file_path)], check=True)
                    else:
                        subprocess.run(["xdg-open", str(file_path)], check=True)
                    self.app.notify(f"📎 Abriendo: {file_path.name}", severity="information")
                except Exception as e:
                    self.app.notify(f"❌ Error al abrir archivo: {str(e)}", severity="error")
            else:
                self.app.notify("❌ Archivo no encontrado", severity="error")
        else:
            self.app.notify("Este comentario no tiene archivo adjunto", severity="warning")

    @on(Button.Pressed, "#add")
    def on_add(self) -> None:
        self.action_add_comment()
    
    @on(Button.Pressed, "#edit")
    def on_edit(self) -> None:
        self.action_edit_comment()
    
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None:
        self.action_delete_comment()
    
    def action_close(self) -> None:
        self.dismiss(self.comments)

class TagsManagerModal(ModalScreen[list[Tag]]):
    DEFAULT_CSS = """
    TagsManagerModal { align: center middle; }
    TagsManagerModal > VerticalScroll {
        width: 65; height: 34; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    TagsManagerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    TagsManagerModal .search-label { color: $text-muted; margin-bottom: 0; }
    TagsManagerModal Input { width: 100%; margin-bottom: 1; }
    TagsManagerModal #tags-list { width: 100%; height: 14; overflow-y: auto; border: solid $primary-background; padding: 1; }
    TagsManagerModal .tag-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    TagsManagerModal .tag-item:hover { background: $boost; }
    TagsManagerModal .tag-item.selected { border: solid $accent; background: $surface-lighten-1; }
    TagsManagerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    TagsManagerModal .hint { width: 100%; height: auto; text-align: center; color: $text-muted; margin: 1 0; }
    TagsManagerModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    TagsManagerModal Button { margin: 0 1; }
    """
    
    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("a", "add_tag", show=False),
        Binding("e", "edit_tag", show=False),
        Binding("d", "delete_tag", show=False),
        Binding("ctrl+f", "focus_search", show=False),
        Binding("/", "focus_search", show=False),
        Binding("tab", "blur_search", show=False),
    ]
    
    def __init__(self, tags: list[Tag], next_tag_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tags = [Tag(id=t.id, name=t.name) for t in tags]
        self.next_tag_id = next_tag_id
        self.selected_index = 0 if tags else -1
        self.search_query = ""
        self.filtered_tags: list[Tag] = []
        self.search_focused = False
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🏷️  Gestionar Etiquetas", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar, Tab para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar etiquetas...", id="search-input")
            yield Container(id="tags-list")
            yield Label("↑↓ Navegar | a: Añadir | e: Editar | d: Eliminar | /: Buscar | Tab: Salir búsqueda | Esc: Cerrar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("➕ Añadir", variant="primary", id="add")
                yield Button("✏️ Editar", variant="default", id="edit")
                yield Button("🗑️ Eliminar", variant="error", id="delete")

    async def on_mount(self) -> None:
        await self.refresh_tags_list()
        try:
            self.query_one("#search-input", Input).blur()
        except:
            pass

    def _filter_tags(self) -> list[Tag]:
        if not self.search_query:
            return self.tags
        
        query_lower = self.search_query.lower()
        return [tag for tag in self.tags if query_lower in tag.name.lower()]
    
    async def refresh_tags_list(self) -> None:
        tags_list = self.query_one("#tags-list", Container)
        await tags_list.remove_children()
        
        self.filtered_tags = self._filter_tags()
        
        if not self.tags:
            await tags_list.mount(Label("No hay etiquetas. Pulsa 'a' para crear una.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_tags:
            await tags_list.mount(Label(f"No se encontraron etiquetas para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_tags):
                self.selected_index = max(0, len(self.filtered_tags) - 1)
            
            for i, tag in enumerate(self.filtered_tags):
                item = Static(f"  {tag.name}  ", id=f"tag-{i}", classes="tag-item")
                await tags_list.mount(item)
                if i == self.selected_index:
                    item.add_class("selected")
            self.scroll_to_selected()
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0 and self.selected_index < len(self.filtered_tags):
            try:
                item = self.query_one(f"#tag-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.filtered_tags)):
            try:
                item = self.query_one(f"#tag-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.search_focused:
            return
        if self.filtered_tags and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.search_focused:
            return
        if self.filtered_tags and self.selected_index < len(self.filtered_tags) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#search-input", Input).focus()
        except: pass
    
    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_tags_list)

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_close(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(self.tags)
    
    def action_add_tag(self) -> None:
        if self.search_focused:
            return
        
        def on_result(name: Optional[str]) -> None:
            if name:
                tag_names = [n.strip() for n in name.split(';') if n.strip()]
                
                if not tag_names:
                    return
                
                created_count = 0
                duplicates = []
                
                for tag_name in tag_names:
                    tag_name_truncated = tag_name[:30]
                    
                    if any(t.name.lower() == tag_name_truncated.lower() for t in self.tags):
                        duplicates.append(tag_name_truncated)
                        continue
                    
                    tag = Tag(id=self.next_tag_id, name=tag_name_truncated)
                    self.next_tag_id += 1
                    self.tags.append(tag)
                    created_count += 1
                
                if created_count > 0:
                    self.selected_index = 0
                    self.search_query = ""
                    try:
                        self.query_one("#search-input", Input).value = ""
                    except: pass
                    self.call_later(self.refresh_tags_list)
                    
                    if created_count == 1:
                        self.app.notify(f"Etiqueta '{tag_names[0][:30]}' creada", severity="information")
                    else:
                        self.app.notify(f"{created_count} etiquetas creadas", severity="information")
                
                if duplicates:
                    if len(duplicates) == 1:
                        self.app.notify(f"'{duplicates[0]}' ya existe", severity="warning")
                    else:
                        self.app.notify(f"{len(duplicates)} etiquetas ya existían", severity="warning")
        
        self.app.push_screen(
            InputModal(
                "🏷️  Nueva(s) Etiqueta(s)", 
                placeholder="Nombre (usa ; para crear varias)"
            ), 
            on_result
        )
    
    def action_edit_tag(self) -> None:
        if self.search_focused:
            return
        if not self.filtered_tags or self.selected_index < 0 or self.selected_index >= len(self.filtered_tags):
            return
        tag = self.filtered_tags[self.selected_index]
        
        def on_result(name: Optional[str]) -> None:
            if name:
                tag.name = name[:30]
                self.call_later(self.refresh_tags_list)
        self.app.push_screen(InputModal("✏️  Editar Etiqueta", initial_text=tag.name), on_result)
    
    def action_delete_tag(self) -> None:
        if self.search_focused:
            return
        if not self.filtered_tags or self.selected_index < 0 or self.selected_index >= len(self.filtered_tags):
            return
        tag = self.filtered_tags[self.selected_index]
        
        def on_confirm(yes: bool) -> None:
            if yes:
                self.tags.remove(tag)
                if self.selected_index >= len(self.filtered_tags) and self.selected_index > 0:
                    self.selected_index -= 1
                if not self.tags:
                    self.selected_index = -1
                self.call_later(self.refresh_tags_list)
        self.app.push_screen(ConfirmModal(f"¿Eliminar etiqueta '{tag.name}'?"), on_confirm)
    
    @on(Button.Pressed, "#add")
    def on_add(self) -> None:
        self.action_add_tag()
    
    @on(Button.Pressed, "#edit")
    def on_edit(self) -> None:
        self.action_edit_tag()
    
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None:
        self.action_delete_tag()
    
    @on(Input.Changed, "#search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_tags_list()
    
    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()
    
    def action_close(self) -> None:
        self.dismiss(self.tags)

class TagPickerModal(ModalScreen[list[int]]):
    DEFAULT_CSS = """
    TagPickerModal { align: center middle; }
    TagPickerModal > VerticalScroll {
        width: 65; height: auto; max-height: 90%; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    TagPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    TagPickerModal .search-label { color: $text-muted; margin-bottom: 0; }
    TagPickerModal Input { width: 100%; margin-bottom: 1; }
    TagPickerModal #tags-list { width: 100%; height: auto; max-height: 20; overflow-y: auto; border: solid $primary-background; padding: 1; }
    TagPickerModal .tag-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    TagPickerModal .tag-item:hover { background: $boost; }
    TagPickerModal .tag-item.selected { border: solid $accent; background: $surface-lighten-1; }
    TagPickerModal .tag-item.checked { color: $success; }
    TagPickerModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    TagPickerModal .hint { width: 100%; height: auto; text-align: center; color: $text-muted; margin: 1 0; }
    TagPickerModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    TagPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_tag", show=False),
        Binding("enter", "save", show=False),
        Binding("ctrl+f", "focus_search", show=False),
        Binding("/", "focus_search", show=False),
        Binding("tab", "blur_search", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]
    
    def __init__(self, all_tags: list[Tag], selected_tag_ids: list[int], **kwargs) -> None:
        super().__init__(**kwargs)
        self.all_tags = all_tags
        self.selected_tag_ids = list(selected_tag_ids)
        self.selected_index = 0 if all_tags else -1
        self.search_query = ""
        self.filtered_tags: list[Tag] = []
        self.search_focused = False
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("🏷️  Seleccionar Etiquetas", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar, Tab para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar etiquetas...", id="search-input")
            yield Container(id="tags-list")
            yield Label("↑↓ Navegar | Espacio: Marcar | /: Buscar | Tab: Salir búsqueda | Enter: Guardar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    async def on_mount(self) -> None:
        await self.refresh_tags_list()
        try:
            self.query_one("#search-input", Input).blur()
        except:
            pass

    def _filter_tags(self) -> list[Tag]:
        if not self.search_query:
            return self.all_tags
        
        query_lower = self.search_query.lower()
        return [tag for tag in self.all_tags if query_lower in tag.name.lower()]
    
    async def refresh_tags_list(self) -> None:
        tags_list = self.query_one("#tags-list", Container)
        await tags_list.remove_children()
        
        self.filtered_tags = self._filter_tags()
        
        if not self.all_tags:
            await tags_list.mount(Label("No hay etiquetas. Créalas con 'T' en el menú principal.", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_tags:
            await tags_list.mount(Label(f"No se encontraron etiquetas para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_tags):
                self.selected_index = max(0, len(self.filtered_tags) - 1)
            
            for i, tag in enumerate(self.filtered_tags):
                checked = "☑" if tag.id in self.selected_tag_ids else "☐"
                item = Static(f"{checked}  {tag.name}", id=f"tag-{i}", classes="tag-item")
                await tags_list.mount(item)
                if tag.id in self.selected_tag_ids:
                    item.add_class("checked")
                if i == self.selected_index:
                    item.add_class("selected")
            self.scroll_to_selected()
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0 and self.selected_index < len(self.filtered_tags):
            try:
                item = self.query_one(f"#tag-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.filtered_tags)):
            try:
                item = self.query_one(f"#tag-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.search_focused:
            return
        if self.filtered_tags and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.search_focused:
            return
        if self.filtered_tags and self.selected_index < len(self.filtered_tags) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_toggle_tag(self) -> None:
        if self.search_focused:
            return
        if not self.filtered_tags or self.selected_index < 0 or self.selected_index >= len(self.filtered_tags):
            return
        tag = self.filtered_tags[self.selected_index]
        if tag.id in self.selected_tag_ids:
            self.selected_tag_ids.remove(tag.id)
        else:
            self.selected_tag_ids.append(tag.id)
        self.call_later(self.refresh_tags_list)
    
    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#search-input", Input).focus()
        except: pass
    
    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_tags_list)

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()
    
    def action_save(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        self.dismiss(self.selected_tag_ids)

    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)
    
    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    @on(Input.Changed, "#search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_tags_list()
        self.selected_index = 0
        await self.refresh_tags_list()
    
    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()
    
    def action_cancel(self) -> None:
        self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()

class StatusFilterPickerModal(ModalScreen[Optional[list[str]]]):
    DEFAULT_CSS = """
    StatusFilterPickerModal { align: center middle; }
    StatusFilterPickerModal > VerticalScroll {
        width: 40; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    StatusFilterPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    StatusFilterPickerModal #status-list { width: 100%; height: auto; padding: 1; }
    StatusFilterPickerModal .status-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        content-align: center middle;
    }
    StatusFilterPickerModal .status-item:hover { background: $boost; }
    StatusFilterPickerModal .status-item.selected { border: solid $accent; background: $surface-lighten-1; }
    StatusFilterPickerModal .status-item.checked { color: $success; }
    StatusFilterPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    StatusFilterPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    StatusFilterPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_status", show=False),
        Binding("enter", "save", show=False),
    ]
    
    def __init__(self, current_filters: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self.selected_status_ids = list(current_filters)
        self.options = ["in_progress", "on_hold", "completed"]
        self.selected_index = 0
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("✓ Filtrar por Estado", classes="modal-title")
            yield Container(id="status-list")
            yield Label("↑↓ Navegar | Espacio: Marcar/Desmarcar | Enter: Guardar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        await self.refresh_list()
    
    async def refresh_list(self) -> None:
        status_list = self.query_one("#status-list", Container)
        await status_list.remove_children()
        
        options_display = [
            ("🔄 En progreso", "in_progress"),
            ("⏳ En espera", "on_hold"),
            ("✅ Completadas", "completed")
        ]
        
        for i, (text, value) in enumerate(options_display):
            checked = "☑" if value in self.selected_status_ids else "☐"
            display_text = f"{checked}  {text}"
            item = Static(display_text, id=f"status-{i}", classes="status-item")
            await status_list.mount(item)
            if value in self.selected_status_ids:
                item.add_class("checked")
            if i == self.selected_index:
                item.add_class("selected")
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#status-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.options)):
            try:
                item = self.query_one(f"#status-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.options and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.options and self.selected_index < len(self.options) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_toggle_status(self) -> None:
        if not self.options or self.selected_index < 0:
            return
        status_id = self.options[self.selected_index]
        if status_id in self.selected_status_ids:
            self.selected_status_ids.remove(status_id)
        else:
            self.selected_status_ids.append(status_id)
        self.call_later(self.refresh_list) 
    
    def action_save(self) -> None:
        self.dismiss(self.selected_status_ids)
    
    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class PriorityFilterPickerModal(ModalScreen[Optional[list[int]]]):
    DEFAULT_CSS = """
    PriorityFilterPickerModal { align: center middle; }
    PriorityFilterPickerModal > VerticalScroll {
        width: 40; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    PriorityFilterPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    PriorityFilterPickerModal #priority-list { width: 100%; height: auto; padding: 1; }
    PriorityFilterPickerModal .priority-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        content-align: center middle;
    }
    PriorityFilterPickerModal .priority-item:hover { background: $boost; }
    PriorityFilterPickerModal .priority-item.selected { border: solid $accent; background: $surface-lighten-1; }
    PriorityFilterPickerModal .priority-item.checked { color: $success; }
    PriorityFilterPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    PriorityFilterPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    PriorityFilterPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_priority", show=False),
        Binding("enter", "save", show=False),
    ]
    
    def __init__(self, current_filters: list[int], **kwargs) -> None:
        super().__init__(**kwargs)
        self.selected_priority_ids = list(current_filters)
        self.options = [0, 1, 2, 3]
        self.selected_index = 0
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("⭐ Filtrar por Prioridad", classes="modal-title")
            yield Container(id="priority-list")
            yield Label("↑↓ Navegar | Espacio: Marcar/Desmarcar | Enter: Guardar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        await self.refresh_list()
    
    async def refresh_list(self) -> None:
        priority_list = self.query_one("#priority-list", Container)
        await priority_list.remove_children()
        
        priorities = [
            ("   Sin prioridad", 0),
            ("[green]■[/green]  Baja", 1),
            ("[yellow]■[/yellow]  Media", 2),
            ("[red]■[/red]  Alta", 3)
        ]
        
        for i, (text, value) in enumerate(priorities):
            checked = "☑" if value in self.selected_priority_ids else "☐"
            display_text = f"{checked}  {text}"
            item = Static(display_text, id=f"priority-{i}", classes="priority-item")
            await priority_list.mount(item)
            if value in self.selected_priority_ids:
                item.add_class("checked")
            if i == self.selected_index:
                item.add_class("selected")
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#priority-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.options)):
            try:
                item = self.query_one(f"#priority-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.options and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.options and self.selected_index < len(self.options) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_toggle_priority(self) -> None:
        if not self.options or self.selected_index < 0:
            return
        priority_id = self.options[self.selected_index]
        if priority_id in self.selected_priority_ids:
            self.selected_priority_ids.remove(priority_id)
        else:
            self.selected_priority_ids.append(priority_id)
        self.call_later(self.refresh_list)
    
    def action_save(self) -> None:
        self.dismiss(self.selected_priority_ids)
    
    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class FilterModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    FilterModal { align: center middle; }
    FilterModal > VerticalScroll {
        width: 70; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    FilterModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    FilterModal .section-label { margin-top: 1; color: $text-muted; }
    FilterModal .filter-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    FilterModal .filter-display { width: 1fr; padding: 0 1; }
    FilterModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    FilterModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]
    
    def __init__(self, current_date_filters: list[str], current_tag_filters: list[int],
                 current_status_filters: list[str], current_priority_filters: list[int],
                 all_tags: list[Tag], available_dates: list[str], title: str = "🔍 Filtrar Tareas", **kwargs) -> None:
        super().__init__(**kwargs)
        self.modal_title_text = title
        self.date_filters = list(current_date_filters)
        self.tag_filters = list(current_tag_filters)
        self.status_filters = list(current_status_filters)
        self.priority_filters = list(current_priority_filters)
        self.all_tags = all_tags
        self.available_dates = available_dates
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(self.modal_title_text, classes="modal-title")
            yield Label("Fecha:", classes="section-label")
            with Horizontal(classes="filter-row"):
                yield Label(self._format_date_filter(), id="date-display", classes="filter-display")
                yield Button("📅 Seleccionar", id="change-date")
                yield Button("❌ Quitar", id="remove-date")
            yield Label("Etiquetas:", classes="section-label")
            with Horizontal(classes="filter-row"):
                yield Label(self._format_tag_filter(), id="tag-display", classes="filter-display")
                yield Button("🏷️ Seleccionar", id="change-tag")
                yield Button("❌ Quitar", id="remove-tag")
            yield Label("Estado:", classes="section-label")
            with Horizontal(classes="filter-row"):
                yield Label(self._format_status_filter(), id="status-display", classes="filter-display")
                yield Button("✓ Seleccionar", id="change-status")
                yield Button("❌ Quitar", id="remove-status")
            yield Label("Prioridad:", classes="section-label")
            with Horizontal(classes="filter-row"):
                yield Label(self._format_priority_filter(), id="priority-display", classes="filter-display")
                yield Button("⭐ Seleccionar", id="change-priority")
                yield Button("❌ Quitar", id="remove-priority")
            with Horizontal(classes="button-row"):
                yield Button("Aplicar", variant="primary", id="apply")
                yield Button("Quitar todos", variant="warning", id="clear")
    
    def _format_date_filter(self) -> str:
        if not self.date_filters:
            return "Todas las fechas"
        date_strs = []
        for fd in self.date_filters:
            if fd == "none":
                date_strs.append("Sin fecha")
            else:
                try:
                    d = datetime.strptime(fd, "%Y-%m-%d")
                    date_strs.append(f"{d.day:02d}/{d.month:02d}")
                except: pass
        return f"📅 {', '.join(date_strs)}" if date_strs else "Todas las fechas"
    
    def _format_tag_filter(self) -> str:
        if not self.tag_filters:
            return "Todas las etiquetas"
        tag_names = []
        for tag_id in self.tag_filters:
            tag = next((t for t in self.all_tags if t.id == tag_id), None)
            if tag:
                tag_names.append(tag.name)
        if tag_names:
            return f"🏷️ {', '.join(tag_names)}"
        return "Todas las etiquetas"
    
    def _format_status_filter(self) -> str:
        if not self.status_filters:
            return "Todos los estados"
        status_names = []
        for status in self.status_filters:
            if status == "completed":
                status_names.append("Completadas")
            elif status == "in_progress":
                status_names.append("En progreso")
            elif status == "on_hold":
                status_names.append("En espera")
            elif status == "pending":
                status_names.append("Pendientes")
        return f"✅ {', '.join(status_names)}" if status_names else "Todos los estados"
    
    def _format_priority_filter(self) -> str:
        if not self.priority_filters:
            return "Todas las prioridades"
        priority_names = {0: "Sin prioridad", 1: "■ Baja", 2: "■ Media", 3: "■ Alta"}
        priority_strs = [priority_names.get(p, '') for p in self.priority_filters]
        return f"⭐ {', '.join(priority_strs)}" if priority_strs else "Todas las prioridades"
    
    @on(Button.Pressed, "#change-date")
    def on_change_date(self) -> None:
        def on_result(result: Optional[list[str]]) -> None:
            if result is not None:
                self.date_filters = result
                self.query_one("#date-display", Label).update(self._format_date_filter())
        self.app.push_screen(DateFilterPickerModal(self.available_dates, self.date_filters), on_result)
    
    @on(Button.Pressed, "#remove-date")
    def on_remove_date(self) -> None:
        self.date_filters = []
        self.query_one("#date-display", Label).update(self._format_date_filter())
    
    @on(Button.Pressed, "#change-tag")
    def on_change_tag(self) -> None:
        def on_result(result: Optional[list[int]]) -> None:
            if result is not None:
                self.tag_filters = result
                self.query_one("#tag-display", Label).update(self._format_tag_filter())
        self.app.push_screen(TagPickerModal(self.all_tags, self.tag_filters), on_result)
    
    @on(Button.Pressed, "#remove-tag")
    def on_remove_tag(self) -> None:
        self.tag_filters = []
        self.query_one("#tag-display", Label).update(self._format_tag_filter())
    
    @on(Button.Pressed, "#change-status")
    def on_change_status(self) -> None:
        def on_result(result: Optional[list[str]]) -> None:
            if result is not None:
                self.status_filters = result
                self.query_one("#status-display", Label).update(self._format_status_filter())
        self.app.push_screen(StatusFilterPickerModal(self.status_filters), on_result)
    
    @on(Button.Pressed, "#remove-status")
    def on_remove_status(self) -> None:
        self.status_filters = []
        self.query_one("#status-display", Label).update(self._format_status_filter())
    
    @on(Button.Pressed, "#change-priority")
    def on_change_priority(self) -> None:
        def on_result(result: Optional[list[int]]) -> None:
            if result is not None:
                self.priority_filters = result
                self.query_one("#priority-display", Label).update(self._format_priority_filter())
        self.app.push_screen(PriorityFilterPickerModal(self.priority_filters), on_result)
    
    @on(Button.Pressed, "#remove-priority")
    def on_remove_priority(self) -> None:
        self.priority_filters = []
        self.query_one("#priority-display", Label).update(self._format_priority_filter())
    
    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        self.action_apply()
    
    def action_apply(self) -> None:
        self.dismiss({
            "dates": self.date_filters,
            "tags": self.tag_filters,
            "statuses": self.status_filters,
            "priorities": self.priority_filters
        })
    
    @on(Button.Pressed, "#clear")
    def on_clear(self) -> None:
        self.dismiss({"dates": [], "tags": [], "statuses": [], "priorities": []})
    
    def action_cancel(self) -> None:
        self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()

class DateFilterPickerModal(ModalScreen[Optional[list[str]]]):
    DEFAULT_CSS = """
    DateFilterPickerModal { align: center middle; }
    DateFilterPickerModal > VerticalScroll {
        width: 50; height: 26; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    DateFilterPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    DateFilterPickerModal #dates-list { width: 100%; height: 12; overflow-y: auto; border: solid $primary-background; padding: 1; }
    DateFilterPickerModal .date-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    DateFilterPickerModal .date-item:hover { background: $boost; }
    DateFilterPickerModal .date-item.selected { border: solid $accent; background: $surface-lighten-1; }
    DateFilterPickerModal .date-item.checked { color: $success; }
    DateFilterPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    DateFilterPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    DateFilterPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_date", show=False),
        Binding("enter", "save", show=False),
    ]
    
    def __init__(self, available_dates: list[str], current_filters: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self.available_dates = available_dates
        self.selected_date_ids = list(current_filters)
        self.options = ["none"] + sorted(set(available_dates), reverse=True)
        self.selected_index = 0
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📅 Filtrar por Fecha", classes="modal-title")
            yield Container(id="dates-list")
            yield Label("↑↓ Navegar | Espacio: Marcar/Desmarcar | Enter: Guardar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        await self.refresh_list()
    
    async def refresh_list(self) -> None:
        dates_list = self.query_one("#dates-list", Container)
        await dates_list.remove_children()
        
        for i, opt in enumerate(self.options):
            checked = "☑" if opt in self.selected_date_ids else "☐"
            if opt == "none":
                text = f"{checked}  Sin fecha asignada"
            else:
                try:
                    d = datetime.strptime(opt, "%Y-%m-%d")
                    text = f"{checked}  {d.day:02d}/{d.month:02d}/{d.year}"
                except:
                    text = f"{checked}  {opt}"
            
            item = Static(text, id=f"date-{i}", classes="date-item")
            await dates_list.mount(item)
            if opt in self.selected_date_ids:
                item.add_class("checked")
            if i == self.selected_index:
                item.add_class("selected")
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#date-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.options)):
            try:
                item = self.query_one(f"#date-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.options and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.options and self.selected_index < len(self.options) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_toggle_date(self) -> None:
        if not self.options or self.selected_index < 0:
            return
        date_id = self.options[self.selected_index]
        if date_id in self.selected_date_ids:
            self.selected_date_ids.remove(date_id)
        else:
            self.selected_date_ids.append(date_id)
        self.call_later(self.refresh_list)
    
    def action_save(self) -> None:
        self.dismiss(self.selected_date_ids)
    
    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class EditTaskModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    EditTaskModal { align: center middle; }
    EditTaskModal > VerticalScroll {
        width: 65; min-height: 48; max-height: 90%; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    EditTaskModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    EditTaskModal .section-label { margin-top: 0; margin-bottom: 0; color: $text-muted; }
    EditTaskModal Input { width: 100%; margin-bottom: 1; }
    EditTaskModal .date-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .group-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .priority-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .comments-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .tags-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .date-display { width: 1fr; padding: 0 1; }
    EditTaskModal .group-display { width: 1fr; padding: 0 1; }
    EditTaskModal .priority-display { width: 1fr; padding: 0 1; }
    EditTaskModal .comments-display { width: 1fr; padding: 0 1; }
    EditTaskModal .tags-display { width: 1fr; padding: 0 1; }
    EditTaskModal .subtasks-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .subtasks-display { width: 1fr; padding: 0 1; }
    EditTaskModal .notes-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .notes-display { width: 1fr; padding: 0 1; }
    EditTaskModal .audios-row { width: 100%; height: auto; align: left middle; margin-bottom: 1; }
    EditTaskModal .audios-display { width: 1fr; padding: 0 1; }
    EditTaskModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 2; }
    EditTaskModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]
    
    def __init__(self, task_text: str, current_date: Optional[str] = None,
                current_group_id: Optional[int] = None, groups: list[Group] = None,
                comments: list[Comment] = None, next_comment_id: int = 1,
                all_tags: list[Tag] = None, selected_tag_ids: list[int] = None,
                current_priority: int = 0, 
                subtasks: list = None, next_subtask_id: int = 1,
                notes: list = None, next_note_id: int = 1,
                voice_notes: list = None, next_voice_note_id: int = 1,
                canvas_list: list = None, next_canvas_id: int = 1,
                current_status: str = "En progreso",
                **kwargs) -> None:
        super().__init__(**kwargs)
        self.task_text = task_text
        self.selected_date = current_date
        self.selected_group_id = current_group_id
        self.groups = groups or []
        self.comments = comments or []
        self.next_comment_id = next_comment_id
        self.all_tags = all_tags or []
        self.selected_tag_ids = list(selected_tag_ids) if selected_tag_ids else []
        self.selected_priority = current_priority
        self.selected_status = current_status if current_status in ("En progreso", "En espera", "Completado") else "En progreso"
        self.subtasks = subtasks or []
        self.next_subtask_id = next_subtask_id
        self.notes = notes or []
        self.next_note_id = next_note_id
        self.voice_notes = voice_notes or []
        self.next_voice_note_id = next_voice_note_id
        self.canvas_list = canvas_list or []
        self.next_canvas_id = next_canvas_id
        self._initial_notes = list(self.notes)
        self._initial_voice_notes = list(self.voice_notes)
        self._initial_subtasks = list(self.subtasks)
        self._initial_comments = list(self.comments)
        self._initial_canvas_list = list(self.canvas_list)
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("✏️  Editar Tarea", classes="modal-title")
            yield Label("Texto:", classes="section-label")
            yield UndoableInput(value=self.task_text, id="task-input")
            yield Label("Estado:", classes="section-label")
            with Horizontal(classes="priority-row"):
                yield Label(self._format_status(), id="status-display", classes="priority-display")
                yield Button("🔄 Cambiar", id="change-status")
            yield Label("Grupo:", classes="section-label")
            with Horizontal(classes="group-row"):
                yield Label(self._format_group(self.selected_group_id), id="group-display", classes="group-display")
                yield Button("📁 Cambiar", id="change-group")
            yield Label("Prioridad:", classes="section-label")
            with Horizontal(classes="priority-row"):
                yield Label(self._format_priority(), id="priority-display", classes="priority-display")
                yield Button("⭐ Cambiar", id="change-priority")
            yield Label("Fecha:", classes="section-label")
            with Horizontal(classes="date-row"):
                yield Label(self._format_date(self.selected_date), id="date-display", classes="date-display")
                yield Button("📅 Cambiar", id="change-date")
                yield Button("❌ Quitar", id="remove-date")
            yield Label("Etiquetas:", classes="section-label")
            with Horizontal(classes="tags-row"):
                yield Label(self._format_tags(), id="tags-display", classes="tags-display")
                yield Button("🏷️ Seleccionar", id="select-tags")
            yield Label("Comentarios:", classes="section-label")
            with Horizontal(classes="comments-row"):
                yield Label(self._format_comments(), id="comments-display", classes="comments-display")
                yield Button("💬 Gestionar", id="manage-comments")
            yield Label("Subtareas:", classes="section-label")
            with Horizontal(classes="subtasks-row"):
                yield Label(self._format_subtasks(), id="subtasks-display", classes="subtasks-display")
                yield Button("📋 Gestionar", id="manage-subtasks")
            yield Label("Notas:", classes="section-label")
            with Horizontal(classes="notes-row"):
                yield Label(self._format_notes(), id="notes-display", classes="notes-display")
                yield Button("📌 Seleccionar", id="select-notes")
            yield Label("Audios:", classes="section-label")
            with Horizontal(classes="audios-row"):
                yield Label(self._format_voice_notes(), id="audios-display", classes="audios-display")
                yield Button("📌 Seleccionar", id="select-voice-notes")
            yield Label("Pizarras:", classes="section-label")
            with Horizontal(classes="audios-row"):
                yield Label(self._format_canvas_list(), id="canvas-display", classes="audios-display")
                yield Button("📌 Seleccionar", id="select-canvas")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def _format_status(self) -> str:
        icons = {"En progreso": "🔄 En progreso", "En espera": "⏳ En espera", "Completado": "✅ Completado"}
        return icons.get(self.selected_status, "🔄 En progreso")

    @on(Button.Pressed, "#change-status")
    def on_change_status(self) -> None:
        def on_result(result: Optional[str]) -> None:
            if result:
                self.selected_status = result
                self.query_one("#status-display", Label).update(self._format_status())
        self.app.push_screen(StatusPickerModal(self.selected_status), on_result)

    def _format_date(self, date_str: Optional[str]) -> str:
        if not date_str: return "Sin fecha"
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            return f"📅 {d.day:02d}/{d.month:02d}/{d.year}"
        except: return "Sin fecha"
    
    def _format_group(self, group_id: Optional[int]) -> str:
        if group_id is None:
            return "📋 Sin grupo"
        group = next((g for g in self.groups if g.id == group_id), None)
        if group:
            return f"📁 {group.name}"
        return "📋 Sin grupo"
    
    def _format_priority(self) -> str:
        priority_names = {
            0: "Sin prioridad",
            1: "■ Baja",
            2: "■ Media",
            3: "■ Alta"
        }
        return priority_names.get(self.selected_priority, "Sin prioridad")
    
    def _format_comments(self) -> str:
        count = len(self.comments)
        if count == 0:
            return "Sin comentarios"
        elif count == 1:
            return "💬 1 comentario"
        else:
            return f"💬 {count} comentarios"

    def _format_notes(self) -> str:
        count = len(self.notes)
        if count == 0:
            return "Sin notas"
        return f"📝 {count} nota(s)"

    def _format_voice_notes(self) -> str:
        count = len(self.voice_notes)
        if count == 0:
            return "Sin audios"
        return f"🎤 {count} audio(s)"
    
    def _format_tags(self) -> str:
        if not self.selected_tag_ids:
            return "Sin etiquetas"
        tag_names = []
        for tag_id in self.selected_tag_ids[:3]:
            tag = next((t for t in self.all_tags if t.id == tag_id), None)
            if tag:
                tag_names.append(tag.name)
        result = "🏷️ " + ", ".join(tag_names)
        if len(self.selected_tag_ids) > 3:
            result += f" (+{len(self.selected_tag_ids) - 3})"
        return result
    
    def on_mount(self) -> None:
        self.query_one("#task-input", Input).focus()
    
    def _format_subtasks(self) -> str:
        count = len(self.subtasks)
        if count == 0:
            return "Sin subtareas"
        done_count = sum(1 for s in self.subtasks if s.done)
        return f"📋 {done_count}/{count} completadas"

    @on(Button.Pressed, "#manage-subtasks")
    def on_manage_subtasks(self) -> None:
        def on_result(updated_subtasks: list) -> None:
            self.subtasks = updated_subtasks
            if self.subtasks:
                self.next_subtask_id = max(s.id for s in self.subtasks) + 1
            self.query_one("#subtasks-display", Label).update(self._format_subtasks())
        
        next_comment_id = self.next_comment_id
        for subtask in self.subtasks:
            if subtask.comments:
                max_id = max(c.id for c in subtask.comments)
                if max_id >= next_comment_id:
                    next_comment_id = max_id + 1

        self.app.push_screen(SubtasksModal(self.subtasks, self.next_subtask_id, next_comment_id, all_tags=self.all_tags), on_result)  


    
    @on(Button.Pressed, "#change-group")
    def on_change_group(self) -> None:
        def on_result(result: Optional[int]) -> None:
            self.selected_group_id = result
            self.query_one("#group-display", Label).update(self._format_group(self.selected_group_id))
        self.app.push_screen(GroupPickerModal(self.groups, self.selected_group_id), on_result)
    
    @on(Button.Pressed, "#change-priority")
    def on_change_priority(self) -> None:
        def on_result(result: Optional[int]) -> None:
            if result is not None:
                self.selected_priority = result
                self.query_one("#priority-display", Label).update(self._format_priority())
        self.app.push_screen(PriorityPickerModal(self.selected_priority), on_result)
    
    @on(Button.Pressed, "#change-date")
    def on_change_date(self) -> None:
        def on_result(result: Optional[str]) -> None:
            if result is not None:
                self.selected_date = result if result else None
                self.query_one("#date-display", Label).update(self._format_date(self.selected_date))
        self.app.push_screen(DatePickerModal(self.selected_date), on_result)
    
    @on(Button.Pressed, "#remove-date")
    def on_remove_date(self) -> None:
        self.selected_date = None
        self.query_one("#date-display", Label).update("Sin fecha")
    
    @on(Button.Pressed, "#select-tags")
    def on_select_tags(self) -> None:
        def on_result(result: Optional[list[int]]) -> None:
            if result is not None:
                self.selected_tag_ids = result
                self.query_one("#tags-display", Label).update(self._format_tags())
        self.app.push_screen(TagPickerModal(self.all_tags, self.selected_tag_ids), on_result)
    
    @on(Button.Pressed, "#manage-comments")
    def on_manage_comments(self) -> None:
        def on_result(updated_comments: list[Comment]) -> None:
            self.comments = updated_comments
            if self.comments:
                self.next_comment_id = max(c.id for c in self.comments) + 1
            self.query_one("#comments-display", Label).update(self._format_comments())
        self.app.push_screen(CommentsModal(self.comments, self.next_comment_id), on_result)
    
    def _format_canvas_list(self) -> str:
        count = len(self.canvas_list)
        if count == 0:
            return "Sin pizarras"
        return f"🎨 {count} pizarra(s)"

    @on(Button.Pressed, "#select-notes")
    def on_select_notes(self) -> None:
        def on_result(result: Optional[list[Note]]) -> None:
            if result is not None:
                self.notes = result
                if self.notes:
                    self.next_note_id = max((n.id for n in self.notes), default=0) + 1
                self.query_one("#notes-display", Label).update(self._format_notes())
        global_notes = getattr(self.app, "notes", [])
        current_ids = [n.id for n in self.notes]
        self.app.push_screen(GlobalNotesPickerModal(global_notes, selected_note_ids=current_ids), on_result)

    @on(Button.Pressed, "#select-voice-notes")
    def on_select_voice_notes(self) -> None:
        def on_result(result: Optional[list[VoiceNote]]) -> None:
            if result is not None:
                self.voice_notes = result
                if self.voice_notes:
                    self.next_voice_note_id = max((v.id for v in self.voice_notes), default=0) + 1
                self.query_one("#audios-display", Label).update(self._format_voice_notes())
        global_vn = getattr(self.app, "voice_notes", [])
        current_ids = [v.id for v in self.voice_notes]
        self.app.push_screen(GlobalVoiceNotesPickerModal(global_vn, selected_vn_ids=current_ids), on_result)

    @on(Button.Pressed, "#select-canvas")
    def on_select_canvas(self) -> None:
        def on_result(result: Optional[list[Canvas]]) -> None:
            if result is not None:
                self.canvas_list = result
                if self.canvas_list:
                    self.next_canvas_id = max((c.id for c in self.canvas_list), default=0) + 1
                self.query_one("#canvas-display", Label).update(self._format_canvas_list())
        global_canvas = getattr(self.app, "canvas_list", [])
        current_ids = [c.id for c in self.canvas_list]
        self.app.push_screen(GlobalCanvasPickerModal(global_canvas, selected_canvas_ids=current_ids), on_result)



    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.action_save()
    
    def action_save(self) -> None:
        text = self.query_one("#task-input", Input).value.strip()
        if not text:
            self.dismiss(None)
            return
        
        if self.selected_group_id == self.app.GENERAL_GROUP_ID:
            self.app.notify("No se pueden asignar tareas al grupo General", severity="error", timeout=3)
            return
        
        self.dismiss({
            "text": text, 
            "status": self.selected_status,
            "date": self.selected_date,
            "group_id": self.selected_group_id,
            "comments": self.comments,
            "tags": self.selected_tag_ids,
            "priority": self.selected_priority,
            "subtasks": self.subtasks,
            "notes": self.notes,
            "voice_notes": self.voice_notes,
            "canvas_list": self.canvas_list
        } if text else None)
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.action_cancel()
    
    def action_cancel(self) -> None:
        if (self.notes != self._initial_notes or 
            self.voice_notes != self._initial_voice_notes or 
            self.subtasks != self._initial_subtasks or 
            self.comments != self._initial_comments or
            self.canvas_list != self._initial_canvas_list):
            text = self.query_one("#task-input", Input).value.strip() or self.task_text
            self.dismiss({
                "text": text,
                "status": self.selected_status,
                "date": self.selected_date,
                "group_id": self.selected_group_id,
                "comments": self.comments,
                "tags": self.selected_tag_ids,
                "priority": self.selected_priority,
                "subtasks": self.subtasks,
                "notes": self.notes,
                "voice_notes": self.voice_notes,
                "canvas_list": self.canvas_list
            })
        else:
            self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()

class DatePickerModal(ModalScreen[Optional[str]]):
    DEFAULT_CSS = """
    DatePickerModal { align: center middle; }
    DatePickerModal > VerticalScroll {
        width: 36; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    DatePickerModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    DatePickerModal .calendar-header { width: 100%; text-align: center; margin-bottom: 1; text-style: bold; }
    DatePickerModal .calendar-display { width: 100%; text-align: center; margin-bottom: 1; }
    DatePickerModal .hint { width: 100%; text-align: center; color: $text-muted; margin-bottom: 1; }
    DatePickerModal .button-row { width: 100%; height: auto; align: center middle; }
    DatePickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("left", "prev_day", show=False),
        Binding("right", "next_day", show=False),
        Binding("up", "prev_week", show=False),
        Binding("down", "next_week", show=False),
        Binding("n", "next_month", show=False),
        Binding("p", "prev_month", show=False),
        Binding("enter", "select_date", show=False),
        Binding("ctrl+s", "select_date", show=False, priority=True),
    ]
    
    def __init__(self, current_date: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        if current_date:
            try: self.selected_date = datetime.strptime(current_date, "%Y-%m-%d").date()
            except: self.selected_date = date.today()
        else:
            self.selected_date = date.today()
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📅 Seleccionar Fecha", classes="modal-title")
            yield Label("", id="month-label", classes="calendar-header")
            yield Static("", id="calendar-display", classes="calendar-display")
            yield Label("←→↑↓: Día | n/p: Mes", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Seleccionar", variant="primary", id="select")
                yield Button("Cancelar", variant="default", id="cancel")
    
    def on_mount(self) -> None:
        self.update_display()
    
    def update_display(self) -> None:
        self.query_one("#month-label", Label).update(f"{MESES[self.selected_date.month]} {self.selected_date.year}")
        cal = calendar.Calendar(firstweekday=0)
        today = date.today()
        lines = ["  ".join(DIAS_SEMANA), "─" * 26]
        for week in cal.monthdayscalendar(self.selected_date.year, self.selected_date.month):
            week_str = ""
            for day in week:
                if day == 0:
                    week_str += "    "
                else:
                    current = date(self.selected_date.year, self.selected_date.month, day)
                    if current == self.selected_date:
                        week_str += f"[bold cyan][{day:2d}][/bold cyan]"
                    elif current == today:
                        week_str += f"[bold green] {day:2d} [/bold green]"
                    else:
                        week_str += f" {day:2d} "
            lines.append(week_str)
        self.query_one("#calendar-display", Static).update("\n".join(lines))
    
    def action_prev_day(self) -> None:
        self.selected_date -= timedelta(days=1)
        self.update_display()
    
    def action_next_day(self) -> None:
        self.selected_date += timedelta(days=1)
        self.update_display()
    
    def action_prev_week(self) -> None:
        self.selected_date -= timedelta(days=7)
        self.update_display()
    
    def action_next_week(self) -> None:
        self.selected_date += timedelta(days=7)
        self.update_display()
    
    def action_prev_month(self) -> None:
        y, m = self.selected_date.year, self.selected_date.month - 1
        if m < 1: m, y = 12, y - 1
        self.selected_date = date(y, m, min(self.selected_date.day, calendar.monthrange(y, m)[1]))
        self.update_display()
    
    def action_next_month(self) -> None:
        y, m = self.selected_date.year, self.selected_date.month + 1
        if m > 12: m, y = 1, y + 1
        self.selected_date = date(y, m, min(self.selected_date.day, calendar.monthrange(y, m)[1]))
        self.update_display()
    
    def action_select_date(self) -> None:
        self.dismiss(self.selected_date.strftime("%Y-%m-%d"))
    
    @on(Button.Pressed, "#select")
    def on_select(self) -> None:
        self.action_select_date()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_select_date()

class ConfirmModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmModal { align: center middle; }
    ConfirmModal > VerticalScroll {
        width: 50; height: auto; border: thick $error;
        background: $surface; padding: 1 2;
    }
    ConfirmModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    ConfirmModal .button-row { width: 100%; height: auto; align: center middle; }
    ConfirmModal Button { margin: 0 1; }
    ConfirmModal Button.selected { border: solid $accent; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("left", "select_yes", show=False),
        Binding("right", "select_no", show=False),
        Binding("h", "select_yes", show=False),
        Binding("l", "select_no", show=False),
        Binding("enter", "confirm", show=False),
        Binding("space", "confirm", show=False),
    ]
    
    def __init__(self, message: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.message = message
        self.selected_yes = True
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(self.message, classes="modal-title")
            with Horizontal(classes="button-row"):
                yield Button("Sí", variant="error", id="yes")
                yield Button("No", variant="default", id="no")
    
    def on_mount(self) -> None:
        self.update_selection()
    
    def update_selection(self) -> None:
        yes_btn = self.query_one("#yes", Button)
        no_btn = self.query_one("#no", Button)
        yes_btn.set_class(self.selected_yes, "selected")
        no_btn.set_class(not self.selected_yes, "selected")
    
    def action_select_yes(self) -> None:
        self.selected_yes = True
        self.update_selection()
    
    def action_select_no(self) -> None:
        self.selected_yes = False
        self.update_selection()
    
    def action_confirm(self) -> None:
        self.dismiss(self.selected_yes)
    
    @on(Button.Pressed, "#yes")
    def on_yes(self) -> None:
        self.dismiss(True)
    
    @on(Button.Pressed, "#no")
    def on_no(self) -> None:
        self.dismiss(False)
    
    def action_cancel(self) -> None:
        self.dismiss(False)

class GroupOptionsModal(ModalScreen[str]):
    DEFAULT_CSS = """
    GroupOptionsModal { align: center middle; }
    GroupOptionsModal > VerticalScroll {
        width: 40; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    GroupOptionsModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    GroupOptionsModal Button { width: 100%; margin: 1 0; }
    GroupOptionsModal Button.selected { border: solid $accent; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("enter", "confirm", show=False),
        Binding("space", "confirm", show=False),
    ]
    
    def __init__(self, group_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.group_name = group_name
        self.selected_index = 0
        self.options = ["rename", "delete", ""]
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(f"Grupo: {self.group_name}", classes="modal-title")
            yield Button("✏️  Renombrar", variant="primary", id="rename")
            yield Button("🗑️  Eliminar grupo y tareas", variant="error", id="delete")
            yield Button("Cancelar", variant="default", id="cancel")
    
    def on_mount(self) -> None:
        self.update_selection()
    
    def update_selection(self) -> None:
        buttons = [("rename", 0), ("delete", 1), ("cancel", 2)]
        for btn_id, idx in buttons:
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                btn.set_class(idx == self.selected_index, "selected")
            except: pass
    
    def action_move_up(self) -> None:
        self.selected_index = (self.selected_index - 1) % 3
        self.update_selection()
    
    def action_move_down(self) -> None:
        self.selected_index = (self.selected_index + 1) % 3
        self.update_selection()
    
    def action_confirm(self) -> None:
        self.dismiss(self.options[self.selected_index])
    
    @on(Button.Pressed, "#rename")
    def on_rename(self) -> None:
        self.dismiss("rename")
    
    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None:
        self.dismiss("delete")
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss("")
    
    def action_cancel(self) -> None:
        self.dismiss("")

class DayTasksModal(ModalScreen[Optional[Task]]):
    DEFAULT_CSS = """
    DayTasksModal { align: center middle; }
    DayTasksModal > VerticalScroll {
        width: 70; height: 20; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    DayTasksModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    DayTasksModal #tasks-list { width: 100%; height: 1fr; overflow-y: auto; }
    DayTasksModal .task-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
        layout: horizontal;
    }
    DayTasksModal .task-item:hover { background: $boost; }
    DayTasksModal .task-item.selected { border: solid $accent; background: $surface-lighten-1; }
    DayTasksModal .task-main { width: 1fr; height: 1; }
    DayTasksModal .task-group { width: auto; height: 1; text-align: right; color: $text-muted; }
    DayTasksModal .hint { width: 100%; text-align: center; color: $text-muted; margin-top: 1; }
    DayTasksModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "go_to_task", show=False),
        Binding("enter", "go_to_task", show=False),
    ]
    
    def __init__(self, tasks: list[tuple[Task, str]], date_str: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tasks = tasks
        self.date_str = date_str
        self.selected_index = 0
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(f"📅 Tareas del {self.date_str}", classes="modal-title")
            yield Container(id="tasks-list")
            yield Label("↑↓ Navegar | Espacio/Enter: Ir al grupo | Esc: Cerrar", classes="hint")
    
    async def on_mount(self) -> None:
        tasks_list = self.query_one("#tasks-list", Container)
        if not self.tasks:
            await tasks_list.mount(Label("No hay tareas para este día", classes="empty-msg"))
        else:
            for i, (task, group_name) in enumerate(self.tasks):
                checkbox = "☑" if task.done else "☐"
                item = Horizontal(id=f"task-item-{i}", classes="task-item")
                await tasks_list.mount(item)
                
                await item.mount(Label(f"{checkbox} {task.text}", classes="task-main"))
                
                await item.mount(Label(f"Grupo: {group_name}", classes="task-group"))
                
                if i == 0:
                    item.add_class("selected")
    
    def update_selection(self) -> None:
        for i in range(len(self.tasks)):
            try:
                item = self.query_one(f"#task-item-{i}", Horizontal)
                item.set_class(i == self.selected_index, "selected")
            except: pass
    
    def action_move_up(self) -> None:
        if self.tasks and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.tasks and self.selected_index < len(self.tasks) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_go_to_task(self) -> None:
        if self.tasks:
            self.dismiss(self.tasks[self.selected_index][0])
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class SearchResultsScreen(ModalScreen[Optional[Task]]):
    DEFAULT_CSS = """
    SearchResultsScreen { align: center middle; }
    SearchResultsScreen > VerticalScroll {
        width: 90; height: 26; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    SearchResultsScreen .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    SearchResultsScreen #results-list { width: 100%; height: 14; overflow-y: auto; }
    SearchResultsScreen .result-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    SearchResultsScreen .result-item:hover { background: $boost; }
    SearchResultsScreen .result-item.selected { border: solid $accent; background: $surface-lighten-1; }
    SearchResultsScreen .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    SearchResultsScreen .button-row { width: 100%; height: 3; align: center middle; }
    SearchResultsScreen Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("enter", "select_result", show=False),
    ]
    
    def __init__(self, results: list[tuple[Task, str]], search_term: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.results = results
        self.search_term = search_term
        self.selected_index = 0
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(f"🔍 Resultados para '{self.search_term}'", classes="modal-title")
            yield Container(id="results-list")
            yield Label("↑↓ Navegar | Enter: Ir al grupo | Esc: Cerrar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Ir al grupo", variant="primary", id="go")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        results_list = self.query_one("#results-list", Container)
        for i, (task, group_name) in enumerate(self.results):
            text = task.text[:30] + "..." if len(task.text) > 30 else task.text
            group_text = f"Grupo: {group_name}"
            total_width = 75
            padding = " " * max(1, total_width - len(text) - len(group_text))
            display_text = f"{text}{padding}{group_text}"
            item = Static(display_text, id=f"result-{i}", classes="result-item")
            await results_list.mount(item)
            if i == 0:
                item.add_class("selected")
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#result-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.results)):
            try:
                item = self.query_one(f"#result-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.selected_index < len(self.results) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_select_result(self) -> None:
        if self.results:
            self.dismiss(self.results[self.selected_index][0])
    
    @on(Button.Pressed, "#go")
    def on_go(self) -> None:
        self.action_select_result()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)

class UnscheduledTasksModal(ModalScreen[Optional[list[int]]]):
    DEFAULT_CSS = """
    UnscheduledTasksModal { align: center middle; }
    UnscheduledTasksModal > VerticalScroll {
        width: 70; height: 32; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    UnscheduledTasksModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    UnscheduledTasksModal .search-label { color: $text-muted; margin-bottom: 0; }
    UnscheduledTasksModal Input { width: 100%; margin-bottom: 1; }
    UnscheduledTasksModal .info-text { width: 100%; text-align: center; color: $text-muted; margin-bottom: 1; }
    UnscheduledTasksModal #tasks-list { width: 100%; height: 14; overflow-y: auto; border: solid $primary-background; padding: 1; }
    UnscheduledTasksModal .task-item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    UnscheduledTasksModal .task-item:hover { background: $boost; }
    UnscheduledTasksModal .task-item.selected { border: solid $accent; background: $surface-lighten-1; }
    UnscheduledTasksModal .task-item.checked { color: $success; }
    UnscheduledTasksModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    UnscheduledTasksModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    UnscheduledTasksModal .button-row { width: 100%; height: 3; align: center middle; }
    UnscheduledTasksModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_task", show=False),
        Binding("enter", "save", show=False),
        Binding("/", "focus_search", show=False),
    ]
    
    def __init__(self, unscheduled_tasks: list[Task], all_groups: list[Group], **kwargs) -> None:
        super().__init__(**kwargs)
        self.unscheduled_tasks = unscheduled_tasks
        self.all_groups = all_groups
        self.selected_task_ids: list[int] = []
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        self.filtered_tasks: list[Task] = []
        self.selected_index = 0 if unscheduled_tasks else -1
    
    def _get_filtered_tasks(self) -> list[Task]:
        if not self.search_query:
            return self.unscheduled_tasks
        q = self.search_query.lower()
        return [t for t in self.unscheduled_tasks if q in t.text.lower()]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📋 Tareas sin fecha", classes="modal-title")
            yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir):", classes="search-label")
            yield UndoableInput(placeholder="Escribe para buscar tareas...", id="ut-search-input")
            yield Container(id="tasks-list")
            yield Label("↑↓ Navegar | Espacio: Marcar/Desmarcar | /: Buscar | Enter: Asignar fecha | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Asignar fecha", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        await self.refresh_list()
        try:
            self.query_one("#ut-search-input", Input).blur()
        except: pass
    
    async def refresh_list(self) -> None:
        tasks_list = self.query_one("#tasks-list", Container)
        await tasks_list.remove_children()
        
        self.filtered_tasks = self._get_filtered_tasks()
        
        if not self.unscheduled_tasks:
            await tasks_list.mount(Label("No hay tareas sin fecha pendientes", classes="empty-msg"))
            self.selected_index = -1
        elif not self.filtered_tasks:
            await tasks_list.mount(Label(f"No se encontraron tareas para '{self.search_query}'", classes="empty-msg"))
            self.selected_index = -1
        else:
            if self.selected_index >= len(self.filtered_tasks) or self.selected_index < 0:
                self.selected_index = 0
            for i, task in enumerate(self.filtered_tasks):
                checked = "☑" if task.id in self.selected_task_ids else "☐"
                
                group_name = "Sin grupo"
                if task.group_id is not None:
                    group = next((g for g in self.all_groups if g.id == task.group_id), None)
                    if group:
                        group_name = group.name
                
                text = task.text[:35] + "..." if len(task.text) > 35 else task.text
                group_text = f"📁 {group_name}"
                
                padding = " " * max(1, 50 - len(text) - len(group_text))
                display_text = f"{checked}  {text}{padding}{group_text}"
                
                item = Static(display_text, id=f"task-{i}", classes="task-item")
                await tasks_list.mount(item)
                if task.id in self.selected_task_ids:
                    item.add_class("checked")
                if i == self.selected_index:
                    item.add_class("selected")

    def action_focus_search(self) -> None:
        self.search_focused = True
        self._explicit_search_focus = True
        try:
            self.query_one("#ut-search-input", Input).focus()
        except: pass

    def action_blur_search(self) -> None:
        self.search_query = ""
        self.search_focused = False
        self._explicit_search_focus = False
        try:
            inp = self.query_one("#ut-search-input", Input)
            inp.value = ""
            inp.blur()
        except: pass
        self.set_focus(None)
        self.call_later(self.refresh_list)

    @on(Input.Changed, "#ut-search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        self.search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_list()

    @on(Input.Submitted, "#ut-search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_search()

    def action_move_up(self) -> None:
        if self.search_focused: return
        if self.filtered_tasks and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.search_focused: return
        if self.filtered_tasks and self.selected_index < len(self.filtered_tasks) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_toggle_task(self) -> None:
        if self.search_focused: return
        if not self.filtered_tasks or self.selected_index < 0:
            return
        task = self.filtered_tasks[self.selected_index]
        if task.id in self.selected_task_ids:
            self.selected_task_ids.remove(task.id)
        else:
            self.selected_task_ids.append(task.id)
        self.call_later(self.refresh_list)
    
    def update_selection(self) -> None:
        for i in range(len(self.filtered_tasks)):
            try:
                item = self.query_one(f"#task-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass

    def action_save(self) -> None:
        if self.search_focused:
            self.action_blur_search()
            return
        self.dismiss(self.selected_task_ids if self.selected_task_ids else None)
    
    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        if self.search_query or self.search_focused:
            self.action_blur_search()
        else:
            self.dismiss(None)

class GroupTab(Static):
    DEFAULT_CSS = """
    GroupTab {
        width: auto; height: 3; padding: 0 2; margin: 0 1;
        border: solid $primary-background; content-align: center middle;
    }
    GroupTab:hover { background: $boost; }
    GroupTab.active { border: solid $accent; background: $accent 20%; text-style: bold; }
    """
    
    def __init__(self, group_id: Optional[int], name: str, **kwargs) -> None:
        super().__init__(name, **kwargs)
        self.group_id = group_id
        self._active = False
    
    @property
    def active(self) -> bool:
        return self._active
    
    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
        self.set_class(value, "active")

    async def on_click(self) -> None:
        if self.app and hasattr(self.app, "_select_group_by_id"):
            await self.app._select_group_by_id(self.group_id)

class SortPickerModal(ModalScreen[Optional[dict[str, Optional[str]]]]):
    DEFAULT_CSS = """
    SortPickerModal { align: center middle; }
    SortPickerModal > VerticalScroll {
        width: 70; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    SortPickerModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    SortPickerModal .info-text { width: 100%; text-align: center; color: $text-muted; margin-bottom: 1; }
    SortPickerModal .category-title { 
        width: 100%; text-align: left; 
        text-style: bold; color: $accent;
        margin: 1 0; padding: 0 1;
    }
    SortPickerModal #sort-list { width: 100%; height: auto; max-height: 20; overflow-y: auto; padding: 1; }
    SortPickerModal .sort-item {
        width: 100%; height: 3; padding: 0 2;
        border: solid $primary-background; margin-bottom: 1;
    }
    SortPickerModal .sort-item:hover { background: $boost; }
    SortPickerModal .sort-item.selected { border: solid $accent; background: $surface-lighten-1; }
    SortPickerModal .sort-item.checked { color: $success; }
    SortPickerModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    SortPickerModal .button-row { width: 100%; height: 3; align: center middle; }
    SortPickerModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_sort", show=False),
        Binding("enter", "save", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]
    
    def __init__(self, current_criteria: dict[str, Optional[str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self.criteria = {
            "alphabetical": current_criteria.get("alphabetical"),
            "date": current_criteria.get("date"),
            "priority": current_criteria.get("priority")
        }
        
        self.flat_options = [
            ("alphabetical", "alpha_asc"),
            ("alphabetical", "alpha_desc"),
            ("date", "date_asc"),
            ("date", "date_desc"),
            ("priority", "priority_desc"),
            ("priority", "priority_asc")
        ]
        self.selected_index = 0
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("📊 Ordenar Tareas", classes="modal-title")
            yield Label("Prioridad: Prioridad → Fecha → Alfabético", classes="info-text")
            yield Container(id="sort-list")
            yield Label("↑↓ Navegar | Espacio: Seleccionar | Enter: Guardar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Limpiar todo", variant="warning", id="clear")
    
    async def on_mount(self) -> None:
        await self.refresh_list()
    
    async def refresh_list(self) -> None:
        sort_list = self.query_one("#sort-list", Container)
        await sort_list.remove_children()
        
        await sort_list.mount(Static("🔤 Alfabético:", classes="category-title"))
        
        alpha_options = [
            ("  A → Z", "alphabetical", "alpha_asc", 0),
            ("  Z → A", "alphabetical", "alpha_desc", 1)
        ]
        
        for text, category, value, idx in alpha_options:
            checked = "☑" if self.criteria.get(category) == value else "☐"
            display_text = f"{checked} {text}"
            item = Static(display_text, id=f"sort-{idx}", classes="sort-item")
            await sort_list.mount(item)
            if self.criteria.get(category) == value:
                item.add_class("checked")
            if idx == self.selected_index:
                item.add_class("selected")
        
        await sort_list.mount(Static("📅 Fecha:", classes="category-title"))
        
        date_options = [
            ("  Más próximas primero ↑", "date", "date_asc", 2),
            ("  Más lejanas primero ↓", "date", "date_desc", 3)
        ]
        
        for text, category, value, idx in date_options:
            checked = "☑" if self.criteria.get(category) == value else "☐"
            display_text = f"{checked} {text}"
            item = Static(display_text, id=f"sort-{idx}", classes="sort-item")
            await sort_list.mount(item)
            if self.criteria.get(category) == value:
                item.add_class("checked")
            if idx == self.selected_index:
                item.add_class("selected")
        
        await sort_list.mount(Static("⭐ Prioridad:", classes="category-title"))
        
        priority_options = [
            ("  Alta → Baja", "priority", "priority_desc", 4),
            ("  Baja → Alta", "priority", "priority_asc", 5)
        ]
        
        for text, category, value, idx in priority_options:
            checked = "☑" if self.criteria.get(category) == value else "☐"
            display_text = f"{checked} {text}"
            item = Static(display_text, id=f"sort-{idx}", classes="sort-item")
            await sort_list.mount(item)
            if self.criteria.get(category) == value:
                item.add_class("checked")
            if idx == self.selected_index:
                item.add_class("selected")
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#sort-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.flat_options)):
            try:
                item = self.query_one(f"#sort-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.selected_index < len(self.flat_options) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_toggle_sort(self) -> None:
        if self.selected_index < 0 or self.selected_index >= len(self.flat_options):
            return
        
        category, value = self.flat_options[self.selected_index]
        
        if self.criteria.get(category) == value:
            self.criteria[category] = None
        else:
            self.criteria[category] = value
        
        self.call_later(self.refresh_list)
    
    def action_save(self) -> None:
        self.dismiss(self.criteria)
    
    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#clear")
    def on_clear_btn(self) -> None:
        self.dismiss({"alphabetical": None, "date": None, "priority": None})
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
            self.action_save()

class EditDayItemsModal(ModalScreen[Optional[dict]]):
    DEFAULT_CSS = """
    EditDayItemsModal { align: center middle; }
    EditDayItemsModal > VerticalScroll {
        width: 80; height: 32; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    EditDayItemsModal .modal-title { text-align: center; text-style: bold; width: 100%; height: 1; margin-bottom: 1; }
    EditDayItemsModal .info-text { width: 100%; text-align: center; color: $text-muted; margin-bottom: 1; }
    EditDayItemsModal .section-header { 
        width: 100%; 
        text-align: left; 
        text-style: bold; 
        color: $accent;
        margin: 1 0;
        padding: 0 1;
    }
    EditDayItemsModal #items-list { width: 100%; height: 18; overflow-y: auto; border: solid $primary-background; padding: 1; }
    EditDayItemsModal .item {
        width: 100%; height: 3; padding: 0 1;
        border: solid $primary-background; margin-bottom: 1;
    }
    EditDayItemsModal .item:hover { background: $boost; }
    EditDayItemsModal .item.selected { border: solid $accent; background: $surface-lighten-1; }
    EditDayItemsModal .item.checked { color: $error; }
    EditDayItemsModal .empty-msg { width: 100%; text-align: center; color: $text-muted; text-style: italic; padding: 2; }
    EditDayItemsModal .hint { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    EditDayItemsModal .button-row { width: 100%; height: 3; align: center middle; }
    EditDayItemsModal Button { margin: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("space", "toggle_item", show=False),
        Binding("enter", "save", show=False),
        Binding("ctrl+s", "save", show=False, priority=True),
    ]
    
    def __init__(self, tasks: list[Task], all_groups: list[Group], date_str: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.all_groups = all_groups
        self.date_str = date_str
        
        self.items = []
        
        for task in tasks:
            if task.due_date == date_str:
                group_name = self._get_group_name(task.group_id)
                self.items.append(("task", task.id, None, task.text, group_name))
            
            for subtask in task.subtasks:
                if subtask.due_date == date_str:
                    self.items.append(("subtask", task.id, subtask.id, subtask.text, task.text))
        
        self.selected_item_ids = []
        self.selected_index = 0 if self.items else -1
    
    def _get_group_name(self, group_id: Optional[int]) -> str:
        if group_id is None:
            return "Sin grupo"
        group = next((g for g in self.all_groups if g.id == group_id), None)
        return group.name if group else "Sin grupo"
    
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label(f"✏️ Editar {self.date_str}", classes="modal-title")
            yield Label("Selecciona tareas/subtareas para QUITAR la fecha", classes="info-text")
            yield Container(id="items-list")
            yield Label("↑↓ Navegar | Espacio: Marcar para quitar | Enter: Aplicar | Esc: Cancelar", classes="hint")
            with Horizontal(classes="button-row"):
                yield Button("Quitar fechas", variant="error", id="save")
                yield Button("Cancelar", variant="default", id="cancel")
    
    async def on_mount(self) -> None:
        await self.refresh_list()
    
    async def refresh_list(self) -> None:
        items_list = self.query_one("#items-list", Container)
        await items_list.remove_children()
        
        if not self.items:
            await items_list.mount(Label("No hay tareas ni subtareas en este día", classes="empty-msg"))
            self.selected_index = -1
            return
        
        tasks_items = [item for item in self.items if item[0] == "task"]
        subtasks_items = [item for item in self.items if item[0] == "subtask"]
        
        current_index = 0
        
        if tasks_items:
            await items_list.mount(Static("📋 Tareas:", classes="section-header"))
            for item_type, task_id, subtask_id, text, parent_text in tasks_items:
                checked = "☒" if (item_type, task_id, subtask_id) in self.selected_item_ids else "☐"
                text_display = text[:35] + "..." if len(text) > 35 else text
                padding = " " * max(1, 50 - len(text_display) - len(parent_text))
                display_text = f"{checked}  {text_display}{padding}📁 {parent_text}"
                
                item = Static(display_text, id=f"item-{current_index}", classes="item")
                await items_list.mount(item)
                if (item_type, task_id, subtask_id) in self.selected_item_ids:
                    item.add_class("checked")
                if current_index == self.selected_index:
                    item.add_class("selected")
                current_index += 1
        
        if subtasks_items:
            await items_list.mount(Static("📝 Subtareas:", classes="section-header"))
            for item_type, task_id, subtask_id, text, parent_text in subtasks_items:
                checked = "☒" if (item_type, task_id, subtask_id) in self.selected_item_ids else "☐"
                text_display = text[:35] + "..." if len(text) > 35 else text
                parent_display = parent_text[:20] + "..." if len(parent_text) > 20 else parent_text
                padding = " " * max(1, 40 - len(text_display) - len(parent_display))
                display_text = f"{checked}  ↳ {text_display}{padding}🔗 {parent_display}"
                
                item = Static(display_text, id=f"item-{current_index}", classes="item")
                await items_list.mount(item)
                if (item_type, task_id, subtask_id) in self.selected_item_ids:
                    item.add_class("checked")
                if current_index == self.selected_index:
                    item.add_class("selected")
                current_index += 1
        
        self.scroll_to_selected()
    
    def scroll_to_selected(self) -> None:
        if self.selected_index >= 0:
            try:
                item = self.query_one(f"#item-{self.selected_index}", Static)
                item.scroll_visible()
            except: pass
    
    def update_selection(self) -> None:
        for i in range(len(self.items)):
            try:
                item = self.query_one(f"#item-{i}", Static)
                item.set_class(i == self.selected_index, "selected")
            except: pass
        self.scroll_to_selected()
    
    def action_move_up(self) -> None:
        if self.items and self.selected_index > 0:
            self.selected_index -= 1
            self.update_selection()
    
    def action_move_down(self) -> None:
        if self.items and self.selected_index < len(self.items) - 1:
            self.selected_index += 1
            self.update_selection()
    
    def action_toggle_item(self) -> None:
        if not self.items or self.selected_index < 0:
            return
        item_type, task_id, subtask_id, text, parent_text = self.items[self.selected_index]
        item_id = (item_type, task_id, subtask_id)
        if item_id in self.selected_item_ids:
            self.selected_item_ids.remove(item_id)
        else:
            self.selected_item_ids.append(item_id)
        self.call_later(self.refresh_list)
    
    def action_save(self) -> None:
        if not self.selected_item_ids:
            self.dismiss(None)
            return
        
        task_ids = [task_id for item_type, task_id, subtask_id in self.selected_item_ids if item_type == "task"]
        subtask_selections = [(task_id, subtask_id) for item_type, task_id, subtask_id in self.selected_item_ids if item_type == "subtask"]
        
        self.dismiss({
            "task_ids": task_ids,
            "subtask_selections": subtask_selections
        })
    
    @on(Button.Pressed, "#save")
    def on_save_btn(self) -> None:
        self.action_save()
    
    @on(Button.Pressed, "#cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)
    
    def action_cancel(self) -> None:
        self.dismiss(None)
        
    def on_key(self, event) -> None:
        if event.key == "ctrl+s":
            event.prevent_default()
            event.stop()
class SnakeModal(ModalScreen):
    BINDINGS = [
        Binding("ctrl+f", "exit_game", "Salir"),
        Binding("escape", "exit_game", "Salir", show=False),
        Binding("up", "dir_up", "Arriba", show=False),
        Binding("w", "dir_up", "Arriba", show=False),
        Binding("k", "dir_up", "Arriba", show=False),
        Binding("down", "dir_down", "Abajo", show=False),
        Binding("s", "dir_down", "Abajo", show=False),
        Binding("j", "dir_down", "Abajo", show=False),
        Binding("left", "dir_left", "Izquierda", show=False),
        Binding("a", "dir_left", "Izquierda", show=False),
        Binding("h", "dir_left", "Izquierda", show=False),
        Binding("right", "dir_right", "Derecha", show=False),
        Binding("d", "dir_right", "Derecha", show=False),
        Binding("l", "dir_right", "Derecha", show=False),
        Binding("r", "restart", "Reiniciar", show=False),
        Binding("enter", "restart", "Reiniciar", show=False),
    ]

    DEFAULT_CSS = """
    SnakeModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }
    #snake-box {
        width: 66;
        height: 25;
        border: double #00ff00;
        background: #0d1117;
        padding: 0 1;
        content-align: center middle;
    }
    #snake-title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: #00ff00;
        height: 1;
    }
    #snake-stats {
        width: 100%;
        text-align: center;
        color: #f3f4f6;
        height: 1;
        margin-bottom: 1;
    }
    #snake-board {
        width: 62;
        height: 16;
        border: solid #30363d;
        background: #000000;
    }
    #snake-footer {
        width: 100%;
        text-align: center;
        color: #8b949e;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.grid_w = 30
        self.grid_h = 14
        self.snake = [(15, 7), (14, 7), (13, 7)]
        self.dir = (1, 0)
        self.next_dir = (1, 0)
        self.score = 0
        self.start_time = time.time()
        self.end_time = None
        self.game_over = False
        self.food = (22, 7)
        self.game_timer = None

    def compose(self) -> ComposeResult:
        with Container(id="snake-box"):
            yield Label("🐍 SNAKE INFINITO 🐍", id="snake-title")
            yield Label("Puntuación: 0   |   Tiempo: 00:00", id="snake-stats")
            yield Static("", id="snake-board")
            yield Label("Atajos: Flechas / WASD para moverte | Ctrl+F para salir", id="snake-footer")

    def on_mount(self) -> None:
        self.food = self._spawn_food()
        self.game_timer = self.set_interval(0.12, self.game_step)
        self.render_game()

    def _spawn_food(self) -> tuple[int, int]:
        empty = [(x, y) for x in range(self.grid_w) for y in range(self.grid_h) if (x, y) not in self.snake]
        return random.choice(empty) if empty else (0, 0)

    def change_dir(self, dx: int, dy: int) -> None:
        if self.game_over:
            return
        if (dx, dy) != (-self.dir[0], -self.dir[1]):
            self.next_dir = (dx, dy)

    def action_dir_up(self) -> None: self.change_dir(0, -1)
    def action_dir_down(self) -> None: self.change_dir(0, 1)
    def action_dir_left(self) -> None: self.change_dir(-1, 0)
    def action_dir_right(self) -> None: self.change_dir(1, 0)

    def action_restart(self) -> None:
        if self.game_over:
            self.snake = [(15, 7), (14, 7), (13, 7)]
            self.dir = (1, 0)
            self.next_dir = (1, 0)
            self.score = 0
            self.start_time = time.time()
            self.end_time = None
            self.game_over = False
            self.food = self._spawn_food()
            self.query_one("#snake-footer", Label).update("Atajos: Flechas / WASD para moverte | Ctrl+F para salir")
            self.render_game()

    def action_exit_game(self) -> None:
        if self.game_timer:
            self.game_timer.stop()
        self.dismiss()

    def on_key(self, event) -> None:
        if event.key.lower() == "ctrl+f":
            event.prevent_default()
            event.stop()
            self.action_exit_game()

    def game_step(self) -> None:
        if self.game_over:
            return

        self.dir = self.next_dir
        hx, hy = self.snake[0][0] + self.dir[0], self.snake[0][1] + self.dir[1]

        if hx < 0 or hx >= self.grid_w or hy < 0 or hy >= self.grid_h or (hx, hy) in self.snake:
            self.game_over = True
            self.end_time = time.time()
            self.query_one("#snake-footer", Label).update("[bold red]¡GAME OVER![/bold red] Presiona 'R' para reiniciar | Ctrl+F para salir")
            self.render_game()
            return

        self.snake.insert(0, (hx, hy))
        if (hx, hy) == self.food:
            self.score += 1
            self.food = self._spawn_food()
        else:
            self.snake.pop()

        self.render_game()

    def render_game(self) -> None:
        curr_time = self.end_time or time.time()
        elapsed = int(curr_time - self.start_time)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        stats_label = self.query_one("#snake-stats", Label)
        stats_label.update(f"🍎 Puntuación: [bold yellow]{self.score}[/bold yellow]   |   ⏱️ Tiempo: [bold cyan]{time_str}[/bold cyan]")

        board_widget = self.query_one("#snake-board", Static)

        if self.game_over:
            total_sec = elapsed
            sec_unit = "segundo" if total_sec == 1 else "segundos"
            lines = [
                "",
                " ╔══════════════════════════════════════════════════╗",
                " ║                                                  ║",
                " ║               🎮  ¡GAME OVER!  🎮                ║",
                " ║                                                  ║",
                f" ║        🏆 Puntuación Final: {self.score:<16} ║",
                f" ║        ⏱️  Tiempo Aguantado: {time_str} ({total_sec} {sec_unit:<8}) ║",
                " ║                                                  ║",
                " ║        [yellow]Presiona 'R' o 'Enter' para reiniciar[/yellow]     ║",
                " ║        [cyan]Presiona 'Ctrl+F' para salir[/cyan]              ║",
                " ║                                                  ║",
                " ╚══════════════════════════════════════════════════╝",
                ""
            ]
            board_widget.update("\n".join(lines))
        else:
            board_rows = []
            for y in range(self.grid_h):
                row_cells = []
                for x in range(self.grid_w):
                    if (x, y) == self.snake[0]:
                        row_cells.append("[bold green]██[/bold green]")
                    elif (x, y) in self.snake:
                        row_cells.append("[green]██[/green]")
                    elif (x, y) == self.food:
                        row_cells.append("[bold red]██[/bold red]")
                    else:
                        row_cells.append("  ")
                board_rows.append("".join(row_cells))
            board_widget.update("\n".join(board_rows))

ASCII_DIGITS = {
    '0': ["█████", "█   █", "█   █", "█   █", "█████"],
    '1': ["  █  ", " ██  ", "  █  ", "  █  ", "█████"],
    '2': ["█████", "    █", "█████", "█    ", "█████"],
    '3': ["█████", "    █", "█████", "    █", "█████"],
    '4': ["█   █", "█   █", "█████", "    █", "    █"],
    '5': ["█████", "█    ", "█████", "    █", "█████"],
    '6': ["█████", "█    ", "█████", "█   █", "█████"],
    '7': ["█████", "    █", "   █ ", "  █  ", "  █  "],
    '8': ["█████", "█   █", "█████", "█   █", "█████"],
    '9': ["█████", "█   █", "█████", "    █", "█████"],
    ':': ["     ", "  █  ", "     ", "  █  ", "     "],
}

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]
DIAS_SEMANA = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]

def time_to_ascii(time_str: str) -> str:
    lines = ["", "", "", "", ""]
    for char in time_str:
        if char in ASCII_DIGITS:
            for i, line in enumerate(ASCII_DIGITS[char]):
                lines[i] += line + " "
    return "\n".join(lines)

def generate_calendar(year: int, month: int, today: datetime) -> str:
    cal = calendar.Calendar(firstweekday=0)
    header = f"         {MESES[month]} {year}         "
    days_header = "  ".join(DIAS_SEMANA)
    weeks = []
    for week in cal.monthdayscalendar(year, month):
        week_str = ""
        for day in week:
            if day == 0:
                week_str += "    "
            else:
                if year == today.year and month == today.month and day == today.day:
                    week_str += f"[bold cyan][{day:2d}][/bold cyan]"
                else:
                    week_str += f" {day:2d} "
        weeks.append(week_str)
    lines = ["", header, "─" * len(header), days_header, "─" * len(days_header)]
    lines.extend(weeks)
    return "\n".join(lines)


class PomodoroConfigModal(ModalScreen[Optional[tuple[int, int]]]):
    DEFAULT_CSS = """
    PomodoroConfigModal { align: center middle; }
    PomodoroConfigModal > VerticalScroll {
        width: 50; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    PomodoroConfigModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    PomodoroConfigModal .section-label { margin-top: 1; color: $text-muted; }
    PomodoroConfigModal Input { width: 100%; margin-bottom: 1; }
    PomodoroConfigModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    PomodoroConfigModal Button { margin: 0 1; }
    """
    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, focus_time: int, break_time: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.focus_time = focus_time
        self.break_time = break_time

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("⚙️ Configurar Pomodoro", classes="modal-title")
            yield Label("Tiempo de focus (minutos):", classes="section-label")
            yield Input(value=str(self.focus_time), id="focus-input")
            yield Label("Tiempo de descanso (minutos):", classes="section-label")
            yield Input(value=str(self.break_time), id="break-input")
            with Horizontal(classes="button-row"):
                yield Button("Guardar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        try: self.query_one("#focus-input", Input).focus()
        except: pass

    @on(Button.Pressed, "#save")
    @on(Input.Submitted)
    def on_save(self) -> None:
        try:
            focus = int(self.query_one("#focus-input", Input).value)
            break_t = int(self.query_one("#break-input", Input).value)
            if focus > 0 and break_t > 0:
                self.dismiss((focus, break_t))
            else:
                self.dismiss(None)
        except ValueError:
            self.dismiss(None)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TimerConfigModal(ModalScreen[Optional[tuple[int, int, str]]]):
    DEFAULT_CSS = """
    TimerConfigModal { align: center middle; }
    TimerConfigModal > VerticalScroll {
        width: 50; height: auto; border: thick $primary;
        background: $surface; padding: 1 2;
    }
    TimerConfigModal .modal-title { text-align: center; text-style: bold; width: 100%; margin-bottom: 1; }
    TimerConfigModal .section-label { margin-top: 1; color: $text-muted; }
    TimerConfigModal Input { width: 100%; margin-bottom: 1; }
    TimerConfigModal .button-row { width: 100%; height: auto; align: center middle; margin-top: 1; }
    TimerConfigModal Button { margin: 0 1; }
    """
    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, initial_minutes: int = 5, initial_seconds: int = 0, initial_name: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.initial_minutes = initial_minutes
        self.initial_seconds = initial_seconds
        self.initial_name = initial_name

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("⏲️ Configurar Temporizador", classes="modal-title")
            yield Label("Minutos:", classes="section-label")
            yield Input(value=str(self.initial_minutes) if self.initial_minutes > 0 else "5", id="minutes-input", placeholder="Minutos")
            yield Label("Segundos:", classes="section-label")
            yield Input(value=str(self.initial_seconds), id="seconds-input", placeholder="Segundos")
            yield Label("Nombre (opcional):", classes="section-label")
            yield Input(value=self.initial_name, id="name-input", placeholder="Ej: Té, Ejercicio...")
            with Horizontal(classes="button-row"):
                yield Button("Iniciar", variant="primary", id="start")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        try: self.query_one("#minutes-input", Input).focus()
        except: pass

    @on(Button.Pressed, "#start")
    @on(Input.Submitted)
    def on_start(self) -> None:
        try:
            minutes = int(self.query_one("#minutes-input", Input).value or "0")
            seconds = int(self.query_one("#seconds-input", Input).value or "0")
            name = self.query_one("#name-input", Input).value.strip()
            if minutes > 0 or seconds > 0:
                self.dismiss((minutes, seconds, name))
            else:
                self.dismiss(None)
        except ValueError:
            self.dismiss(None)

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ClockModal(ModalScreen):
    BINDINGS = [
        Binding("escape", "exit_clock", "Ocultar"),
        Binding("ctrl+t", "exit_clock", "Ocultar", show=False),
        Binding("left", "prev_tab", "Anterior", show=False),
        Binding("h", "prev_tab", "Anterior", show=False),
        Binding("right", "next_tab", "Siguiente", show=False),
        Binding("l", "next_tab", "Siguiente", show=False),
        Binding("space", "toggle_start", "Iniciar/Pausar"),
        Binding("r", "reset", "Reiniciar"),
        Binding("s", "settings", "Configurar"),
        Binding("q", "quit_clock", "Cerrar y Apagar"),
    ]

    DEFAULT_CSS = """
    ClockModal {
        align: center middle;
    }
    #clock-modal-box {
        width: 95%;
        height: 92%;
        max-width: 140;
        max-height: 45;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
        content-align: center middle;
    }
    #clock-tabs-row {
        width: 100%;
        height: 3;
        layout: horizontal;
        align: center middle;
        margin-bottom: 1;
    }
    .clock-tab-btn {
        width: auto;
        height: 3;
        padding: 0 3;
        margin: 0 1;
        border: solid $primary-background;
        content-align: center middle;
    }
    .clock-tab-btn:hover {
        background: $boost;
    }
    .clock-tab-btn.active {
        border: solid $accent;
        background: $surface-lighten-1;
        color: $accent;
        text-style: bold;
    }
    #clock-main-display {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $accent;
    }
    #clock-sub-info {
        width: 100%;
        height: 1;
        text-align: center;
        text-style: bold;
        color: $text;
        margin-top: 1;
    }
    #clock-status-label {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
    }
    #clock-footer-hint {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.modes = [
            ("stopwatch", "⏱️ Cronómetro", "Medidor de tiempo transcurrido"),
            ("pomodoro", "🍅 Pomodoro", "Técnica Pomodoro (Focus / Descanso)"),
            ("timer", "⏲️ Temporizador", "Cuenta regresiva con notificación"),
            ("clock", "🕐 Reloj", "Reloj digital en tiempo real"),
        ]

    @property
    def state(self) -> dict:
        return self.app.time_tools_state

    def compose(self) -> ComposeResult:
        active_idx = self.state.get("active_mode_index", 0)
        with Container(id="clock-modal-box"):
            with Horizontal(id="clock-tabs-row"):
                for i, (mode_id, label, _) in enumerate(self.modes):
                    classes = "clock-tab-btn active" if i == active_idx else "clock-tab-btn"
                    yield Static(label, id=f"clock-tab-{i}", classes=classes)
            yield Static("", id="clock-main-display")
            yield Static("", id="clock-sub-info")
            yield Static("", id="clock-status-label")
            yield Static("", id="clock-footer-hint")

    def on_mount(self) -> None:
        self.update_tab_ui()
        self.set_interval(0.1, self.tick)

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "s":
            event.prevent_default()
            event.stop()
            self.action_settings()
        elif key == "r":
            event.prevent_default()
            event.stop()
            self.action_reset()
        elif key == "space":
            event.prevent_default()
            event.stop()
            self.action_toggle_start()
        elif key in ["left", "h"]:
            event.prevent_default()
            event.stop()
            self.action_prev_tab()
        elif key in ["right", "l"]:
            event.prevent_default()
            event.stop()
            self.action_next_tab()
        elif key == "escape":
            event.prevent_default()
            event.stop()
            self.action_exit_clock()
        elif key == "q":
            event.prevent_default()
            event.stop()
            self.action_quit_clock()

    def on_click(self, event) -> None:
        for i in range(len(self.modes)):
            try:
                btn = self.query_one(f"#clock-tab-{i}", Static)
                if event.widget == btn:
                    self.state["active_mode_index"] = i
                    self.update_tab_ui()
                    break
            except: pass

    def action_prev_tab(self) -> None:
        idx = self.state.get("active_mode_index", 0)
        self.state["active_mode_index"] = (idx - 1) % len(self.modes)
        self.update_tab_ui()

    def action_next_tab(self) -> None:
        idx = self.state.get("active_mode_index", 0)
        self.state["active_mode_index"] = (idx + 1) % len(self.modes)
        self.update_tab_ui()

    def update_tab_ui(self) -> None:
        active_idx = self.state.get("active_mode_index", 0)
        for i in range(len(self.modes)):
            try:
                tab = self.query_one(f"#clock-tab-{i}", Static)
                tab.set_class(i == active_idx, "active")
            except: pass

        mode_id, label, desc = self.modes[active_idx]
        footer_hint = self.query_one("#clock-footer-hint", Static)

        if mode_id == "stopwatch":
            footer_hint.update("←/→: Cambiar | Espacio: Iniciar/Pausar | R: Reiniciar | Esc: Ocultar | Q: Apagar")
        elif mode_id == "pomodoro":
            f_t = self.state["pomodoro_focus_time"]
            b_t = self.state["pomodoro_break_time"]
            footer_hint.update(f"←/→: Cambiar | Espacio: Iniciar/Pausar | R: Reiniciar | S: Config ({f_t}/{b_t}m) | Esc: Ocultar | Q: Apagar")
        elif mode_id == "timer":
            footer_hint.update("←/→: Cambiar | Espacio: Iniciar/Pausar | R: Reiniciar | S: Configurar | Esc: Ocultar | Q: Apagar")
        elif mode_id == "clock":
            footer_hint.update("←/→: Cambiar | Esc: Ocultar | Q: Cerrar")

    def tick(self) -> None:
        active_idx = self.state.get("active_mode_index", 0)
        mode_id = self.modes[active_idx][0]
        main_disp = self.query_one("#clock-main-display", Static)
        sub_info = self.query_one("#clock-sub-info", Static)
        status_lbl = self.query_one("#clock-status-label", Static)

        if mode_id == "stopwatch":
            if self.state["stopwatch_running"] and self.state["stopwatch_start_time"]:
                elapsed = self.state["stopwatch_elapsed"] + (datetime.now() - self.state["stopwatch_start_time"])
            else:
                elapsed = self.state["stopwatch_elapsed"]
            total_sec = int(elapsed.total_seconds())
            h, rem = divmod(total_sec, 3600)
            m, s = divmod(rem, 60)
            t_str = f"{h:02d}:{m:02d}:{s:02d}"
            main_disp.update(time_to_ascii(t_str))
            sub_info.update("⏱️ Cronómetro - Medidor de tiempo transcurrido")
            status_lbl.update("▶️ En marcha" if self.state["stopwatch_running"] else "⏸️ Pausado")

        elif mode_id == "pomodoro":
            if self.state["pomodoro_running"] and self.state["pomodoro_start_time"]:
                elapsed = datetime.now() - self.state["pomodoro_start_time"]
                remaining = self.state["pomodoro_remaining"] - elapsed
            else:
                remaining = self.state["pomodoro_remaining"]

            total_sec = max(0, int(remaining.total_seconds()))
            m, s = divmod(total_sec, 60)
            t_str = f"00:{m:02d}:{s:02d}"
            main_disp.update(time_to_ascii(t_str))
            mode_txt = "[bold green]🎯 FOCUS[/bold green]" if self.state["pomodoro_is_focus"] else "[bold yellow]☕ DESCANSO[/bold yellow]"
            sub_info.update(f"🍅 Pomodoro - Estado: {mode_txt}")
            status_lbl.update("▶️ En marcha" if self.state["pomodoro_running"] else "⏸️ Pausado")

        elif mode_id == "timer":
            if self.state["timer_running"] and self.state["timer_start_time"]:
                elapsed = datetime.now() - self.state["timer_start_time"]
                remaining = self.state["timer_remaining"] - elapsed
            else:
                remaining = self.state["timer_remaining"]

            total_sec = max(0, int(remaining.total_seconds()))
            h, rem = divmod(total_sec, 3600)
            m, s = divmod(rem, 60)
            t_str = f"{h:02d}:{m:02d}:{s:02d}"
            main_disp.update(time_to_ascii(t_str))
            t_name = self.state["timer_name"]
            t_title = f"⏲️ Temporizador ({t_name})" if t_name else "⏲️ Temporizador"
            sub_info.update(t_title)
            if self.state["timer_finished"]:
                status_lbl.update("[bold red]🔔 ¡TIEMPO TERMINADO![/bold red]")
            elif self.state["timer_running"]:
                status_lbl.update("▶️ En marcha")
            elif self.state["timer_duration"].total_seconds() > 0:
                status_lbl.update("⏸️ Pausado")
            else:
                status_lbl.update("Pulsa 's' para configurar minutos y segundos")

        elif mode_id == "clock":
            now = datetime.now()
            main_disp.update(time_to_ascii(now.strftime("%H:%M:%S")))
            sub_info.update("🕐 Reloj Digital")
            status_lbl.update(now.strftime("%A, %d de %B de %Y"))

    def action_toggle_start(self) -> None:
        active_idx = self.state.get("active_mode_index", 0)
        mode_id = self.modes[active_idx][0]
        if mode_id == "stopwatch":
            if self.state["stopwatch_running"]:
                if self.state["stopwatch_start_time"]:
                    self.state["stopwatch_elapsed"] += datetime.now() - self.state["stopwatch_start_time"]
                self.state["stopwatch_start_time"] = None
                self.state["stopwatch_running"] = False
            else:
                self.state["stopwatch_start_time"] = datetime.now()
                self.state["stopwatch_running"] = True

        elif mode_id == "pomodoro":
            if self.state["pomodoro_running"]:
                if self.state["pomodoro_start_time"]:
                    elapsed = datetime.now() - self.state["pomodoro_start_time"]
                    self.state["pomodoro_remaining"] -= elapsed
                self.state["pomodoro_start_time"] = None
                self.state["pomodoro_running"] = False
            else:
                self.state["pomodoro_start_time"] = datetime.now()
                self.state["pomodoro_running"] = True

        elif mode_id == "timer":
            if self.state["timer_duration"].total_seconds() == 0:
                self.action_settings()
            elif self.state["timer_running"]:
                if self.state["timer_start_time"]:
                    elapsed = datetime.now() - self.state["timer_start_time"]
                    self.state["timer_remaining"] -= elapsed
                self.state["timer_start_time"] = None
                self.state["timer_running"] = False
            else:
                self.state["timer_start_time"] = datetime.now()
                self.state["timer_running"] = True
                self.state["timer_finished"] = False

    def action_reset(self) -> None:
        active_idx = self.state.get("active_mode_index", 0)
        mode_id = self.modes[active_idx][0]
        if mode_id == "stopwatch":
            self.state["stopwatch_running"] = False
            self.state["stopwatch_elapsed"] = timedelta()
            self.state["stopwatch_start_time"] = None

        elif mode_id == "pomodoro":
            self.state["pomodoro_running"] = False
            self.state["pomodoro_is_focus"] = True
            self.state["pomodoro_remaining"] = timedelta(minutes=self.state["pomodoro_focus_time"])
            self.state["pomodoro_start_time"] = None

        elif mode_id == "timer":
            self.state["timer_running"] = False
            self.state["timer_remaining"] = self.state["timer_duration"]
            self.state["timer_start_time"] = None
            self.state["timer_finished"] = False

    def action_settings(self) -> None:
        active_idx = self.state.get("active_mode_index", 0)
        mode_id = self.modes[active_idx][0]
        if mode_id == "pomodoro":
            def on_result(result: Optional[tuple[int, int]]) -> None:
                if result:
                    focus, break_t = result
                    self.state["pomodoro_focus_time"] = focus
                    self.state["pomodoro_break_time"] = break_t
                    self.state["pomodoro_running"] = False
                    self.state["pomodoro_is_focus"] = True
                    self.state["pomodoro_remaining"] = timedelta(minutes=focus)
                    self.state["pomodoro_start_time"] = None
                    self.update_tab_ui()

            self.app.push_screen(PomodoroConfigModal(self.state["pomodoro_focus_time"], self.state["pomodoro_break_time"]), on_result)

        elif mode_id == "timer":
            curr_min = int(self.state["timer_duration"].total_seconds() // 60)
            curr_sec = int(self.state["timer_duration"].total_seconds() % 60)
            def on_result(result: Optional[tuple[int, int, str]]) -> None:
                if result:
                    minutes, seconds, name = result
                    self.state["timer_duration"] = timedelta(minutes=minutes, seconds=seconds)
                    self.state["timer_remaining"] = self.state["timer_duration"]
                    self.state["timer_name"] = name
                    self.state["timer_running"] = False
                    self.state["timer_start_time"] = None
                    self.state["timer_finished"] = False
                    self.update_tab_ui()

            self.app.push_screen(TimerConfigModal(curr_min, curr_sec, self.state["timer_name"]), on_result)

    def action_exit_clock(self) -> None:
        self.dismiss()

    def action_quit_clock(self) -> None:
        self.state["stopwatch_running"] = False
        self.state["stopwatch_elapsed"] = timedelta()
        self.state["stopwatch_start_time"] = None
        self.state["pomodoro_running"] = False
        self.state["pomodoro_is_focus"] = True
        self.state["pomodoro_remaining"] = timedelta(minutes=self.state["pomodoro_focus_time"])
        self.state["pomodoro_start_time"] = None
        self.state["timer_running"] = False
        self.state["timer_duration"] = timedelta()
        self.state["timer_remaining"] = timedelta()
        self.state["timer_start_time"] = None
        self.state["timer_name"] = ""
        self.state["timer_finished"] = False
        self.dismiss()


class TodoApp(App):
    CSS = """
    Screen { background: $background; }
    Header {
        background: #1e1e1e;
        color: #00ff00;  /* Verde terminal */
    }
    Header .header--title {
        color: #00ff00;
        text-style: bold;
    }
    #top-bar-container { width: 100%; height: 3; layout: horizontal; }
    #tabs-container { width: 1fr; height: 3; layout: horizontal; overflow-x: auto; padding: 0 1; }
    #header-clock {
        width: 25;
        height: 3;
        content-align: center middle;
        text-align: center;
        border: solid $primary-background;
        background: $surface;
        color: $accent;
        text-style: bold;
    }
    #main-search-container { width: 100%; height: auto; padding: 0 1; margin-top: 1; margin-bottom: 1; }
    #main-search-container.hidden { display: none; }
    #main-search-label { color: $text-muted; margin-bottom: 0; margin-left: 1; }
    #main-search-input { width: 100%; }
    #task-list { width: 100%; height: 1fr; overflow-y: auto; padding: 1; }
    #calendar-view { width: 100%; height: 1fr; padding: 1; display: none; align: center top; }
    #calendar-view.visible { display: block; }
    #calendar-header { width: 100%; text-align: center; text-style: bold; padding: 1; }
    #calendar-display { width: 100%; text-align: center; padding: 1; }
    #calendar-day-tasks { width: 100%; text-align: center; padding: 1; margin-top: 1; border-top: solid $primary-background; }
    #calendar-hint { width: 100%; text-align: center; color: $text-muted; padding: 1; }
    #empty-message { width: 100%; height: 100%; content-align: center middle; color: $text-muted; text-style: italic; }
    #stats { dock: bottom; width: 100%; height: 1; background: $primary-background; color: $text; padding: 0 2; }
    #completed-separator, #completed-separator-subtasks, #in-progress-separator, #on-hold-separator, #in-progress-separator-subtasks, #on-hold-separator-subtasks, .status-subseparator { width: 100%; height: 1; text-align: center; color: $text-muted; margin: 1 0; }
    .section-separator-main {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        color: #bd93f9;
        text-style: bold;
        margin: 1 0;
    }
    .empty-section-label {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
        margin-bottom: 1;
    }
    .section-separator-sub {
        width: 100%;
        height: 1;
        text-align: left;
        color: $primary;
        text-style: bold;
        margin: 1 0 0 1;
    }
    .general-tags-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        padding: 1;
        margin-bottom: 1;
    }
    .general-tag-chip {
        background: #90EE90;
        color: #000000;
        margin-right: 1;
        padding: 0 1;
        text-style: bold;
    }
    """
    
    BINDINGS = [
        Binding("a", "add_task", "Añadir"),
        Binding("e", "edit_task", "Editar"),
        Binding("d", "delete_task", "Eliminar"),
        Binding("f", "filter_tasks", "Filtrar"),
        Binding("f5", "reset_filters", "Reset Filtros", show=True),
        Binding("o", "sort_tasks", "Ordenar"),
        Binding("g", "new_group", "Nuevo Grupo"),
        Binding("G", "group_options", "Opc. Grupo"),
        Binding("c", "toggle_calendar", "Calendario"),
        Binding("i", "today_tasks", "Hoy"),
        Binding("/", "focus_main_search", "Buscar"),
        Binding("x", "edit_day", "Editar día"),
        Binding("X", "clear_day", "Vaciar día"),
        Binding("ctrl+g", "open_snake", "Snake", show=False),
        Binding("escape", "handle_escape", show=False),
        Binding("left", "nav_left", show=False),
        Binding("right", "nav_right", show=False),
        Binding("up", "nav_up", show=False),
        Binding("down", "nav_down", show=False),
        Binding("h", "nav_left", show=False),
        Binding("l", "nav_right", show=False),
        Binding("k", "nav_up", show=False),
        Binding("j", "nav_down", show=False),
        Binding("n", "next_month", "Mes sig.", show=False),
        Binding("p", "prev_month", "Mes ant.", show=False),
        Binding("space", "toggle_done", "Completar"),
        Binding("enter", "action_enter", show=False),
        Binding("q", "quit", "Salir"),
        Binding("ctrl+z", "undo", "Deshacer"),
        Binding("ctrl+y", "redo", "Rehacer"),
    ]
    
    TITLE = "MyTaskit"
    theme = "dracula"
    
    def __init__(self) -> None:
        super().__init__()
        self.tasks: list[Task] = []
        self.groups: list[Group] = []
        self.tags: list[Tag] = []
        self.notes: list[Note] = []
        self.canvas_list: list[Canvas] = []
        self.voice_notes: list[VoiceNote] = []
        self.next_task_id = 1
        self.next_group_id = 1
        self.next_tag_id = 1
        self.next_subtask_id = 1
        self.next_note_id = 1
        self.next_canvas_id = 1
        self.next_voice_note_id = 1
        self.selected_index = 0
        self.GENERAL_GROUP_ID = -1
        self.NOTES_GROUP_ID = -2
        self.CANVAS_GROUP_ID = -3
        self.AUDIO_GROUP_ID = -4
        self.TAGS_GROUP_ID = -5
        self.SUBTASKS_GROUP_ID = -6
        self.current_group_id: Optional[int] = self.GENERAL_GROUP_ID
        self.data_file = Path.home() / "todo" / "todo_tasks.json"
        self.data_file.parent.mkdir(exist_ok=True)
        
        self.calendar_mode = False
        self.cal_year = date.today().year
        self.cal_month = date.today().month
        self.cal_day = date.today().day
        
        self.filter_dates: list[str] = []
        self.filter_tag_ids: list[int] = []
        self.filter_statuses: list[str] = []
        self.filter_priorities: list[int] = []
        
        self.sort_criteria: dict[str, Optional[str]] = {
            "alphabetical": None,
            "date": None,
            "priority": None
        }
        
        self.save_lock = Lock()

        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self.max_undo = 50

        self.main_search_query = ""
        self.main_search_focused = False
        self._explicit_search_focus = False

        self.konami_sequence = []
        self.konami_code = ["up", "up", "down", "down", "left", "right", "left", "right", "b", "a"]
        self.load_data()

        self.time_tools_state = {
            "active_mode_index": 0,
            "stopwatch_running": False,
            "stopwatch_elapsed": timedelta(),
            "stopwatch_start_time": None,
            "pomodoro_running": False,
            "pomodoro_focus_time": 25,
            "pomodoro_break_time": 5,
            "pomodoro_remaining": timedelta(minutes=25),
            "pomodoro_is_focus": True,
            "pomodoro_start_time": None,
            "timer_running": False,
            "timer_duration": timedelta(),
            "timer_remaining": timedelta(),
            "timer_start_time": None,
            "timer_name": "",
            "timer_finished": False,
        }
    
    def action_reset_filters(self) -> None:
        self.filter_dates = []
        self.filter_tag_ids = []
        self.filter_statuses = []
        self.filter_priorities = []
        self._clear_main_search()
        self.selected_index = 0
        self.refresh_view()
        self.update_stats()
        self.notify("🔄 Filtros reseteados", severity="information", timeout=2)
    
    def _clear_main_search(self) -> None:
        need_refresh = bool(self.main_search_query)
        self.main_search_query = ""
        self.main_search_focused = False
        self._explicit_search_focus = False
        try:
            self.query_one("#main-search-input", Input).value = ""
            self.query_one("#main-search-input", Input).blur()
        except:
            pass
        self.set_focus(None)
        if need_refresh:
            self.refresh_view()
            self.update_stats()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Horizontal(id="top-bar-container"):
                yield Horizontal(id="tabs-container")
                yield Static("", id="header-clock")
            with Container(id="main-search-container"):
                yield Label("🔍 Buscar (/ para activar | Tab/Esc para salir y volver a atajos):", id="main-search-label")
                yield UndoableInput(placeholder="Escribe para buscar...", id="main-search-input")
            yield Container(id="task-list")
            with Container(id="calendar-view"):
                yield Static("", id="calendar-header")
                yield Static("", id="calendar-display")
                yield Static("", id="calendar-day-tasks")
                yield Static("←→↑↓: Navegar | n/p: Mes | t: Hoy | a: Asignar | x: Editar día | X: Vaciar día | Enter: Ver | Esc: Volver", id="calendar-hint")
            yield Static("", id="stats")
        yield Footer()
    
    async def on_mount(self) -> None:
        await self.refresh_tabs()
        await self.refresh_view()
        self.update_stats()
        self.set_timer(0.1, self.show_today_reminders)
        self.set_interval(10, self.save_data)
        self.set_interval(0.1, self._update_background_time_tools)
        self._update_background_time_tools()
        try:
            self.query_one("#main-search-input", Input).blur()
        except:
            pass

    def _update_background_time_tools(self) -> None:
        state = self.time_tools_state
        now = datetime.now()
        try:
            self.query_one("#header-clock", Static).update(f"🕒 {now.strftime('%d/%m/%Y %H:%M:%S')}")
        except Exception:
            pass

        # Background Pomodoro check
        if state["pomodoro_running"] and state["pomodoro_start_time"]:
            elapsed = now - state["pomodoro_start_time"]
            remaining = state["pomodoro_remaining"] - elapsed
            if remaining.total_seconds() <= 0:
                state["pomodoro_is_focus"] = not state["pomodoro_is_focus"]
                if state["pomodoro_is_focus"]:
                    state["pomodoro_remaining"] = timedelta(minutes=state["pomodoro_focus_time"])
                else:
                    state["pomodoro_remaining"] = timedelta(minutes=state["pomodoro_break_time"])
                state["pomodoro_start_time"] = now
                msg = "🎯 ¡Tiempo de FOCUS!" if state["pomodoro_is_focus"] else "☕ ¡Tiempo de DESCANSO!"
                self.notify(msg, title="Pomodoro", timeout=10)

        # Background Timer check
        if state["timer_running"] and state["timer_start_time"]:
            elapsed = now - state["timer_start_time"]
            remaining = state["timer_remaining"] - elapsed
            if remaining.total_seconds() <= 0:
                state["timer_remaining"] = timedelta()
                state["timer_running"] = False
                state["timer_start_time"] = None
                if not state["timer_finished"]:
                    state["timer_finished"] = True
                    name_str = state["timer_name"] if state["timer_name"] else "Temporizador"
                    self.notify(f"⏰ ¡Tiempo de '{name_str}' terminado!", title="Temporizador", timeout=10)

    def action_open_clock(self) -> None:
        if self.main_search_focused:
            return
        self.push_screen(ClockModal())

    def on_exit(self) -> None:
        self.save_data()

    def action_focus_main_search(self) -> None:
        if self.calendar_mode:
            return
        self.main_search_focused = True
        self._explicit_search_focus = True
        try:
            search_container = self.query_one("#main-search-container", Container)
            search_container.remove_class("hidden")
        except:
            pass
        self.query_one("#main-search-input", Input).focus()

    def action_blur_main_search(self) -> None:
        if not self.main_search_focused and not self.main_search_query:
            return
        self._clear_main_search()

    @on(Input.Changed, "#main-search-input")
    async def on_main_search_changed(self, event: Input.Changed) -> None:
        self.main_search_query = event.value.strip()
        self.selected_index = 0
        await self.refresh_view()
        self.update_stats()

    @on(Input.Submitted, "#main-search-input")
    def on_main_search_submitted(self, event: Input.Submitted) -> None:
        self.action_blur_main_search()

    def action_today_tasks(self) -> None:
        if self.main_search_focused: return
        today = date.today()
        tasks, subtasks = self._get_tasks_for_date(today.year, today.month, today.day)
        date_str = f"{today.day}/{today.month}/{today.year}"
        
        def on_result(result):
            if result:
                item_type, item_obj = result
                self._go_to_task(item_obj)
        
        self.push_screen(DayItemsModal(tasks, subtasks, date_str), on_result)
    
    def show_today_reminders(self) -> None:
        today_str = date.today().strftime("%Y-%m-%d")
        today_tasks = []
        today_subtasks = []
        
        for task in self.tasks:
            if task.due_date == today_str and not task.done:
                if task.group_id is None:
                    group_name = "Sin grupo"
                else:
                    group = next((g for g in self.groups if g.id == task.group_id), None)
                    group_name = group.name if group else "Sin grupo"
                today_tasks.append((task, group_name))
            
            for subtask in task.subtasks:
                if subtask.due_date == today_str and not subtask.done:
                    if task.group_id is None:
                        group_name = "Sin grupo"
                    else:
                        group = next((g for g in self.groups if g.id == task.group_id), None)
                        group_name = group.name if group else "Sin grupo"
                    parent_info = f"{task.text[:30]}..." if len(task.text) > 30 else task.text
                    today_subtasks.append((subtask, parent_info, group_name))
        
        all_reminders = []
        
        for task, group_name in today_tasks:
            all_reminders.append(("task", task, group_name, None))
        
        for subtask, parent_info, group_name in today_subtasks:
            all_reminders.append(("subtask", subtask, group_name, parent_info))
        
        def show_next(index=0):
            if index < len(all_reminders):
                item_type, item_obj, group_name, parent_info = all_reminders[index]
                
                def on_close(result):
                    show_next(index + 1)
                
                if item_type == "task":
                    self.push_screen(ReminderModal(item_obj, group_name), on_close)
                else:
                    self.push_screen(SubtaskReminderModal(item_obj, parent_info, group_name), on_close)
        
        show_next()
    
    async def refresh_tabs(self) -> None:
        tabs = self.query_one("#tabs-container", Horizontal)
        
        existing_tabs = {t.id: t for t in tabs.query(GroupTab) if t.id}
        if self.calendar_mode:
            expected_ids = ["tab-calendar"]
        else:
            expected_ids = ["tab-general", "tab-all", "tab-subtasks", "tab-notes", "tab-canvas", "tab-audio", "tab-tags"] + [f"tab-{g.id}" for g in self.groups]

        if list(existing_tabs.keys()) == expected_ids:
            if self.calendar_mode:
                existing_tabs["tab-calendar"].active = True
            else:
                existing_tabs["tab-general"].active = (self.current_group_id == self.GENERAL_GROUP_ID)
                existing_tabs["tab-all"].active = (self.current_group_id is None)
                existing_tabs["tab-subtasks"].active = (self.current_group_id == self.SUBTASKS_GROUP_ID)
                existing_tabs["tab-notes"].active = (self.current_group_id == self.NOTES_GROUP_ID)
                existing_tabs["tab-canvas"].active = (self.current_group_id == self.CANVAS_GROUP_ID)
                existing_tabs["tab-audio"].active = (self.current_group_id == self.AUDIO_GROUP_ID)
                existing_tabs["tab-tags"].active = (self.current_group_id == self.TAGS_GROUP_ID)
                for g in self.groups:
                    t = existing_tabs.get(f"tab-{g.id}")
                    if t:
                        icon = "📂" if self.current_group_id == g.id else "📁"
                        t.update(f"{icon} {g.name}")
                        t.active = (self.current_group_id == g.id)
            return

        for child in list(tabs.children):
            await child.remove()
        
        if self.calendar_mode:
            tab = GroupTab(None, "📅 Calendario", id="tab-calendar")
            await tabs.mount(tab)
            tab.active = True
        else:
            tab = GroupTab(self.GENERAL_GROUP_ID, "📚 General", id="tab-general")
            await tabs.mount(tab)
            tab.active = (self.current_group_id == self.GENERAL_GROUP_ID)
            
            tab = GroupTab(None, "📋 Sin grupo", id="tab-all")
            await tabs.mount(tab)
            tab.active = (self.current_group_id is None)

            tab = GroupTab(self.SUBTASKS_GROUP_ID, "📋 Subtareas", id="tab-subtasks")
            await tabs.mount(tab)
            tab.active = (self.current_group_id == self.SUBTASKS_GROUP_ID)

            tab = GroupTab(self.NOTES_GROUP_ID, "📝 Notas", id="tab-notes")
            await tabs.mount(tab)
            tab.active = (self.current_group_id == self.NOTES_GROUP_ID)

            tab = GroupTab(self.CANVAS_GROUP_ID, "🎨 Pizarra", id="tab-canvas")
            await tabs.mount(tab)
            tab.active = (self.current_group_id == self.CANVAS_GROUP_ID)

            tab = GroupTab(self.AUDIO_GROUP_ID, "🎤 Audios", id="tab-audio")
            await tabs.mount(tab)
            tab.active = (self.current_group_id == self.AUDIO_GROUP_ID)

            tab = GroupTab(self.TAGS_GROUP_ID, "🏷️ Etiquetas", id="tab-tags")
            await tabs.mount(tab)
            tab.active = (self.current_group_id == self.TAGS_GROUP_ID)

            for g in self.groups:
                icon = "📂" if self.current_group_id == g.id else "📁"
                t = GroupTab(g.id, f"{icon} {g.name}", id=f"tab-{g.id}")
                await tabs.mount(t)
                t.active = (self.current_group_id == g.id)
    
    def _get_current_tasks(self) -> list[Task]:
        if self.current_group_id == self.GENERAL_GROUP_ID:
            tasks = list(self.tasks)
        elif self.current_group_id is None:
            tasks = [t for t in self.tasks if t.group_id is None]
        else:
            tasks = [t for t in self.tasks if t.group_id == self.current_group_id]
        
        if self.filter_dates:
            filtered = []
            for t in tasks:
                for filter_date in self.filter_dates:
                    if filter_date == "none" and t.due_date is None:
                        filtered.append(t)
                        break
                    elif t.due_date == filter_date:
                        filtered.append(t)
                        break
            tasks = filtered
        
        if self.filter_tag_ids:
            tasks = [t for t in tasks if all(tag_id in t.tags for tag_id in self.filter_tag_ids)]
        
        if self.filter_statuses:
            filtered = []
            for t in tasks:
                st = getattr(t, "status", "Completado" if t.done else "En progreso")
                for status in self.filter_statuses:
                    if (status == "completed" and (t.done or st == "Completado")) or \
                       (status == "in_progress" and (not t.done and st == "En progreso")) or \
                       (status == "on_hold" and (not t.done and st == "En espera")) or \
                       (status == "pending" and not t.done):
                        filtered.append(t)
                        break
            tasks = filtered
        
        if self.filter_priorities:
            tasks = [t for t in tasks if t.priority in self.filter_priorities]
        
        if self.main_search_query:
            q = self.main_search_query.lower()
            tasks = [t for t in tasks if q in t.text.lower()]
        
        return tasks
    
    def _get_tasks_for_date(self, y: int, m: int, d: int) -> tuple[list[tuple], list[tuple]]:
        date_str = f"{y:04d}-{m:02d}-{d:02d}"
        
        tasks_result = []
        subtasks_result = []
        
        for t in self.tasks:
            if t.due_date == date_str:
                if t.group_id is None:
                    gname = "Sin grupo"
                else:
                    g = next((x for x in self.groups if x.id == t.group_id), None)
                    gname = g.name if g else "Sin grupo"
                tasks_result.append((t, gname))
            
            for subtask in t.subtasks:
                if subtask.due_date == date_str:
                    if t.group_id is None:
                        gname = "Sin grupo"
                    else:
                        g = next((x for x in self.groups if x.id == t.group_id), None)
                        gname = g.name if g else "Sin grupo"
                    subtasks_result.append((subtask, t, gname))
        
        return tasks_result, subtasks_result
    
    async def refresh_view(self) -> None:
        task_list = self.query_one("#task-list", Container)
        calendar_view = self.query_one("#calendar-view", Container)

        try:
            search_container = self.query_one("#main-search-container", Container)
            if self.calendar_mode:
                search_container.add_class("hidden")
            else:
                search_container.remove_class("hidden")
        except:
            pass

        if self.calendar_mode:
            task_list.styles.display = "none"
            calendar_view.add_class("visible")
            calendar_view.styles.display = "block"
            self.refresh_calendar()
        else:
            task_list.styles.display = "block"
            calendar_view.remove_class("visible")
            calendar_view.styles.display = "none"
            await task_list.remove_children()
            if self.current_group_id == self.GENERAL_GROUP_ID:
                await self._refresh_general_view(task_list)
            elif self.current_group_id == self.SUBTASKS_GROUP_ID:
                await self._refresh_subtasks_list(task_list)
            elif self.current_group_id == self.NOTES_GROUP_ID:
                await self._refresh_notes_list(task_list)
            elif self.current_group_id == self.CANVAS_GROUP_ID:
                await self._refresh_canvas_list(task_list)
            elif self.current_group_id == self.AUDIO_GROUP_ID:
                await self._refresh_voice_notes_list(task_list)
            elif self.current_group_id == self.TAGS_GROUP_ID:
                await self._refresh_tags_list(task_list)
            else:
                await self._refresh_task_list(task_list)

    def _get_ordered_subtasks(self, subtask_items: list[tuple[Task, Subtask]] = None) -> list[tuple[Task, Subtask]]:
        if subtask_items is None:
            subtask_items = self._get_filtered_all_subtasks()
        in_progress = [item for item in subtask_items if not item[1].done and getattr(item[1], 'status', 'En progreso') == 'En progreso']
        on_hold = [item for item in subtask_items if not item[1].done and getattr(item[1], 'status', 'En progreso') == 'En espera']
        completed = [item for item in subtask_items if item[1].done or getattr(item[1], 'status', 'En progreso') == 'Completado']
        return in_progress + on_hold + completed

    async def _refresh_subtasks_list(self, task_list: Container) -> None:
        subtask_items = self._get_filtered_all_subtasks()

        if not subtask_items:
            msg = "No hay subtareas. Pulsa 'a' para añadir una subtarea a una tarea."
            await task_list.mount(Label(msg, id="empty-message"))
        else:
            in_progress = [item for item in subtask_items if not item[1].done and getattr(item[1], 'status', 'En progreso') == 'En progreso']
            on_hold = [item for item in subtask_items if not item[1].done and getattr(item[1], 'status', 'En progreso') == 'En espera']
            completed = [item for item in subtask_items if item[1].done or getattr(item[1], 'status', 'En progreso') == 'Completado']

            if in_progress:
                await task_list.mount(Static("── En progreso ──", id="in-progress-separator-subtasks"))
                for (task, subtask) in in_progress:
                    idx = subtask_items.index((task, subtask))
                    item_widget = SubtaskRowWidget(subtask, parent_task=task, all_tags=self.tags, id=f"subtask-row-{idx}")
                    await task_list.mount(item_widget)

            if on_hold:
                await task_list.mount(Static("── En espera ──", id="on-hold-separator-subtasks"))
                for (task, subtask) in on_hold:
                    idx = subtask_items.index((task, subtask))
                    item_widget = SubtaskRowWidget(subtask, parent_task=task, all_tags=self.tags, id=f"subtask-row-{idx}")
                    await task_list.mount(item_widget)

            if completed:
                await task_list.mount(Static("── Completadas ──", id="completed-separator"))
                for (task, subtask) in completed:
                    idx = subtask_items.index((task, subtask))
                    item_widget = SubtaskRowWidget(subtask, parent_task=task, all_tags=self.tags, id=f"subtask-row-{idx}")
                    await task_list.mount(item_widget)

        self._update_selection_subtasks(subtask_items)

    def _get_filtered_all_subtasks(self) -> list[tuple[Task, Subtask]]:
        results = []
        for task in self.tasks:
            for subtask in task.subtasks:
                results.append((task, subtask))

        if self.filter_statuses:
            if "done" in self.filter_statuses and "pending" not in self.filter_statuses:
                results = [item for item in results if item[1].done]
            elif "pending" in self.filter_statuses and "done" not in self.filter_statuses:
                results = [item for item in results if not item[1].done]

        if self.filter_tag_ids:
            results = [item for item in results if item[1].tags and any(t_id in item[1].tags for t_id in self.filter_tag_ids)]

        if self.filter_priorities:
            results = [item for item in results if item[1].priority in self.filter_priorities]

        if self.filter_dates:
            results = [item for item in results if item[1].due_date in self.filter_dates]

        if self.main_search_query:
            q = self.main_search_query.lower()
            results = [item for item in results if q in item[1].text.lower() or q in item[0].text.lower()]

        return results

    def _update_selection_subtasks(self, subtask_items: list = None) -> None:
        if subtask_items is None:
            subtask_items = self._get_filtered_all_subtasks()
        ordered = self._get_ordered_subtasks(subtask_items)
        if not ordered:
            return

        if self.selected_index >= len(ordered):
            self.selected_index = len(ordered) - 1
        if self.selected_index < 0:
            self.selected_index = 0

        for idx, (task, subtask) in enumerate(ordered):
            try:
                orig_idx = subtask_items.index((task, subtask))
                widget = self.query_one(f"#subtask-row-{orig_idx}", SubtaskRowWidget)
                is_sel = (idx == self.selected_index)
                widget.selected = is_sel
                if is_sel:
                    widget.scroll_visible()
            except Exception:
                pass

    async def _refresh_voice_notes_list(self, task_list: Container) -> None:
        filtered_vn = self._get_filtered_voice_notes()

        if not filtered_vn:
            msg = "No hay notas de voz. Pulsa 'a' para añadir/grabar una."
            await task_list.mount(Label(msg, id="empty-message"))
        else:
            seen_ids = set()
            for vn in filtered_vn:
                if vn.id in seen_ids:
                    vn.id = max([v.id for v in self.voice_notes], default=0) + 1
                    self.next_voice_note_id = max(self.next_voice_note_id, vn.id + 1)
                seen_ids.add(vn.id)
                w = VoiceNoteWidget(vn, all_tags=self.tags, id=f"vn-{vn.id}")
                await task_list.mount(w)

        self._update_selection_voice_notes(filtered_vn)

    def _get_filtered_voice_notes(self) -> list[VoiceNote]:
        vn_list = list(self.voice_notes)

        if self.filter_tag_ids:
            vn_list = [v for v in vn_list if any(tag_id in v.tags for tag_id in self.filter_tag_ids)]

        if self.main_search_query:
            q = self.main_search_query.lower()
            vn_list = [v for v in vn_list if q in v.title.lower() or q in v.description.lower()]

        vn_list.sort(key=lambda v: v.created_at, reverse=True)
        return vn_list

    def _update_selection_voice_notes(self, vn_list: list) -> None:
        if not vn_list:
            return

        if self.selected_index >= len(vn_list):
            self.selected_index = len(vn_list) - 1
        if self.selected_index < 0:
            self.selected_index = 0

        for idx, vn in enumerate(vn_list):
            try:
                widget = self.query_one(f"#vn-{vn.id}", VoiceNoteWidget)
                is_sel = (idx == self.selected_index)
                widget.selected = is_sel
                if is_sel:
                    widget.scroll_visible()
            except Exception:
                pass
    
    async def _refresh_task_list(self, task_list: Container) -> None:
        ordered = self._get_ordered_tasks()
        seen_ids = set()
        for t in ordered:
            if t.id in seen_ids:
                t.id = max([tk.id for tk in self.tasks], default=0) + 1
                self.next_task_id = max(self.next_task_id, t.id + 1)
            seen_ids.add(t.id)

        in_progress = [t for t in ordered if not t.done and getattr(t, 'status', 'En progreso') == 'En progreso']
        on_hold = [t for t in ordered if not t.done and getattr(t, 'status', 'En progreso') == 'En espera']
        completed = [t for t in ordered if t.done or getattr(t, 'status', 'En progreso') == 'Completado']
        
        if not ordered:
            msg = "No hay tareas. Pulsa 'a' para añadir una."
            await task_list.mount(Label(msg, id="empty-message"))
        else:
            if in_progress:
                await task_list.mount(Static("── En progreso ──", id="in-progress-separator"))
                for t in in_progress:
                    w = TaskWidget(t, all_tags=self.tags, all_groups=self.groups, id=f"task-{t.id}")
                    await task_list.mount(w)
            if on_hold:
                await task_list.mount(Static("── En espera ──", id="on-hold-separator"))
                for t in on_hold:
                    w = TaskWidget(t, all_tags=self.tags, all_groups=self.groups, id=f"task-{t.id}")
                    await task_list.mount(w)
            if completed:
                await task_list.mount(Static("── Completadas ──", id="completed-separator"))
                for t in completed:
                    w = TaskWidget(t, all_tags=self.tags, all_groups=self.groups, id=f"task-{t.id}")
                    await task_list.mount(w)
        
        self._update_selection(in_progress + on_hold + completed)

    async def _refresh_notes_list(self, task_list: Container) -> None:
        filtered_notes = self._get_filtered_notes()

        if not filtered_notes:
            msg = "No hay notas. Pulsa 'a' para añadir una."
            await task_list.mount(Label(msg, id="empty-message"))
        else:
            seen_ids = set()
            for note in filtered_notes:
                if note.id in seen_ids:
                    note.id = max([n.id for n in self.notes], default=0) + 1
                    self.next_note_id = max(self.next_note_id, note.id + 1)
                seen_ids.add(note.id)
                w = NoteWidget(note, all_tags=self.tags, id=f"note-{note.id}")
                await task_list.mount(w)

        self._update_selection_notes(filtered_notes)

    def _get_filtered_notes(self) -> list[Note]:
        notes = list(self.notes)

        if self.filter_tag_ids:
            notes = [n for n in notes if any(tag_id in n.tags for tag_id in self.filter_tag_ids)]

        if self.main_search_query:
            q = self.main_search_query.lower()
            notes = [n for n in notes if q in n.title.lower() or q in n.description.lower()]

        notes.sort(key=lambda n: n.created_at, reverse=True)
        return notes

    def _update_selection_notes(self, notes: list) -> None:
        if not notes:
            return

        if self.selected_index >= len(notes):
            self.selected_index = len(notes) - 1
        if self.selected_index < 0:
            self.selected_index = 0

        for idx, note in enumerate(notes):
            try:
                widget = self.query_one(f"#note-{note.id}", NoteWidget)
                is_sel = (idx == self.selected_index)
                widget.selected = is_sel
                if is_sel:
                    widget.scroll_visible()
            except Exception:
                pass

    async def _refresh_canvas_list(self, task_list: Container) -> None:
        filtered_canvas = self._get_filtered_canvas()

        if not filtered_canvas:
            msg = "No hay pizarras. Pulsa 'a' para añadir una."
            await task_list.mount(Label(msg, id="empty-message"))
        else:
            seen_ids = set()
            for canvas in filtered_canvas:
                if canvas.id in seen_ids:
                    canvas.id = max([c.id for c in self.canvas_list], default=0) + 1
                    self.next_canvas_id = max(self.next_canvas_id, canvas.id + 1)
                seen_ids.add(canvas.id)
                w = CanvasWidget(canvas, all_tags=self.tags, id=f"canvas-{canvas.id}")
                await task_list.mount(w)

        self._update_selection_canvas(filtered_canvas)

    def _get_filtered_canvas(self) -> list[Canvas]:
        canvas_list = list(self.canvas_list)
        if self.filter_tag_ids:
            canvas_list = [c for c in canvas_list if any(tag_id in c.tags for tag_id in self.filter_tag_ids)]
        if self.main_search_query:
            q = self.main_search_query.lower()
            canvas_list = [c for c in canvas_list if q in c.title.lower()]
        canvas_list.sort(key=lambda c: c.created_at, reverse=True)
        return canvas_list

    def _update_selection_canvas(self, canvas_list: list) -> None:
        if not canvas_list:
            return

        if self.selected_index >= len(canvas_list):
            self.selected_index = len(canvas_list) - 1
        if self.selected_index < 0:
            self.selected_index = 0

        for idx, canvas in enumerate(canvas_list):
            try:
                widget = self.query_one(f"#canvas-{canvas.id}", CanvasWidget)
                is_sel = (idx == self.selected_index)
                widget.selected = is_sel
                if is_sel:
                    widget.scroll_visible()
            except Exception:
                pass

    def refresh_calendar(self) -> None:
        self.query_one("#calendar-header", Static).update(f"{MESES[self.cal_month]} {self.cal_year}")
        
        cal = calendar.Calendar(firstweekday=0)
        today = date.today()
        lines = ["  ".join(DIAS_SEMANA), "─" * 26]
        
        for week in cal.monthdayscalendar(self.cal_year, self.cal_month):
            week_str = ""
            for day in week:
                if day == 0:
                    week_str += "    "
                else:
                    current = date(self.cal_year, self.cal_month, day)
                    date_str = current.strftime("%Y-%m-%d")
                    
                    has_tasks = any(t.due_date == date_str for t in self.tasks)
                    has_subtasks = any(
                        any(st.due_date == date_str for st in t.subtasks)
                        for t in self.tasks
                    )
                    
                    if day == self.cal_day:
                        week_str += f"[bold cyan][{day:2d}][/bold cyan]"
                    elif current == today:
                        if has_tasks and has_subtasks:
                            week_str += f"[bold #D2B48C]•{day:2d} [/bold #D2B48C]"
                        elif has_subtasks:
                            week_str += f"[bold #FFA500]•{day:2d} [/bold #FFA500]"
                        elif has_tasks:
                            week_str += f"[bold green]•{day:2d} [/bold green]"
                        else:
                            week_str += f"[bold green] {day:2d} [/bold green]"
                    else:
                        if has_tasks and has_subtasks:
                            week_str += f"[#D2B48C]•{day:2d} [/#D2B48C]"
                        elif has_subtasks:
                            week_str += f"[#FFA500]•{day:2d} [/#FFA500]"
                        elif has_tasks:
                            week_str += f"[yellow]•{day:2d} [/yellow]"
                        else:
                            week_str += f" {day:2d} "
            lines.append(week_str)
        
        lines.append("")
        lines.append("[bold green]●[/bold green] Hoy  [yellow]●[/yellow] Tareas  [#FFA500]●[/#FFA500] Subtareas  [#D2B48C]●[/#D2B48C] Ambas")
        
        self.query_one("#calendar-display", Static).update("\n".join(lines))
        
        tasks, subtasks = self._get_tasks_for_date(self.cal_year, self.cal_month, self.cal_day)
        day_tasks = self.query_one("#calendar-day-tasks", Static)
        
        total_items = len(tasks) + len(subtasks)
        
        if total_items > 0:
            lines = [f"📋 {len(tasks)} tarea(s) | 📝 {len(subtasks)} subtarea(s):"]
            
            for t, gname in tasks[:2]:
                cb = "☑" if t.done else "☐"
                txt = t.text[:30] + "..." if len(t.text) > 30 else t.text
                group_text = f"📁 {gname}"
                padding = " " * max(1, 45 - len(txt) - len(group_text))
                lines.append(f"  {cb} {txt}{padding}{group_text}")
            
            for st, parent, gname in subtasks[:2]:
                cb = "☑" if st.done else "☐"
                txt = st.text[:25] + "..." if len(st.text) > 25 else st.text
                parent_txt = parent.text[:15] + "..." if len(parent.text) > 15 else parent.text
                lines.append(f"  {cb} ↳ {txt} 🔗 {parent_txt}")
            
            if total_items > 4:
                lines.append(f"  ... y {total_items - 4} más")
            
            day_tasks.update("\n".join(lines))
        else:
            day_tasks.update("No hay tareas ni subtareas para este día")
    
    def _update_selection(self, all_tasks: list = None, completed: list = None) -> None:
        if all_tasks is None:
            all_tasks = self._get_ordered_tasks()
        elif completed is not None:
            all_tasks = all_tasks + completed
        if not all_tasks:
            self.selected_index = 0
            return
        self.selected_index = max(0, min(self.selected_index, len(all_tasks) - 1))
        for i, t in enumerate(all_tasks):
            try:
                w = self.query_one(f"#task-{t.id}", TaskWidget)
                w.selected = (i == self.selected_index)
            except: pass
    
    def _get_ordered_tasks(self) -> list:
        c = self._get_current_tasks()
        in_progress = [t for t in c if not t.done and getattr(t, 'status', 'En progreso') == 'En progreso']
        on_hold = [t for t in c if not t.done and getattr(t, 'status', 'En progreso') == 'En espera']
        completed = [t for t in c if t.done or getattr(t, 'status', 'En progreso') == 'Completado']
        
        alpha_criterion = self.sort_criteria.get("alphabetical")
        if alpha_criterion == "alpha_asc":
            in_progress.sort(key=lambda t: t.text.lower())
            on_hold.sort(key=lambda t: t.text.lower())
            completed.sort(key=lambda t: t.text.lower())
        elif alpha_criterion == "alpha_desc":
            in_progress.sort(key=lambda t: t.text.lower(), reverse=True)
            on_hold.sort(key=lambda t: t.text.lower(), reverse=True)
            completed.sort(key=lambda t: t.text.lower(), reverse=True)
        
        date_criterion = self.sort_criteria.get("date")
        if date_criterion == "date_asc":
            def sort_date_asc(lst):
                w = [t for t in lst if t.due_date]
                wo = [t for t in lst if not t.due_date]
                w.sort(key=lambda t: t.due_date)
                return w + wo
            in_progress = sort_date_asc(in_progress)
            on_hold = sort_date_asc(on_hold)
            completed = sort_date_asc(completed)
        elif date_criterion == "date_desc":
            def sort_date_desc(lst):
                w = [t for t in lst if t.due_date]
                wo = [t for t in lst if not t.due_date]
                w.sort(key=lambda t: t.due_date, reverse=True)
                return w + wo
            in_progress = sort_date_desc(in_progress)
            on_hold = sort_date_desc(on_hold)
            completed = sort_date_desc(completed)
        
        priority_criterion = self.sort_criteria.get("priority")
        if priority_criterion == "priority_desc":
            in_progress.sort(key=lambda t: t.priority, reverse=True)
            on_hold.sort(key=lambda t: t.priority, reverse=True)
            completed.sort(key=lambda t: t.priority, reverse=True)
        elif priority_criterion == "priority_asc":
            in_progress.sort(key=lambda t: t.priority)
            on_hold.sort(key=lambda t: t.priority)
            completed.sort(key=lambda t: t.priority)
        
        return in_progress + on_hold + completed
    
    def update_selection(self) -> None:
        ordered = self._get_ordered_tasks()
        if not ordered:
            self.selected_index = 0
            return
        self.selected_index = max(0, min(self.selected_index, len(ordered) - 1))
        for i, t in enumerate(ordered):
            try:
                widget = self.query_one(f"#task-{t.id}", TaskWidget)
                widget.selected = (i == self.selected_index)
                if i == self.selected_index:
                    widget.scroll_visible()
            except: pass
    
    def update_stats(self) -> None:
        if self.calendar_mode:
            tasks, subtasks = self._get_tasks_for_date(self.cal_year, self.cal_month, self.cal_day)
            total_tasks = len(tasks)
            total_subtasks = len(subtasks)
            done_tasks = sum(1 for t, _ in tasks if t.done)
            done_subtasks = sum(1 for st, _, _ in subtasks if st.done)
            text = f"📅 {self.cal_day}/{self.cal_month}/{self.cal_year} | Tareas: {total_tasks} ({done_tasks} ✓) | Subtareas: {total_subtasks} ({done_subtasks} ✓)"
        elif self.current_group_id == self.NOTES_GROUP_ID:
            notes = self._get_filtered_notes()
            total = len(notes)
            with_links = sum(1 for n in notes if n.url)
            with_images = sum(1 for n in notes if n.image_path)
            with_files = sum(1 for n in notes if n.file_path)

            text = f"Total: {total} notas | 🔗 {with_links} | 📷 {with_images} | 📎 {with_files} | Grupo: Notas"

            if self.filter_tag_ids:
                tag_names = []
                for tag_id in self.filter_tag_ids:
                    tag = next((t for t in self.tags if t.id == tag_id), None)
                    if tag:
                        tag_names.append(tag.name)
                if tag_names:
                    text += f" | Filtro: {', '.join(tag_names)}"
        elif self.current_group_id == self.CANVAS_GROUP_ID:
            canvas_list = self._get_filtered_canvas()
            total = len(canvas_list)
            text = f"Total: {total} pizarras | Grupo: Pizarra"
        elif self.current_group_id == self.AUDIO_GROUP_ID:
            vns = self._get_filtered_voice_notes()
            total = len(vns)
            total_sec = sum(v.duration for v in vns)
            mins, secs = divmod(int(total_sec), 60)
            text = f"Total: {total} notas de voz | Duración total: {mins:02d}:{secs:02d} | Grupo: Notas de voz"

            if self.filter_tag_ids:
                tag_names = [t.name for tid in self.filter_tag_ids for t in self.tags if t.id == tid]
                if tag_names:
                    text += f" | Filtro: {', '.join(tag_names)}"
        else:
            c = self._get_current_tasks()
            total, done = len(c), sum(1 for t in c if t.done)

            if self.current_group_id == self.GENERAL_GROUP_ID:
                gname = "General"
            elif self.current_group_id is None:
                gname = "Sin grupo"
            else:
                g = next((x for x in self.groups if x.id == self.current_group_id), None)
                gname = g.name if g else "Sin grupo"

            text = f"Total: {total} | Completadas: {done} | Pendientes: {total - done} | Grupo: {gname}"
            
            sort_parts = []
            sort_names = {
                "alpha_asc": "A→Z",
                "alpha_desc": "Z→A",
                "date_asc": "Fecha↑",
                "date_desc": "Fecha↓",
                "priority_desc": "Pri↓",
                "priority_asc": "Pri↑"
            }
            
            if self.sort_criteria.get("priority"):
                sort_parts.append(sort_names.get(self.sort_criteria["priority"], ""))
            if self.sort_criteria.get("date"):
                sort_parts.append(sort_names.get(self.sort_criteria["date"], ""))
            if self.sort_criteria.get("alphabetical"):
                sort_parts.append(sort_names.get(self.sort_criteria["alphabetical"], ""))
            
            if sort_parts:
                text += f" | Orden: {' → '.join(sort_parts)}"
            else:
                text += " | Orden: Creación"
            
            filters = []
            
            if self.filter_dates:
                date_strs = []
                for fd in self.filter_dates:
                    if fd == "none":
                        date_strs.append("Sin fecha")
                    else:
                        try:
                            d = datetime.strptime(fd, "%Y-%m-%d")
                            date_strs.append(f"{d.day:02d}/{d.month:02d}")
                        except: pass
                if date_strs:
                    filters.append(f"📅 {', '.join(date_strs)}")
            
            if self.filter_tag_ids:
                tag_names = []
                for tag_id in self.filter_tag_ids:
                    tag = next((t for t in self.tags if t.id == tag_id), None)
                    if tag:
                        tag_names.append(tag.name)
                if tag_names:
                    filters.append(f"🏷️ {', '.join(tag_names)}")
            
            if self.filter_statuses:
                status_names = []
                for status in self.filter_statuses:
                    if status == "completed":
                        status_names.append("Completadas")
                    elif status == "in_progress":
                        status_names.append("En progreso")
                    elif status == "on_hold":
                        status_names.append("En espera")
                    elif status == "pending":
                        status_names.append("Pendientes")
                if status_names:
                    filters.append(f"✅ {', '.join(status_names)}")
            
            if self.filter_priorities:
                priority_names = {0: "Sin prioridad", 1: "■ Baja", 2: "■ Media", 3: "■ Alta"}
                priority_strs = [priority_names.get(p, '') for p in self.filter_priorities]
                if priority_strs:
                    filters.append(f"⭐ {', '.join(priority_strs)}")
            
            if filters:
                text += " | Filtros: " + ", ".join(filters)

        if self.main_search_query:
            text += f" | 🔍 '{self.main_search_query}'"

        self.query_one("#stats", Static).update(text)

        self.query_one("#stats", Static).update(text)
    
    def get_selected_widget(self) -> Optional[TaskWidget]:
        ordered = self._get_ordered_tasks()
        if not ordered or self.selected_index >= len(ordered): return None
        try: return self.query_one(f"#task-{ordered[self.selected_index].id}", TaskWidget)
        except: return None
    
    def action_quit(self) -> None:
        if self.main_search_focused: return
        self.save_data()
        self.exit()
    
    async def action_handle_escape(self) -> None:
        if self.main_search_focused:
            self._clear_main_search()
            return
        if self.calendar_mode:
            self.calendar_mode = False
            await self.refresh_tabs()
            await self.refresh_view()
            self.update_stats()
    
    async def action_nav_left(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            d = date(self.cal_year, self.cal_month, self.cal_day) - timedelta(days=1)
            self.cal_year, self.cal_month, self.cal_day = d.year, d.month, d.day
            self.refresh_calendar()
            self.update_stats()
        else:
            await self._prev_group()
    
    async def action_nav_right(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            d = date(self.cal_year, self.cal_month, self.cal_day) + timedelta(days=1)
            self.cal_year, self.cal_month, self.cal_day = d.year, d.month, d.day
            self.refresh_calendar()
            self.update_stats()
        else:
            await self._next_group()
    
    async def action_nav_up(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            d = date(self.cal_year, self.cal_month, self.cal_day) - timedelta(days=7)
            self.cal_year, self.cal_month, self.cal_day = d.year, d.month, d.day
            self.refresh_calendar()
            self.update_stats()
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            items = self._get_general_items_list()
            if items:
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self._update_selection_general(items)
                else:
                    try:
                        self.query_one("#task-list", Container).scroll_home()
                    except Exception:
                        pass
            else:
                try:
                    self.query_one("#task-list", Container).scroll_up()
                except Exception:
                    pass
        elif self.current_group_id == self.SUBTASKS_GROUP_ID:
            ordered = self._get_ordered_subtasks()
            if ordered and self.selected_index > 0:
                self.selected_index -= 1
                self._update_selection_subtasks()
        elif self.current_group_id == self.NOTES_GROUP_ID:
            notes = self._get_filtered_notes()
            if notes and self.selected_index > 0:
                self.selected_index -= 1
                self._update_selection_notes(notes)
        elif self.current_group_id == self.CANVAS_GROUP_ID:
            canvas_list = self._get_filtered_canvas()
            if canvas_list and self.selected_index > 0:
                self.selected_index -= 1
                self._update_selection_canvas(canvas_list)
        elif self.current_group_id == self.AUDIO_GROUP_ID:
            vn_list = self._get_filtered_voice_notes()
            if vn_list and self.selected_index > 0:
                self.selected_index -= 1
                self._update_selection_voice_notes(vn_list)
        else:
            ordered = self._get_ordered_tasks()
            if ordered and self.selected_index > 0:
                self.selected_index -= 1
                self._update_selection(ordered)
    
    async def action_nav_down(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            d = date(self.cal_year, self.cal_month, self.cal_day) + timedelta(days=7)
            self.cal_year, self.cal_month, self.cal_day = d.year, d.month, d.day
            self.refresh_calendar()
            self.update_stats()
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            items = self._get_general_items_list()
            if items:
                if self.selected_index < len(items) - 1:
                    self.selected_index += 1
                    self._update_selection_general(items)
                else:
                    try:
                        self.query_one("#task-list", Container).scroll_end()
                    except Exception:
                        pass
            else:
                try:
                    self.query_one("#task-list", Container).scroll_down()
                except Exception:
                    pass
        elif self.current_group_id == self.TAGS_GROUP_ID:
            tags = self._get_filtered_tags()
            if tags:
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self._update_selection_tags(tags)
                else:
                    try:
                        self.query_one("#task-list", Container).scroll_home()
                    except Exception:
                        pass
            else:
                try:
                    self.query_one("#task-list", Container).scroll_up()
                except Exception:
                    pass
        elif self.current_group_id == self.SUBTASKS_GROUP_ID:
            ordered = self._get_ordered_subtasks()
            if ordered and self.selected_index < len(ordered) - 1:
                self.selected_index += 1
                self._update_selection_subtasks()
        elif self.current_group_id == self.NOTES_GROUP_ID:
            notes = self._get_filtered_notes()
            if notes and self.selected_index < len(notes) - 1:
                self.selected_index += 1
                self._update_selection_notes(notes)
        elif self.current_group_id == self.CANVAS_GROUP_ID:
            canvas_list = self._get_filtered_canvas()
            if canvas_list and self.selected_index < len(canvas_list) - 1:
                self.selected_index += 1
                self._update_selection_canvas(canvas_list)
        elif self.current_group_id == self.AUDIO_GROUP_ID:
            vn_list = self._get_filtered_voice_notes()
            if vn_list and self.selected_index < len(vn_list) - 1:
                self.selected_index += 1
                self._update_selection_voice_notes(vn_list)
        else:
            ordered = self._get_ordered_tasks()
            if ordered and self.selected_index < len(ordered) - 1:
                self.selected_index += 1
                self._update_selection(ordered)

    async def _refresh_general_view(self, task_list: Container) -> None:
        items = []

        # 1. Tareas
        await task_list.mount(Static("── 📋 TAREAS ──", classes="section-separator-main"))
        ordered_tasks = self._get_ordered_tasks()
        in_prog_tasks = [t for t in ordered_tasks if not t.done and getattr(t, 'status', 'En progreso') == 'En progreso']
        on_hold_tasks = [t for t in ordered_tasks if not t.done and getattr(t, 'status', 'En progreso') == 'En espera']
        completed_tasks = [t for t in ordered_tasks if t.done or getattr(t, 'status', 'En progreso') == 'Completado']

        if not ordered_tasks:
            await task_list.mount(Label(" (Sin tareas) ", classes="empty-section-label"))
        else:
            if in_prog_tasks:
                await task_list.mount(Static("── En progreso ──", id="in-progress-separator"))
                for t in in_prog_tasks:
                    w_id = f"task-{t.id}"
                    w = TaskWidget(t, all_tags=self.tags, all_groups=self.groups, id=w_id)
                    await task_list.mount(w)
                    items.append(("task", t, w_id))
            if on_hold_tasks:
                await task_list.mount(Static("── En espera ──", id="on-hold-separator"))
                for t in on_hold_tasks:
                    w_id = f"task-{t.id}"
                    w = TaskWidget(t, all_tags=self.tags, all_groups=self.groups, id=w_id)
                    await task_list.mount(w)
                    items.append(("task", t, w_id))
            if completed_tasks:
                await task_list.mount(Static("── Completadas ──", id="completed-separator"))
                for t in completed_tasks:
                    w_id = f"task-{t.id}"
                    w = TaskWidget(t, all_tags=self.tags, all_groups=self.groups, id=w_id)
                    await task_list.mount(w)
                    items.append(("task", t, w_id))

        # 2. Subtareas
        await task_list.mount(Static("── 📋 SUBTAREAS ──", classes="section-separator-main"))
        filtered_subtasks = self._get_filtered_all_subtasks()
        if not filtered_subtasks:
            await task_list.mount(Label(" (Sin subtareas) ", classes="empty-section-label"))
        else:
            in_prog_sub = [s for s in filtered_subtasks if not s[1].done and getattr(s[1], 'status', 'En progreso') == 'En progreso']
            on_hold_sub = [s for s in filtered_subtasks if not s[1].done and getattr(s[1], 'status', 'En progreso') == 'En espera']
            completed_sub = [s for s in filtered_subtasks if s[1].done or getattr(s[1], 'status', 'En progreso') == 'Completado']

            if in_prog_sub:
                await task_list.mount(Static("── En progreso ──", id="in-progress-separator-subtasks"))
                for parent_task, subtask in in_prog_sub:
                    s_idx = filtered_subtasks.index((parent_task, subtask))
                    w_id = f"general-subtask-{s_idx}"
                    w = SubtaskRowWidget(subtask, parent_task=parent_task, all_tags=self.tags, id=w_id)
                    await task_list.mount(w)
                    items.append(("subtask", subtask, w_id))

            if on_hold_sub:
                await task_list.mount(Static("── En espera ──", id="on-hold-separator-subtasks"))
                for parent_task, subtask in on_hold_sub:
                    s_idx = filtered_subtasks.index((parent_task, subtask))
                    w_id = f"general-subtask-{s_idx}"
                    w = SubtaskRowWidget(subtask, parent_task=parent_task, all_tags=self.tags, id=w_id)
                    await task_list.mount(w)
                    items.append(("subtask", subtask, w_id))

            if completed_sub:
                await task_list.mount(Static("── Completadas ──", id="completed-separator-subtasks"))
                for parent_task, subtask in completed_sub:
                    s_idx = filtered_subtasks.index((parent_task, subtask))
                    w_id = f"general-subtask-{s_idx}"
                    w = SubtaskRowWidget(subtask, parent_task=parent_task, all_tags=self.tags, id=w_id)
                    await task_list.mount(w)
                    items.append(("subtask", subtask, w_id))

        # 3. Notas
        await task_list.mount(Static("── 📝 NOTAS ──", classes="section-separator-main"))
        filtered_notes = self._get_filtered_notes()
        if not filtered_notes:
            await task_list.mount(Label(" (Sin notas) ", classes="empty-section-label"))
        else:
            seen_ids = set()
            for note in filtered_notes:
                if note.id in seen_ids:
                    note.id = max([n.id for n in self.notes], default=0) + 1
                    self.next_note_id = max(self.next_note_id, note.id + 1)
                seen_ids.add(note.id)
                w_id = f"note-{note.id}"
                w = NoteWidget(note, all_tags=self.tags, id=w_id)
                await task_list.mount(w)
                items.append(("note", note, w_id))

        # 4. Pizarras
        await task_list.mount(Static("── 🎨 PIZARRAS ──", classes="section-separator-main"))
        filtered_canvas = self._get_filtered_canvas()
        if not filtered_canvas:
            await task_list.mount(Label(" (Sin pizarras) ", classes="empty-section-label"))
        else:
            seen_ids = set()
            for canvas in filtered_canvas:
                if canvas.id in seen_ids:
                    canvas.id = max([c.id for c in self.canvas_list], default=0) + 1
                    self.next_canvas_id = max(self.next_canvas_id, canvas.id + 1)
                seen_ids.add(canvas.id)
                w_id = f"canvas-{canvas.id}"
                w = CanvasWidget(canvas, all_tags=self.tags, id=w_id)
                await task_list.mount(w)
                items.append(("canvas", canvas, w_id))

        # 5. Audios
        await task_list.mount(Static("── 🎤 AUDIOS ──", classes="section-separator-main"))
        filtered_vn = self._get_filtered_voice_notes()
        if not filtered_vn:
            await task_list.mount(Label(" (Sin audios) ", classes="empty-section-label"))
        else:
            seen_ids = set()
            for vn in filtered_vn:
                if vn.id in seen_ids:
                    vn.id = max([v.id for v in self.voice_notes], default=0) + 1
                    self.next_voice_note_id = max(self.next_voice_note_id, vn.id + 1)
                seen_ids.add(vn.id)
                w_id = f"vn-{vn.id}"
                w = VoiceNoteWidget(vn, all_tags=self.tags, id=w_id)
                await task_list.mount(w)
                items.append(("voice_note", vn, w_id))

        # 6. Etiquetas
        await task_list.mount(Static("── 🏷️ ETIQUETAS ──", classes="section-separator-main"))
        filtered_tags = self._get_filtered_tags()
        if not filtered_tags:
            await task_list.mount(Label(" (Sin etiquetas) ", classes="empty-section-label"))
        else:
            for tag in filtered_tags:
                count = sum(1 for t in self.tasks if tag.id in t.tags)
                w_id = f"tag-{tag.id}"
                w = TagWidget(tag, task_count=count, id=w_id)
                await task_list.mount(w)
                items.append(("tag", tag, w_id))

        self._update_selection_general(items)

    def _get_general_items_list(self) -> list:
        items = []
        ordered_tasks = self._get_ordered_tasks()
        pending = [t for t in ordered_tasks if not t.done]
        completed = [t for t in ordered_tasks if t.done]

        for t in pending:
            items.append(("task", t, f"task-{t.id}"))
        for t in completed:
            items.append(("task", t, f"task-{t.id}"))

        filtered_subtasks = self._get_filtered_all_subtasks()
        pending_subtasks = [s for s in filtered_subtasks if not s[1].done]
        completed_subtasks = [s for s in filtered_subtasks if s[1].done]

        for parent_task, subtask in pending_subtasks:
            s_idx = filtered_subtasks.index((parent_task, subtask))
            items.append(("subtask", subtask, f"general-subtask-{s_idx}"))
        for parent_task, subtask in completed_subtasks:
            s_idx = filtered_subtasks.index((parent_task, subtask))
            items.append(("subtask", subtask, f"general-subtask-{s_idx}"))

        for note in self._get_filtered_notes():
            items.append(("note", note, f"note-{note.id}"))

        for canvas in self._get_filtered_canvas():
            items.append(("canvas", canvas, f"canvas-{canvas.id}"))

        for vn in self._get_filtered_voice_notes():
            items.append(("voice_note", vn, f"vn-{vn.id}"))

        for tag in self._get_filtered_tags():
            items.append(("tag", tag, f"tag-{tag.id}"))

        return items

    def _get_selected_general_item(self) -> Optional[tuple[str, Any]]:
        items = self._get_general_items_list()
        if items and 0 <= self.selected_index < len(items):
            item_type, item_obj, _ = items[self.selected_index]
            return item_type, item_obj
        return None

    def _update_selection_general(self, items: list = None) -> None:
        if items is None:
            items = self._get_general_items_list()
        if not items:
            self.selected_index = 0
            return

        if self.selected_index >= len(items):
            self.selected_index = len(items) - 1
        if self.selected_index < 0:
            self.selected_index = 0

        for idx, (item_type, item_obj, widget_id) in enumerate(items):
            try:
                if item_type == "task":
                    w = self.query_one(f"#{widget_id}", TaskWidget)
                elif item_type == "subtask":
                    w = self.query_one(f"#{widget_id}", SubtaskRowWidget)
                elif item_type == "note":
                    w = self.query_one(f"#{widget_id}", NoteWidget)
                elif item_type == "canvas":
                    w = self.query_one(f"#{widget_id}", CanvasWidget)
                elif item_type == "voice_note":
                    w = self.query_one(f"#{widget_id}", VoiceNoteWidget)
                elif item_type == "tag":
                    w = self.query_one(f"#{widget_id}", TagWidget)
                else:
                    continue
                is_sel = (idx == self.selected_index)
                w.selected = is_sel
                if is_sel:
                    if idx == len(items) - 1:
                        self.query_one("#task-list", Container).scroll_end()
                    elif idx == 0:
                        self.query_one("#task-list", Container).scroll_home()
                    else:
                        w.scroll_visible()
            except Exception:
                pass

    def _select_tag_by_data(self, tag: Tag) -> None:
        if self.current_group_id == self.GENERAL_GROUP_ID:
            items = self._get_general_items_list()
            for idx, (itype, obj, _) in enumerate(items):
                if itype == "tag" and obj == tag:
                    self.selected_index = idx
                    self._update_selection_general(items)
                    break
            return
        tags = self._get_filtered_tags()
        if tag in tags:
            self.selected_index = tags.index(tag)
            self._update_selection_tags(tags)

    async def _refresh_tags_list(self, task_list: Container) -> None:
        filtered_tags = self._get_filtered_tags()

        if not filtered_tags:
            msg = "No hay etiquetas. Pulsa 'a' para añadir una."
            await task_list.mount(Label(msg, id="empty-message"))
        else:
            for tag in filtered_tags:
                count = sum(1 for t in self.tasks if tag.id in t.tags)
                w = TagWidget(tag, task_count=count, id=f"tag-{tag.id}")
                await task_list.mount(w)

        self._update_selection_tags(filtered_tags)

    def _get_filtered_tags(self) -> list[Tag]:
        tags = list(self.tags)
        if self.main_search_query:
            q = self.main_search_query.lower()
            tags = [t for t in tags if q in t.name.lower()]
        return tags

    def _update_selection_tags(self, tags: list = None) -> None:
        if tags is None:
            tags = self._get_filtered_tags()
        if not tags:
            return

        if self.selected_index >= len(tags):
            self.selected_index = len(tags) - 1
        if self.selected_index < 0:
            self.selected_index = 0

        for idx, tag in enumerate(tags):
            try:
                widget = self.query_one(f"#tag-{tag.id}", TagWidget)
                is_sel = (idx == self.selected_index)
                widget.selected = is_sel
                if is_sel:
                    widget.scroll_visible()
            except Exception:
                pass

    def _select_note_by_data(self, note: Note) -> None:
        if self.current_group_id == self.GENERAL_GROUP_ID:
            items = self._get_general_items_list()
            for idx, (itype, obj, _) in enumerate(items):
                if itype == "note" and obj == note:
                    self.selected_index = idx
                    self._update_selection_general(items)
                    break
            return
        notes = self._get_filtered_notes()
        if note in notes:
            self.selected_index = notes.index(note)
            self._update_selection_notes(notes)

    def _select_voice_note_by_data(self, vn: VoiceNote) -> None:
        if self.current_group_id == self.GENERAL_GROUP_ID:
            items = self._get_general_items_list()
            for idx, (itype, obj, _) in enumerate(items):
                if itype == "voice_note" and obj == vn:
                    self.selected_index = idx
                    self._update_selection_general(items)
                    break
            return
        vn_list = self._get_filtered_voice_notes()
        if vn in vn_list:
            self.selected_index = vn_list.index(vn)
            self._update_selection_voice_notes(vn_list)

    def _select_canvas_by_data(self, canvas: Canvas) -> None:
        if self.current_group_id == self.GENERAL_GROUP_ID:
            items = self._get_general_items_list()
            for idx, (itype, obj, _) in enumerate(items):
                if itype == "canvas" and obj == canvas:
                    self.selected_index = idx
                    self._update_selection_general(items)
                    break
            return
        canvas_list = self._get_filtered_canvas()
        if canvas in canvas_list:
            self.selected_index = canvas_list.index(canvas)
            self._update_selection_canvas(canvas_list)

    def _select_task_by_data(self, task: Task) -> None:
        if self.current_group_id == self.GENERAL_GROUP_ID:
            items = self._get_general_items_list()
            for idx, (itype, obj, _) in enumerate(items):
                if itype == "task" and obj == task:
                    self.selected_index = idx
                    self._update_selection_general(items)
                    break
            return
        ordered = self._get_ordered_tasks()
        if task in ordered:
            self.selected_index = ordered.index(task)
            pending = [t for t in ordered if not t.done]
            completed = [t for t in ordered if t.done]
            self._update_selection(pending, completed)
    
    def action_next_month(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            self.cal_month += 1
            if self.cal_month > 12:
                self.cal_month, self.cal_year = 1, self.cal_year + 1
            self.cal_day = min(self.cal_day, calendar.monthrange(self.cal_year, self.cal_month)[1])
            self.refresh_calendar()
            self.update_stats()
    
    def action_prev_month(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            self.cal_month -= 1
            if self.cal_month < 1:
                self.cal_month, self.cal_year = 12, self.cal_year - 1
            self.cal_day = min(self.cal_day, calendar.monthrange(self.cal_year, self.cal_month)[1])
            self.refresh_calendar()
            self.update_stats()
    
    def action_go_today(self) -> None:
        if self.calendar_mode:
            today = date.today()
            self.cal_year, self.cal_month, self.cal_day = today.year, today.month, today.day
            self.refresh_calendar()
            self.update_stats()
    
    async def _select_group_by_id(self, group_id: Optional[int]) -> None:
        self.calendar_mode = False
        self.current_group_id = group_id
        self.selected_index = 0
        self._clear_main_search()
        await self.refresh_tabs()
        await self.refresh_view()
        self.update_stats()

    async def _prev_group(self) -> None:
        ids = [self.GENERAL_GROUP_ID, None, self.SUBTASKS_GROUP_ID, self.NOTES_GROUP_ID, self.CANVAS_GROUP_ID, self.AUDIO_GROUP_ID, self.TAGS_GROUP_ID] + [g.id for g in self.groups]
        idx = (ids.index(self.current_group_id) - 1) % len(ids)
        await self._select_group_by_id(ids[idx])

    async def _next_group(self) -> None:
        ids = [self.GENERAL_GROUP_ID, None, self.SUBTASKS_GROUP_ID, self.NOTES_GROUP_ID, self.CANVAS_GROUP_ID, self.AUDIO_GROUP_ID, self.TAGS_GROUP_ID] + [g.id for g in self.groups]
        idx = (ids.index(self.current_group_id) + 1) % len(ids)
        await self._select_group_by_id(ids[idx])
        
    async def action_toggle_calendar(self) -> None:
        if self.main_search_focused: return
        self.calendar_mode = not self.calendar_mode
        if self.calendar_mode:
            today = date.today()
            self.cal_year, self.cal_month, self.cal_day = today.year, today.month, today.day
            self._clear_main_search()
        await self.refresh_tabs()
        await self.refresh_view()
        self.update_stats()
    
    def action_action_enter(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            tasks, subtasks = self._get_tasks_for_date(self.cal_year, self.cal_month, self.cal_day)
            date_str = f"{self.cal_day}/{self.cal_month}/{self.cal_year}"

            def on_result(result):
                if result:
                    item_type, item_obj = result
                    self._go_to_task(item_obj)

            self.push_screen(DayItemsModal(tasks, subtasks, date_str), on_result)
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item:
                itype, obj = item
                if itype == "note":
                    self.action_view_note(obj)
                elif itype == "canvas":
                    self.action_edit_canvas(obj)
                elif itype == "voice_note":
                    self.action_play_voice_note(obj)
                elif itype in ("task", "subtask"):
                    self.call_later(self.action_toggle_done)
        elif self.current_group_id == self.NOTES_GROUP_ID:
            self.action_view_note()
        elif self.current_group_id == self.CANVAS_GROUP_ID:
            self.action_edit_canvas()
        elif self.current_group_id == self.AUDIO_GROUP_ID:
            self.action_play_voice_note()
        else:
            self.action_toggle_done()
    
    async def action_toggle_done(self) -> None:
        if self.main_search_focused: return
        if not self.calendar_mode:
            if self.current_group_id == self.SUBTASKS_GROUP_ID:
                subtasks = self._get_ordered_subtasks()
                if subtasks and 0 <= self.selected_index < len(subtasks):
                    self._save_undo_state()
                    parent_task, subtask = subtasks[self.selected_index]
                    subtask.done = not subtask.done
                    self.save_data()
                    self.update_stats()
                    await self.refresh_view()
                return
            if self.current_group_id == self.GENERAL_GROUP_ID:
                item = self._get_selected_general_item()
                if item:
                    itype, obj = item
                    if itype in ("task", "subtask"):
                        self._save_undo_state()
                        obj.done = not obj.done
                        self.save_data()
                        self.update_stats()
                        await self.refresh_view()
                return
            w = self.get_selected_widget()
            if w:
                self._save_undo_state()
                w.toggle_done()
                self.save_data()
                self.update_stats()
                await self.refresh_view()
    
    def _go_to_task(self, task: Task) -> None:
        async def nav() -> None:
            self.calendar_mode = False
            self.current_group_id = task.group_id
            self.selected_index = 0
            await self.refresh_tabs()
            await self.refresh_view()
            self.update_stats()
            for i, t in enumerate(self._get_ordered_tasks()):
                if t.id == task.id:
                    self.selected_index = i
                    break
            self.update_selection()
        self.call_later(nav)
    
    def action_search(self) -> None:
        if self.current_group_id == self.NOTES_GROUP_ID:
            def on_input_notes(query: Optional[str]) -> None:
                if not query: return
                results = []
                for note in self.notes:
                    if (query.lower() in note.title.lower() or
                        query.lower() in note.description.lower()):
                        results.append(note)
                if not results:
                    self.notify(f"No se encontraron notas para '{query}'", severity="error", timeout=3)
                else:
                    self.filter_tag_ids = []
                    filtered = self._get_filtered_notes()
                    for idx, n in enumerate(filtered):
                        if n.id == results[0].id:
                            self.selected_index = idx
                            break
                    self.refresh_view()
                    self.notify(f"Encontradas {len(results)} nota(s)", severity="information", timeout=2)
            self.push_screen(InputModal("🔍 Buscar Notas", placeholder="Buscar en notas..."), on_input_notes)
            return

        if self.current_group_id == self.CANVAS_GROUP_ID:
            def on_input_canvas(query: Optional[str]) -> None:
                if not query: return
                results = []
                for canvas in self.canvas_list:
                    if query.lower() in canvas.title.lower():
                        results.append(canvas)
                if not results:
                    self.notify(f"No se encontraron pizarras para '{query}'", severity="error", timeout=3)
                else:
                    self.filter_tag_ids = []
                    filtered = self._get_filtered_canvas()
                    for idx, c in enumerate(filtered):
                        if c.id == results[0].id:
                            self.selected_index = idx
                            break
                    self.refresh_view()
                    self.notify(f"Encontradas {len(results)} pizarra(s)", severity="information", timeout=2)
            self.push_screen(InputModal("🔍 Buscar Pizarras", placeholder="Buscar en pizarras..."), on_input_canvas)
            return

        if self.current_group_id == self.AUDIO_GROUP_ID:
            def on_input_vn(query: Optional[str]) -> None:
                if not query: return
                results = []
                for vn in self.voice_notes:
                    if (query.lower() in vn.title.lower() or
                        query.lower() in vn.description.lower()):
                        results.append(vn)
                if not results:
                    self.notify(f"No se encontraron notas de voz para '{query}'", severity="error", timeout=3)
                else:
                    self.filter_tag_ids = []
                    filtered = self._get_filtered_voice_notes()
                    for idx, v in enumerate(filtered):
                        if v.id == results[0].id:
                            self.selected_index = idx
                            break
                    self.refresh_view()
                    self.notify(f"Encontradas {len(results)} nota(s) de voz", severity="information", timeout=2)
            self.push_screen(InputModal("🔍 Buscar Notas de Voz", placeholder="Buscar en notas de voz..."), on_input_vn)
            return

        def on_input(query: Optional[str]) -> None:
            if not query: return
            results = []
            for t in self.tasks:
                if query.lower() in t.text.lower():
                    gname = "Sin grupo"
                    if t.group_id:
                        g = next((x for x in self.groups if x.id == t.group_id), None)
                        gname = g.name if g else "Sin grupo"
                    results.append((t, gname))
            if not results:
                self.notify(f"No se encontraron tareas para '{query}'", severity="error", timeout=3)
            elif len(results) == 1:
                self._go_to_task(results[0][0])
            else:
                self.push_screen(SearchResultsScreen(results, query), lambda t: self._go_to_task(t) if t else None)
        self.push_screen(InputModal("🔍 Buscar", placeholder="Buscar tareas..."), on_input)
    
    def action_assign_tasks_from_calendar(self) -> None:
        if not self.calendar_mode:
            return
        
        has_unscheduled = any(
            (t.due_date is None and not t.done) or
            any(st.due_date is None and not st.done for st in t.subtasks)
            for t in self.tasks
        )
        
        if not has_unscheduled:
            self.notify("No hay tareas ni subtareas sin fecha para asignar", severity="information", timeout=3)
            return
        
        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                selected_date = f"{self.cal_year:04d}-{self.cal_month:02d}-{self.cal_day:02d}"
                
                task_ids = result.get("task_ids", [])
                subtask_selections = result.get("subtask_selections", [])
                
                for task in self.tasks:
                    if task.id in task_ids:
                        task.due_date = selected_date
                
                for task in self.tasks:
                    for subtask in task.subtasks:
                        if (task.id, subtask.id) in subtask_selections:
                            subtask.due_date = selected_date
                
                count = len(task_ids) + len(subtask_selections)
                if count > 0:
                    self.save_data()
                    self.refresh_calendar()
                    self.update_stats()
                    self.notify(f"📅 {count} elemento(s) asignado(s) (Ctrl+Z para deshacer)", 
                            severity="information", timeout=2)
        
        self.push_screen(UnscheduledItemsModal(self.tasks, self.groups), on_result)
    
    def action_filter_tasks(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode: return

        if self.current_group_id == self.CANVAS_GROUP_ID:
            self.notify("Las pizarras no tienen filtros", severity="information", timeout=2)
            return

        if self.current_group_id == self.NOTES_GROUP_ID or self.current_group_id == self.AUDIO_GROUP_ID:
            async def on_result(result: Optional[list[int]]) -> None:
                if result is not None:
                    self.filter_tag_ids = result
                    self.selected_index = 0
                    await self.refresh_view()
                    self.update_stats()

            self.push_screen(TagPickerModal(all_tags=self.tags, selected_tag_ids=self.filter_tag_ids), on_result)
            return

        if self.current_group_id == self.GENERAL_GROUP_ID:
            group_tasks = list(self.tasks)
        elif self.current_group_id is None:
            group_tasks = [t for t in self.tasks if t.group_id is None]
        else:
            group_tasks = [t for t in self.tasks if t.group_id == self.current_group_id]
        
        available_dates = [t.due_date for t in group_tasks if t.due_date]
        
        async def on_result(result: Optional[dict]) -> None:
            if result is not None:
                self.filter_dates = result.get("dates", [])
                self.filter_tag_ids = result.get("tags", [])
                self.filter_statuses = result.get("statuses", [])
                self.filter_priorities = result.get("priorities", [])
                self.selected_index = 0
                await self.refresh_view()
                self.update_stats()
        
        filter_title = "🔍 Filtrar Subtareas" if self.current_group_id == self.SUBTASKS_GROUP_ID else "🔍 Filtrar Tareas"
        self.push_screen(
            FilterModal(
                self.filter_dates,
                self.filter_tag_ids,
                self.filter_statuses,
                self.filter_priorities,
                self.tags,
                available_dates,
                title=filter_title
            ),
            on_result
        )
    
    def action_sort_tasks(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            return
        
        async def on_result(sort_criteria: Optional[dict[str, Optional[str]]]) -> None:
            if sort_criteria is not None:
                self.sort_criteria = sort_criteria
                self.selected_index = 0
                await self.refresh_view()
                self.update_stats()
        
        self.push_screen(SortPickerModal(self.sort_criteria), on_result)
    
    def action_new_group(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode: return
        async def on_result(name: Optional[str]) -> None:
            if name:
                self._save_undo_state()
                g = Group(id=self.next_group_id, name=name)
                self.next_group_id += 1
                self.groups.append(g)
                self.current_group_id = g.id
                self.selected_index = 0
                await self.refresh_tabs()
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("📁 Grupo creado (Ctrl+Z para deshacer)", severity="information", timeout=2)
        self.push_screen(InputModal("Nuevo Grupo", placeholder="Nombre..."), on_result)
    
    def action_group_options(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode or self.current_group_id is None or self.current_group_id == self.GENERAL_GROUP_ID:
            return
        g = next((x for x in self.groups if x.id == self.current_group_id), None)
        if not g: return
        
        async def on_opt(opt: str) -> None:
            if opt == "rename":
                def on_name(name: Optional[str]) -> None:
                    if name:
                        self._save_undo_state()
                        g.name = name
                        self.call_later(self._after_rename)
                        self.notify("✏️ Grupo renombrado (Ctrl+Z para deshacer)", severity="information", timeout=2)
                self.push_screen(InputModal("Renombrar", initial_text=g.name), on_name)
            elif opt == "delete":
                count = len([t for t in self.tasks if t.group_id == g.id])
                async def on_confirm(yes: bool) -> None:
                    if yes:
                        self._save_undo_state()
                        for t in [t for t in self.tasks if t.group_id == g.id]:
                            if t.voice_notes:
                                for vn in t.voice_notes:
                                    if vn.audio_path and os.path.exists(vn.audio_path):
                                        try: os.remove(vn.audio_path)
                                        except Exception: pass
                        self.tasks = [t for t in self.tasks if t.group_id != g.id]
                        self.groups.remove(g)
                        self.current_group_id = None
                        self.selected_index = 0
                        await self.refresh_tabs()
                        await self.refresh_view()
                        self.update_stats()
                        self.save_data()
                        self.notify(f"🗑️ Grupo eliminado con {count} tareas (Ctrl+Z para deshacer)", 
                                severity="information", timeout=2)
                self.push_screen(ConfirmModal(f"¿Eliminar '{g.name}' y sus {count} tareas?"), on_confirm)
        self.push_screen(GroupOptionsModal(g.name), on_opt)
    
    async def _after_rename(self) -> None:
        await self.refresh_tabs()
        self.update_stats()
        self.save_data()

    def action_manage_tags(self) -> None:
        if self.calendar_mode:
            return

        async def on_result(updated_tags: Optional[list[Tag]]) -> None:
            if updated_tags is not None:
                self._save_undo_state()

                old_tag_ids = {t.id for t in self.tags}
                new_tag_ids = {t.id for t in updated_tags}
                deleted_tag_ids = old_tag_ids - new_tag_ids

                if deleted_tag_ids:
                    for task in self.tasks:
                        task.tags = [tid for tid in task.tags if tid not in deleted_tag_ids]
                        for subtask in task.subtasks:
                            if hasattr(subtask, 'tags'):
                                subtask.tags = [tid for tid in subtask.tags if tid not in deleted_tag_ids]

                self.tags = updated_tags
                if updated_tags:
                    self.next_tag_id = max(t.id for t in updated_tags) + 1

                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("🏷️ Etiquetas actualizadas (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(TagsManagerModal(self.tags, self.next_tag_id), on_result)

    def action_manage_comments(self) -> None:
        if not self.subtasks or self.selected_index < 0:
            return
        subtask = self.subtasks[self.selected_index]
        
        next_comment_id = self.next_comment_id
        if subtask.comments:
            next_comment_id = max(c.id for c in subtask.comments) + 1
        
        def on_result(updated_comments: list[Comment]) -> None:
            subtask.comments = updated_comments
            if subtask.comments:
                self.next_comment_id = max(c.id for c in subtask.comments) + 1
            self.call_later(self.refresh_subtasks_list)
        
        self.app.push_screen(CommentsModal(subtask.comments, next_comment_id), on_result)
    
    def action_add_subtask_tab(self) -> None:
        if not self.tasks:
            self.notify("⚠️ No hay tareas disponibles donde añadir una subtarea", severity="warning")
            return

        def on_task_selected(selected_task: Optional[Task]) -> None:
            if selected_task:
                def on_subtask_text(text: Optional[str]) -> None:
                    if text:
                        self._save_undo_state()
                        new_subtask = Subtask(id=self.next_subtask_id, text=text)
                        self.next_subtask_id += 1
                        selected_task.subtasks.append(new_subtask)
                        self.save_data()
                        self.update_stats()
                        self.call_later(self.refresh_view)
                        self.notify("✅ Subtarea creada (Ctrl+Z para deshacer)", severity="information", timeout=2)
                self.push_screen(InputModal("📋 Nueva Subtarea", placeholder="Descripción..."), on_subtask_text)

        self.push_screen(TaskPickerModal(self.tasks), on_task_selected)

    def action_edit_subtask_tab(self) -> None:
        subtasks_items = self._get_ordered_subtasks()
        if not subtasks_items or self.selected_index < 0 or self.selected_index >= len(subtasks_items):
            return
        parent_task, subtask = subtasks_items[self.selected_index]

        next_comment_id = max((c.id for c in subtask.comments), default=0) + 1 if subtask.comments else 1

        def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                subtask.text = result["text"]
                if "status" in result:
                    subtask.set_status(result["status"])
                subtask.comments = result.get("comments", [])
                subtask.tags = result.get("tags", [])
                subtask.priority = result.get("priority", 0)
                subtask.due_date = result.get("due_date", "")
                subtask.notes = result.get("notes", [])
                subtask.voice_notes = result.get("voice_notes", [])
                subtask.canvas_list = result.get("canvas_list", [])

                for n in subtask.notes:
                    if not any(gn.id == n.id for gn in self.notes):
                        self.notes.append(n)
                for v in subtask.voice_notes:
                    if not any(gv.id == v.id for gv in self.voice_notes):
                        self.voice_notes.append(v)
                for c in subtask.canvas_list:
                    if not any(gc.id == c.id for gc in self.canvas_list):
                        self.canvas_list.append(c)

                self.save_data()
                self.update_stats()
                self.call_later(self.refresh_view)
                self.notify("✏️ Subtarea editada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(
            EditSubtaskModal(subtask.text, subtask.comments, next_comment_id,
                           all_tags=self.tags, selected_tags=subtask.tags,
                           priority=subtask.priority, due_date=subtask.due_date,
                           notes=getattr(subtask, 'notes', []),
                           voice_notes=getattr(subtask, 'voice_notes', []),
                           canvas_list=getattr(subtask, 'canvas_list', []),
                           global_notes=self.notes,
                           global_voice_notes=self.voice_notes,
                           global_canvas_list=self.canvas_list,
                           status=getattr(subtask, 'status', 'En progreso')),
            on_result
        )

    def action_delete_subtask_tab(self) -> None:
        subtasks_items = self._get_ordered_subtasks()
        if not subtasks_items or self.selected_index < 0 or self.selected_index >= len(subtasks_items):
            return
        parent_task, subtask = subtasks_items[self.selected_index]

        txt = subtask.text[:30] + "..." if len(subtask.text) > 30 else subtask.text
        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                if subtask in parent_task.subtasks:
                    parent_task.subtasks.remove(subtask)
                self.save_data()
                self.update_stats()
                await self.refresh_view()
                self.notify("🗑️ Subtarea eliminada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(ConfirmModal(f"¿Eliminar la subtarea '{txt}'?"), on_confirm)

    def _edit_subtask_obj(self, subtask: Subtask) -> None:
        next_comment_id = max((c.id for c in subtask.comments), default=0) + 1 if subtask.comments else 1

        def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                subtask.text = result["text"]
                if "status" in result:
                    subtask.set_status(result["status"])
                subtask.comments = result.get("comments", [])
                subtask.tags = result.get("tags", [])
                subtask.priority = result.get("priority", 0)
                subtask.due_date = result.get("due_date", "")
                subtask.notes = result.get("notes", [])
                subtask.voice_notes = result.get("voice_notes", [])
                subtask.canvas_list = result.get("canvas_list", [])

                for n in subtask.notes:
                    if not any(gn.id == n.id for gn in self.notes):
                        self.notes.append(n)
                for v in subtask.voice_notes:
                    if not any(gv.id == v.id for gv in self.voice_notes):
                        self.voice_notes.append(v)
                for c in subtask.canvas_list:
                    if not any(gc.id == c.id for gc in self.canvas_list):
                        self.canvas_list.append(c)

                self.save_data()
                self.update_stats()
                self.call_later(self.refresh_view)
                self.notify("✏️ Subtarea editada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(
            EditSubtaskModal(subtask.text, subtask.comments, next_comment_id,
                           all_tags=self.tags, selected_tags=subtask.tags,
                           priority=subtask.priority, due_date=subtask.due_date,
                           notes=getattr(subtask, 'notes', []),
                           voice_notes=getattr(subtask, 'voice_notes', []),
                           canvas_list=getattr(subtask, 'canvas_list', []),
                           global_notes=self.notes,
                           global_voice_notes=self.voice_notes,
                           global_canvas_list=self.canvas_list,
                           status=getattr(subtask, 'status', 'En progreso')),
            on_result
        )

    def _delete_subtask_obj(self, subtask: Subtask) -> None:
        parent_task = next((t for t in self.tasks if subtask in t.subtasks), None)
        txt = subtask.text[:30] + "..." if len(subtask.text) > 30 else subtask.text
        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                if parent_task and subtask in parent_task.subtasks:
                    parent_task.subtasks.remove(subtask)
                self.save_data()
                self.update_stats()
                await self.refresh_view()
                self.notify("🗑️ Subtarea eliminada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(ConfirmModal(f"¿Eliminar la subtarea '{txt}'?"), on_confirm)

    def action_add_task(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode:
            self.action_assign_tasks_from_calendar()
            return

        if self.current_group_id == self.SUBTASKS_GROUP_ID:
            self.action_add_subtask_tab()
            return

        if self.current_group_id == self.NOTES_GROUP_ID:
            self.action_add_note()
            return

        if self.current_group_id == self.CANVAS_GROUP_ID:
            self.action_add_canvas()
            return

        if self.current_group_id == self.AUDIO_GROUP_ID:
            self.action_add_voice_note()
            return

        if self.current_group_id == self.TAGS_GROUP_ID:
            self.action_add_tag()
            return

        if self.current_group_id == self.GENERAL_GROUP_ID:
            self.notify("No se pueden crear tareas en General. Cambia a un grupo específico.", severity="error", timeout=3)
            return
        
        async def on_result(text: Optional[str]) -> None:
            if text:
                self._save_undo_state()
                t = Task(id=self.next_task_id, text=text, group_id=self.current_group_id)
                self.next_task_id += 1
                self.tasks.append(t)
                pending = [x for x in self._get_current_tasks() if not x.done]
                self.selected_index = len(pending) - 1
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("✅ Tarea creada (Ctrl+Z para deshacer)", severity="information", timeout=2)
        self.push_screen(InputModal("Nueva Tarea", placeholder="Escribe la tarea..."), on_result)
    
    def action_edit_task(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode: return

        if self.current_group_id == self.SUBTASKS_GROUP_ID:
            self.action_edit_subtask_tab()
            return

        if self.current_group_id == self.NOTES_GROUP_ID:
            self.action_edit_note()
            return

        if self.current_group_id == self.CANVAS_GROUP_ID:
            self.action_edit_canvas()
            return

        if self.current_group_id == self.AUDIO_GROUP_ID:
            self.action_edit_voice_note()
            return

        if self.current_group_id == self.TAGS_GROUP_ID:
            self.action_edit_tag()
            return

        if self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item:
                itype, obj = item
                if itype == "note":
                    self.action_edit_note(obj)
                    return
                elif itype == "canvas":
                    self.action_edit_canvas(obj)
                    return
                elif itype == "voice_note":
                    self.action_edit_voice_note(obj)
                    return
                elif itype == "tag":
                    self.action_edit_tag(obj)
                    return
                elif itype == "subtask":
                    self._edit_subtask_obj(obj)
                    return

        w = self.get_selected_widget()
        if not w: return
        t = w.task_data
        next_comment_id = 1
        if t.comments:
            next_comment_id = max(c.id for c in t.comments) + 1
        
        next_subtask_id = 1
        if t.subtasks:
            next_subtask_id = max(s.id for s in t.subtasks) + 1

        next_note_id = max((n.id for n in t.notes), default=0) + 1 if t.notes else 1
        next_voice_note_id = max((v.id for v in t.voice_notes), default=0) + 1 if t.voice_notes else 1
        next_canvas_id = max((c.id for c in t.canvas_list), default=0) + 1 if t.canvas_list else 1
        
        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                t.text = result["text"]
                if "status" in result:
                    t.set_status(result["status"])
                t.due_date = result["date"]
                t.comments = result.get("comments", [])
                t.tags = result.get("tags", [])
                t.priority = result.get("priority", 0)
                t.subtasks = result.get("subtasks", [])
                t.notes = result.get("notes", [])
                t.voice_notes = result.get("voice_notes", [])
                t.canvas_list = result.get("canvas_list", [])

                for n in t.notes:
                    if not any(gn.id == n.id for gn in self.notes):
                        self.notes.append(n)
                for v in t.voice_notes:
                    if not any(gv.id == v.id for gv in self.voice_notes):
                        self.voice_notes.append(v)
                for c in t.canvas_list:
                    if not any(gc.id == c.id for gc in self.canvas_list):
                        self.canvas_list.append(c)

                old_group_id = t.group_id
                new_group_id = result.get("group_id")
                t.group_id = new_group_id
                self.save_data()
                if old_group_id != new_group_id:
                    self.current_group_id = new_group_id
                    self.selected_index = 0
                    await self.refresh_tabs()
                await self.refresh_view()
                self.update_stats()
                for i, task in enumerate(self._get_ordered_tasks()):
                    if task.id == t.id:
                        self.selected_index = i
                        break
                self.update_selection()
                self.notify("✏️ Tarea editada (Ctrl+Z para deshacer)", severity="information", timeout=2)
        
        self.push_screen(EditTaskModal(t.text, t.due_date, t.group_id, self.groups, 
                                    t.comments, next_comment_id, self.tags, t.tags, 
                                    t.priority, t.subtasks, next_subtask_id,
                                    t.notes, next_note_id, t.voice_notes, next_voice_note_id,
                                    t.canvas_list, next_canvas_id,
                                    current_status=getattr(t, 'status', 'En progreso')), on_result)
        
    def action_delete_task(self) -> None:
        if self.main_search_focused: return
        if self.calendar_mode: return

        if self.current_group_id == self.SUBTASKS_GROUP_ID:
            self.action_delete_subtask_tab()
            return

        if self.current_group_id == self.NOTES_GROUP_ID:
            self.action_delete_note()
            return

        if self.current_group_id == self.CANVAS_GROUP_ID:
            self.action_delete_canvas()
            return

        if self.current_group_id == self.AUDIO_GROUP_ID:
            self.action_delete_voice_note()
            return

        if self.current_group_id == self.TAGS_GROUP_ID:
            self.action_delete_tag()
            return

        if self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item:
                itype, obj = item
                if itype == "note":
                    self.action_delete_note(obj)
                    return
                elif itype == "canvas":
                    self.action_delete_canvas(obj)
                    return
                elif itype == "voice_note":
                    self.action_delete_voice_note(obj)
                    return
                elif itype == "tag":
                    self.action_delete_tag(obj)
                    return
                elif itype == "subtask":
                    self._delete_subtask_obj(obj)
                    return

        ordered = self._get_ordered_tasks()
        if not ordered: return
        t = ordered[self.selected_index]
        
        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                if t.voice_notes:
                    for vn in t.voice_notes:
                        if vn.audio_path and os.path.exists(vn.audio_path):
                            try: os.remove(vn.audio_path)
                            except Exception: pass
                self.tasks.remove(t)
                if self.selected_index >= len(self._get_ordered_tasks()) and self.selected_index > 0:
                    self.selected_index -= 1
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("🗑️ Tarea eliminada (Ctrl+Z para deshacer)", severity="information", timeout=2)
        txt = t.text[:30] + "..." if len(t.text) > 30 else t.text
        self.push_screen(ConfirmModal(f"¿Eliminar '{txt}'?"), on_confirm)

    def action_add_voice_note(self) -> None:
        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                new_id = max([v.id for v in self.voice_notes], default=0) + 1
                self.next_voice_note_id = max(self.next_voice_note_id, new_id + 1)
                vn = VoiceNote(
                    id=new_id,
                    title=result["title"],
                    audio_path=result.get("audio_path", ""),
                    description=result.get("description", ""),
                    duration=result.get("duration", 0.0),
                    tags=result.get("tags", [])
                )
                self.voice_notes.append(vn)

                target_task_ids = result.get("target_task_ids", [])
                for target_task_id in target_task_ids:
                    task = next((t for t in self.tasks if t.id == target_task_id), None)
                    if task:
                        if not any(v.id == vn.id for v in task.voice_notes):
                            task.voice_notes.append(vn)
                if target_task_ids:
                    self.notify(f"📌 Vinculada a {len(target_task_ids)} tarea(s)", severity="information", timeout=3)

                self.selected_index = 0
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("✅ Nota de voz creada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        modal = VoiceNoteEditModal(modal_title="🎤 Nueva Nota de Voz", all_tags=self.tags)
        self.push_screen(modal, on_result)

    def action_edit_voice_note(self, target_voice_note: VoiceNote = None) -> None:
        if target_voice_note:
            vn = target_voice_note
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "voice_note": vn = item[1]
            else: return
        else:
            vns = self._get_filtered_voice_notes()
            if not vns or self.selected_index >= len(vns): return
            vn = vns[self.selected_index]
        associated_task_ids = [t.id for t in self.tasks if any(v.id == vn.id for v in t.voice_notes)]

        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                vn.title = result["title"]
                vn.description = result.get("description", "")
                vn.audio_path = result.get("audio_path", "")
                vn.duration = result.get("duration", 0.0)
                vn.tags = result.get("tags", [])

                for t in self.tasks:
                    t.voice_notes = [v for v in t.voice_notes if v.id != vn.id]

                target_task_ids = result.get("target_task_ids", [])
                for target_task_id in target_task_ids:
                    task = next((t for t in self.tasks if t.id == target_task_id), None)
                    if task:
                        task.voice_notes.append(vn)
                if target_task_ids:
                    self.notify(f"📌 Vinculada a {len(target_task_ids)} tarea(s)", severity="information", timeout=3)

                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("✅ Nota de voz actualizada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        modal = VoiceNoteEditModal(
            modal_title="🎤 Editar Nota de Voz",
            initial_title=vn.title,
            initial_description=vn.description,
            initial_audio=vn.audio_path,
            initial_duration=vn.duration,
            all_tags=self.tags,
            selected_tag_ids=vn.tags,
            selected_tasks=associated_task_ids
        )
        modal.selected_tasks = associated_task_ids
        self.push_screen(modal, on_result)

    def action_delete_voice_note(self, target_voice_note: VoiceNote = None) -> None:
        if target_voice_note:
            vn = target_voice_note
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "voice_note": vn = item[1]
            else: return
        else:
            vns = self._get_filtered_voice_notes()
            if not vns or self.selected_index >= len(vns): return
            vn = vns[self.selected_index]

        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                if vn.audio_path and os.path.exists(vn.audio_path):
                    try: os.remove(vn.audio_path)
                    except Exception: pass
                self.voice_notes.remove(vn)
                for t in self.tasks:
                    t.voice_notes = [v for v in t.voice_notes if v.id != vn.id]
                if self.selected_index >= len(self._get_filtered_voice_notes()) and self.selected_index > 0:
                    self.selected_index -= 1
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("🗑️ Nota de voz eliminada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        txt = vn.title[:30] + "..." if len(vn.title) > 30 else vn.title
        self.push_screen(ConfirmModal(f"¿Eliminar nota de voz '{txt}'?"), on_confirm)

    def action_play_voice_note(self, target_voice_note: VoiceNote = None) -> None:
        if target_voice_note:
            vn = target_voice_note
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "voice_note": vn = item[1]
            else: return
        else:
            vns = self._get_filtered_voice_notes()
            if not vns or self.selected_index >= len(vns): return
            vn = vns[self.selected_index]
        self.push_screen(AudioPlayerModal(vn.title, vn.audio_path))

    def action_add_note(self) -> None:
        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                new_id = max([n.id for n in self.notes], default=0) + 1
                self.next_note_id = max(self.next_note_id, new_id + 1)
                note = Note(
                    id=new_id,
                    title=result["title"],
                    description=result.get("description", ""),
                    url=result.get("url"),
                    image_path=result.get("image_path"),
                    file_path=result.get("file_path"),
                    tags=result.get("tags", [])
                )
                self.notes.append(note)

                target_task_ids = result.get("target_task_ids", [])
                for target_task_id in target_task_ids:
                    task = next((t for t in self.tasks if t.id == target_task_id), None)
                    if task:
                        if not any(n.id == note.id for n in task.notes):
                            task.notes.append(note)
                if target_task_ids:
                    self.notify(f"📌 Vinculada a {len(target_task_ids)} tarea(s)", severity="information", timeout=3)

                self.selected_index = 0
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("✅ Nota creada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        modal = NoteEditModal(modal_title="📝 Nueva Nota", all_tags=self.tags)
        self.push_screen(modal, on_result)

    def action_edit_note(self, target_note: Note = None) -> None:
        if target_note:
            note = target_note
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "note": note = item[1]
            else: return
        else:
            notes = self._get_filtered_notes()
            if not notes or self.selected_index >= len(notes): return
            note = notes[self.selected_index]
        associated_task_ids = [t.id for t in self.tasks if any(n.id == note.id for n in t.notes)]

        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                note.title = result["title"]
                note.description = result.get("description", "")
                note.url = result.get("url")
                note.image_path = result.get("image_path")
                note.file_path = result.get("file_path")
                note.tags = result.get("tags", [])

                for t in self.tasks:
                    t.notes = [n for n in t.notes if n.id != note.id]

                target_task_ids = result.get("target_task_ids", [])
                for target_task_id in target_task_ids:
                    task = next((t for t in self.tasks if t.id == target_task_id), None)
                    if task:
                        task.notes.append(note)
                if target_task_ids:
                    self.notify(f"📌 Vinculada a {len(target_task_ids)} tarea(s)", severity="information", timeout=3)

                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("✅ Nota actualizada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        modal = NoteEditModal(
            modal_title="📝 Editar Nota",
            initial_title=note.title,
            initial_description=note.description,
            initial_url=note.url or "",
            initial_image=note.image_path or "",
            initial_file=note.file_path or "",
            all_tags=self.tags,
            selected_tag_ids=note.tags
        )
        modal.selected_tasks = associated_task_ids
        self.push_screen(modal, on_result)

    def action_delete_note(self, target_note: Note = None) -> None:
        if target_note:
            note = target_note
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "note": note = item[1]
            else: return
        else:
            notes = self._get_filtered_notes()
            if not notes or self.selected_index >= len(notes): return
            note = notes[self.selected_index]

        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                self.notes.remove(note)
                for t in self.tasks:
                    t.notes = [n for n in t.notes if n.id != note.id]
                if self.selected_index >= len(self._get_filtered_notes()) and self.selected_index > 0:
                    self.selected_index -= 1
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("🗑️ Nota eliminada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        txt = note.title[:30] + "..." if len(note.title) > 30 else note.title
        self.push_screen(ConfirmModal(f"¿Eliminar '{txt}'?"), on_confirm)

    def action_view_note(self, target_note: Note = None) -> None:
        if target_note:
            note = target_note
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "note": note = item[1]
            else: return
        else:
            notes = self._get_filtered_notes()
            if not notes or self.selected_index >= len(notes): return
            note = notes[self.selected_index]

        content_lines = []
        content_lines.append(f"[bold]{note.title}[/bold]")
        content_lines.append("")

        if note.description:
            content_lines.append(note.description)
            content_lines.append("")

        if note.url:
            content_lines.append(f"🔗 Enlace: {note.url}")

        if note.image_path:
            content_lines.append(f"📷 Imagen: {note.image_path}")

        if note.file_path:
            content_lines.append(f"📎 Archivo: {note.file_path}")

        if note.tags:
            tag_names = []
            for tag_id in note.tags:
                tag = next((t for t in self.tags if t.id == tag_id), None)
                if tag:
                    tag_names.append(tag.name)
            if tag_names:
                content_lines.append("")
                content_lines.append(f"🏷️ Etiquetas: {', '.join(tag_names)}")

        content_lines.append("")
        content_lines.append(f"📅 Creada: {note.created_at}")

        content = "\n".join(content_lines)
        self.push_screen(InputModal(
            "📝 Ver Nota",
            placeholder=content
        ), lambda x: None)

        if note.url:
            try:
                import webbrowser
                webbrowser.open(note.url)
            except:
                pass

    def action_add_canvas(self) -> None:
        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                new_id = max([c.id for c in self.canvas_list], default=0) + 1
                self.next_canvas_id = max(self.next_canvas_id, new_id + 1)
                canvas = Canvas(
                    id=new_id,
                    title=result["title"],
                    width=result["width"],
                    height=result["height"],
                    grid=result["grid"],
                    tags=result.get("tags", [])
                )
                self.canvas_list.append(canvas)

                target_task_ids = result.get("target_task_ids", [])
                for target_task_id in target_task_ids:
                    task = next((t for t in self.tasks if t.id == target_task_id), None)
                    if task:
                        if task.canvas_list is None: task.canvas_list = []
                        if not any(c.id == canvas.id for c in task.canvas_list):
                            task.canvas_list.append(canvas)
                if target_task_ids:
                    self.notify(f"📌 Vinculada a {len(target_task_ids)} tarea(s)", severity="information", timeout=3)

                self.selected_index = 0
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("✅ Pizarra creada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(CanvasEditorModal(all_tags=self.tags), on_result)

    def action_edit_canvas(self, target_canvas: Canvas = None) -> None:
        if target_canvas:
            canvas = target_canvas
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "canvas": canvas = item[1]
            else: return
        else:
            canvas_list = self._get_filtered_canvas()
            if not canvas_list or self.selected_index >= len(canvas_list): return
            canvas = canvas_list[self.selected_index]

        associated_task_ids = [t.id for t in self.tasks if t.canvas_list and any(c.id == canvas.id for c in t.canvas_list)]

        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                canvas.title = result["title"]
                canvas.width = result["width"]
                canvas.height = result["height"]
                canvas.grid = result["grid"]
                canvas.tags = result.get("tags", [])

                target_task_ids = result.get("target_task_ids", [])
                for task in self.tasks:
                    if task.canvas_list is None: task.canvas_list = []
                    if task.id in target_task_ids:
                        if not any(c.id == canvas.id for c in task.canvas_list):
                            task.canvas_list.append(canvas)
                    else:
                        task.canvas_list = [c for c in task.canvas_list if c.id != canvas.id]

                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("✅ Pizarra actualizada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(CanvasEditorModal(canvas_data=canvas, all_tags=self.tags, selected_tag_ids=canvas.tags, selected_task_ids=associated_task_ids), on_result)

    def action_delete_canvas(self, target_canvas: Canvas = None) -> None:
        if target_canvas:
            canvas = target_canvas
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "canvas": canvas = item[1]
            else: return
        else:
            canvas_list = self._get_filtered_canvas()
            if not canvas_list or self.selected_index >= len(canvas_list): return
            canvas = canvas_list[self.selected_index]

        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                self.canvas_list.remove(canvas)
                if self.selected_index >= len(self._get_filtered_canvas()) and self.selected_index > 0:
                    self.selected_index -= 1
                await self.refresh_view()
                self.update_stats()
                self.save_data()
                self.notify("🗑️ Pizarra eliminada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        txt = canvas.title[:30] + "..." if len(canvas.title) > 30 else canvas.title
        self.push_screen(ConfirmModal(f"¿Eliminar '{txt}'?"), on_confirm)

    def _capture_state(self) -> dict:
        return {
            "next_task_id": self.next_task_id,
            "next_group_id": self.next_group_id,
            "next_tag_id": self.next_tag_id,
            "next_subtask_id": self.next_subtask_id,
            "next_note_id": self.next_note_id,
            "next_canvas_id": self.next_canvas_id,
            "next_voice_note_id": self.next_voice_note_id,
            "current_group_id": self.current_group_id,
            "selected_index": self.selected_index,
            "groups": [{"id": g.id, "name": g.name} for g in self.groups],
            "tags": [{"id": t.id, "name": t.name, "created_at": t.created_at} for t in self.tags],
            "notes": [{
                "id": n.id,
                "title": n.title,
                "description": n.description,
                "url": n.url,
                "image_path": n.image_path,
                "file_path": n.file_path,
                "created_at": n.created_at,
                "tags": list(n.tags)
            } for n in self.notes],
            "canvas": [{
                "id": c.id,
                "title": c.title,
                "width": c.width,
                "height": c.height,
                "grid": c.grid,
                "created_at": c.created_at
            } for c in self.canvas_list],
            "voice_notes": [{
                "id": v.id,
                "title": v.title,
                "audio_path": v.audio_path,
                "description": v.description,
                "duration": v.duration,
                "created_at": v.created_at,
                "tags": list(v.tags)
            } for v in self.voice_notes],
            "tasks": [{
                "id": t.id,
                "text": t.text,
                "done": t.done,
                "status": getattr(t, "status", "Completado" if t.done else "En progreso"),
                "created_at": t.created_at,
                "group_id": t.group_id,
                "due_date": t.due_date,
                "comments": [{
                    "id": c.id,
                    "title": c.title,
                    "description": c.description,
                    "url": c.url,
                    "image_path": c.image_path,
                    "file_path": c.file_path,
                    "created_at": c.created_at
                } for c in t.comments],
                "tags": list(t.tags),
                "priority": t.priority,
                "subtasks": [{
                    "id": s.id,
                    "text": s.text,
                    "done": s.done,
                    "status": getattr(s, "status", "Completado" if s.done else "En progreso"),
                    "created_at": s.created_at,
                    "due_date": s.due_date,
                    "tags": s.tags if hasattr(s, 'tags') else [],
                    "priority": s.priority if hasattr(s, 'priority') else 0,
                    "comments": [{
                        "id": c.id,
                        "title": c.title,
                        "description": c.description,
                        "url": c.url,
                        "image_path": c.image_path,
                        "file_path": c.file_path,
                        "created_at": c.created_at
                    } for c in s.comments]
                } for s in t.subtasks],
                "notes": [{
                    "id": n.id,
                    "title": n.title,
                    "description": n.description,
                    "url": n.url,
                    "image_path": n.image_path,
                    "file_path": n.file_path,
                    "created_at": n.created_at,
                    "tags": list(n.tags)
                } for n in t.notes],
                "voice_notes": [{
                    "id": v.id,
                    "title": v.title,
                    "audio_path": v.audio_path,
                    "description": v.description,
                    "duration": v.duration,
                    "created_at": v.created_at,
                    "tags": list(v.tags)
                } for v in t.voice_notes],
                "canvas": [{
                    "id": c.id,
                    "title": c.title,
                    "width": c.width,
                    "height": c.height,
                    "grid": c.grid,
                    "created_at": c.created_at,
                    "tags": list(c.tags) if hasattr(c, 'tags') and c.tags else []
                } for c in getattr(t, 'canvas_list', [])]
            } for t in self.tasks]
        }

    def _save_undo_state(self) -> None:
        state = self._capture_state()
        self.undo_stack.append(state)

        self.redo_stack.clear()

        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

    def _restore_state(self, state: dict) -> None:
        self.next_task_id = state["next_task_id"]
        self.next_group_id = state["next_group_id"]
        self.next_tag_id = state["next_tag_id"]
        self.next_subtask_id = state.get("next_subtask_id", 1)
        self.next_note_id = state.get("next_note_id", 1)
        self.next_canvas_id = state.get("next_canvas_id", 1)
        self.next_voice_note_id = state.get("next_voice_note_id", 1)
        self.current_group_id = state["current_group_id"]
        self.selected_index = state["selected_index"]

        self.groups = [Group(id=g["id"], name=g["name"]) for g in state["groups"]]

        self.tags = [Tag(id=t["id"], name=t["name"]) for t in state["tags"]]

        self.notes = [Note(
            id=n["id"],
            title=n.get("title", ""),
            description=n.get("description", ""),
            url=n.get("url"),
            image_path=n.get("image_path"),
            file_path=n.get("file_path"),
            created_at=n.get("created_at", ""),
            tags=n.get("tags", [])
        ) for n in state.get("notes", [])]

        self.canvas_list = [Canvas(
            id=c["id"],
            title=c.get("title", ""),
            width=c.get("width", 50),
            height=c.get("height", 20),
            grid=c.get("grid", [[" " for _ in range(c.get("width", 50))] for _ in range(c.get("height", 20))]),
            created_at=c.get("created_at", "")
        ) for c in state.get("canvas", [])]

        self.voice_notes = [VoiceNote(
            id=v["id"],
            title=v.get("title", ""),
            audio_path=v.get("audio_path", ""),
            description=v.get("description", ""),
            duration=v.get("duration", 0.0),
            created_at=v.get("created_at", ""),
            tags=v.get("tags", [])
        ) for v in state.get("voice_notes", [])]

        self.tasks = []
        for t in state["tasks"]:
            comments = [Comment(
                id=c["id"],
                title=c.get("title", c.get("text", "")),
                description=c.get("description", ""),
                url=c.get("url"),
                image_path=c.get("image_path"),
                file_path=c.get("file_path"),
                created_at=c.get("created_at", "")
            ) for c in t["comments"]]
            
            subtasks = []
            for s in t.get("subtasks", []):
                subtask_comments = [Comment(
                    id=c["id"],
                    title=c.get("title", c.get("text", "")),
                    description=c.get("description", ""),
                    url=c.get("url"),
                    image_path=c.get("image_path"),
                    file_path=c.get("file_path"),
                    created_at=c.get("created_at", "")
                ) for c in s.get("comments", [])]
                
                subtask_notes = [Note(
                    id=n["id"], title=n.get("title", ""), description=n.get("description", ""),
                    url=n.get("url"), image_path=n.get("image_path"), file_path=n.get("file_path"),
                    created_at=n.get("created_at", ""), tags=n.get("tags", [])
                ) for n in s.get("notes", [])]
                subtask_voice_notes = [VoiceNote(
                    id=v["id"], title=v.get("title", ""), audio_path=v.get("audio_path", ""),
                    description=v.get("description", ""), duration=v.get("duration", 0.0),
                    created_at=v.get("created_at", ""), tags=v.get("tags", [])
                ) for v in s.get("voice_notes", [])]
                subtask_canvas_list = [Canvas(
                    id=c["id"], title=c.get("title", ""), width=c.get("width", 50),
                    height=c.get("height", 20), grid=c.get("grid", []), created_at=c.get("created_at", "")
                ) for c in s.get("canvas", [])]
                
                subtask = Subtask(
                    id=s["id"],
                    text=s["text"],
                    done=s.get("done", False),
                    status=s.get("status", "Completado" if s.get("done", False) else "En progreso"),
                    created_at=s.get("created_at", ""),
                    due_date=s.get("due_date"),
                    comments=subtask_comments,
                    tags=s.get("tags", []),
                    priority=s.get("priority", 0),
                    notes=subtask_notes,
                    voice_notes=subtask_voice_notes,
                    canvas_list=subtask_canvas_list
                )
                subtasks.append(subtask)
            
            task_notes = [Note(
                id=n["id"],
                title=n.get("title", ""),
                description=n.get("description", ""),
                url=n.get("url"),
                image_path=n.get("image_path"),
                file_path=n.get("file_path"),
                created_at=n.get("created_at", ""),
                tags=n.get("tags", [])
            ) for n in t.get("notes", [])]

            task_voice_notes = [VoiceNote(
                id=v["id"],
                title=v.get("title", ""),
                audio_path=v.get("audio_path", ""),
                description=v.get("description", ""),
                duration=v.get("duration", 0.0),
                created_at=v.get("created_at", ""),
                tags=v.get("tags", [])
            ) for v in t.get("voice_notes", [])]

            task_canvas_list = [Canvas(
                id=c["id"],
                title=c.get("title", ""),
                width=c.get("width", 50),
                height=c.get("height", 20),
                grid=c.get("grid", [[" " for _ in range(c.get("width", 50))] for _ in range(c.get("height", 20))]),
                created_at=c.get("created_at", "")
            ) for c in t.get("canvas", [])]
            
            task = Task(
                id=t["id"],
                text=t["text"],
                done=t["done"],
                status=t.get("status", "Completado" if t.get("done", False) else "En progreso"),
                created_at=t["created_at"],
                group_id=t["group_id"],
                due_date=t["due_date"],
                comments=comments,
                tags=list(t["tags"]),
                priority=t["priority"],
                subtasks=subtasks,
                notes=task_notes,
                voice_notes=task_voice_notes,
                canvas_list=task_canvas_list
            )
            self.tasks.append(task)

    async def action_undo(self) -> None:
        if not self.undo_stack:
            self.notify("⚠️ No hay acciones para deshacer", severity="warning", timeout=2)
            return

        current_state = self._capture_state()
        self.redo_stack.append(current_state)

        if len(self.redo_stack) > self.max_undo:
            self.redo_stack.pop(0)

        previous_state = self.undo_stack.pop()

        self._restore_state(previous_state)

        await self.refresh_tabs()
        await self.refresh_view()
        self.update_stats()

        self.notify(f"↩️ Deshecho (Ctrl+Y para rehacer | {len(self.undo_stack)} deshacer restantes)", severity="information", timeout=2)
    
    async def action_redo(self) -> None:
        if not self.redo_stack:
            self.notify("⚠️ No hay acciones para rehacer", severity="warning", timeout=2)
            return

        current_state = self._capture_state()
        self.undo_stack.append(current_state)

        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

        redo_state = self.redo_stack.pop()

        self._restore_state(redo_state)

        await self.refresh_tabs()
        await self.refresh_view()
        self.update_stats()

        self.notify(f"↪️ Rehecho (Ctrl+Z para deshacer | {len(self.redo_stack)} rehacer restantes)", severity="information", timeout=2)

    def save_data(self) -> None:
        with self.save_lock:
            data = {
                "next_task_id": self.next_task_id,
                "next_group_id": self.next_group_id,
                "next_tag_id": self.next_tag_id,
                "next_subtask_id": self.next_subtask_id,
                "next_note_id": self.next_note_id,
                "next_canvas_id": self.next_canvas_id,
                "next_voice_note_id": self.next_voice_note_id,
                "groups": [{"id": g.id, "name": g.name} for g in self.groups],
                "tags": [{"id": t.id, "name": t.name, "created_at": t.created_at} for t in self.tags],
                "notes": [{
                    "id": n.id,
                    "title": n.title,
                    "description": n.description,
                    "url": n.url,
                    "image_path": n.image_path,
                    "file_path": n.file_path,
                    "created_at": n.created_at,
                    "tags": n.tags
                } for n in self.notes],
                "canvas": [{
                    "id": c.id,
                    "title": c.title,
                    "width": c.width,
                    "height": c.height,
                    "grid": c.grid,
                    "created_at": c.created_at
                } for c in self.canvas_list],
                "voice_notes": [{
                    "id": v.id,
                    "title": v.title,
                    "audio_path": v.audio_path,
                    "description": v.description,
                    "duration": v.duration,
                    "created_at": v.created_at,
                    "tags": v.tags
                } for v in self.voice_notes],
                "tasks": [{
                    "id": t.id, 
                    "text": t.text, 
                    "done": t.done, 
                    "status": getattr(t, "status", "Completado" if t.done else "En progreso"),
                    "created_at": t.created_at,
                    "group_id": t.group_id, 
                    "due_date": t.due_date,
                    "comments": [{"id": c.id, "title": c.title, "description": c.description,
                                "url": c.url, "image_path": c.image_path, "file_path": c.file_path,
                                "created_at": c.created_at}
                                for c in t.comments],
                    "tags": t.tags, 
                    "priority": t.priority,
                    "subtasks": [{
                        "id": s.id,
                        "text": s.text,
                        "done": s.done,
                        "status": getattr(s, "status", "Completado" if s.done else "En progreso"),
                        "created_at": s.created_at,
                        "due_date": s.due_date,
                        "tags": s.tags if hasattr(s, 'tags') else [],
                        "priority": s.priority if hasattr(s, 'priority') else 0,
                        "comments": [{
                            "id": c.id,
                            "title": c.title,
                            "description": c.description,
                            "url": c.url,
                            "image_path": c.image_path,
                            "file_path": c.file_path,
                            "created_at": c.created_at
                        } for c in s.comments],
                        "notes": [{
                            "id": n.id, "title": n.title, "description": n.description,
                            "url": n.url, "image_path": n.image_path, "file_path": n.file_path,
                            "created_at": n.created_at, "tags": n.tags
                        } for n in getattr(s, 'notes', [])],
                        "voice_notes": [{
                            "id": v.id, "title": v.title, "audio_path": v.audio_path,
                            "description": v.description, "duration": v.duration,
                            "created_at": v.created_at, "tags": v.tags
                        } for v in getattr(s, 'voice_notes', [])],
                        "canvas": [{
                            "id": c.id, "title": c.title, "width": c.width,
                            "height": c.height, "grid": c.grid, "created_at": c.created_at
                        } for c in getattr(s, 'canvas_list', [])]
                    } for s in t.subtasks],
                    "notes": [{
                        "id": n.id,
                        "title": n.title,
                        "description": n.description,
                        "url": n.url,
                        "image_path": n.image_path,
                        "file_path": n.file_path,
                        "created_at": n.created_at,
                        "tags": n.tags
                    } for n in t.notes],
                    "voice_notes": [{
                        "id": v.id,
                        "title": v.title,
                        "audio_path": v.audio_path,
                        "description": v.description,
                        "duration": v.duration,
                        "created_at": v.created_at,
                        "tags": v.tags
                    } for v in t.voice_notes],
                    "canvas": [{
                        "id": c.id,
                        "title": c.title,
                        "width": c.width,
                        "height": c.height,
                        "grid": c.grid,
                        "created_at": c.created_at,
                        "tags": getattr(c, 'tags', [])
                    } for c in getattr(t, 'canvas_list', [])]
                } for t in self.tasks]
            }
        try:
            self.data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            print(f"Error guardando datos: {e}")
            self.notify(f"❌ Error al guardar: {e}", severity="error", timeout=3)
        
    def load_data(self) -> None:
        try:
            if self.data_file.exists():
                data = json.loads(self.data_file.read_text(encoding='utf-8'))
                self.next_task_id = data.get("next_task_id", 1)
                self.next_group_id = data.get("next_group_id", 1)
                self.next_tag_id = data.get("next_tag_id", 1)
                self.next_subtask_id = data.get("next_subtask_id", 1)
                self.next_note_id = data.get("next_note_id", 1)
                self.next_canvas_id = data.get("next_canvas_id", 1)
                self.next_voice_note_id = data.get("next_voice_note_id", 1)
                self.groups = [Group(id=g["id"], name=g["name"]) for g in data.get("groups", [])]
                self.tags = [Tag(id=t["id"], name=t["name"], created_at=t.get("created_at", "")) for t in data.get("tags", [])]
                self.notes = [Note(
                    id=n["id"],
                    title=n.get("title", ""),
                    description=n.get("description", ""),
                    url=n.get("url"),
                    image_path=n.get("image_path"),
                    file_path=n.get("file_path"),
                    created_at=n.get("created_at", ""),
                    tags=n.get("tags", [])
                ) for n in data.get("notes", [])]
                self.canvas_list = [Canvas(
                    id=c["id"],
                    title=c.get("title", ""),
                    width=c.get("width", 50),
                    height=c.get("height", 20),
                    grid=c.get("grid", [[" " for _ in range(c.get("width", 50))] for _ in range(c.get("height", 20))]),
                    created_at=c.get("created_at", ""),
                    tags=c.get("tags", [])
                ) for c in data.get("canvas", [])]
                self.voice_notes = [VoiceNote(
                    id=v["id"],
                    title=v.get("title", ""),
                    audio_path=v.get("audio_path", ""),
                    description=v.get("description", ""),
                    duration=v.get("duration", 0.0),
                    created_at=v.get("created_at", ""),
                    tags=v.get("tags", [])
                ) for v in data.get("voice_notes", [])]
                self.tasks = []
                for t in data.get("tasks", []):
                    comments = [Comment(id=c["id"], title=c.get("title", c.get("text", "")),
                                    description=c.get("description", ""),
                                    url=c.get("url"), image_path=c.get('image_path'),
                                    file_path=c.get('file_path'), created_at=c.get("created_at", ""))
                            for c in t.get("comments", [])]
                    
                    subtasks = []
                    for s in t.get("subtasks", []):
                        subtask_comments = [Comment(
                            id=c["id"],
                            title=c.get("title", c.get("text", "")),
                            description=c.get("description", ""),
                            url=c.get("url"),
                            image_path=c.get("image_path"),
                            file_path=c.get("file_path"),
                            created_at=c.get("created_at", "")
                        ) for c in s.get("comments", [])]
                        
                        subtask = Subtask(
                            id=s["id"],
                            text=s["text"],
                            done=s.get("done", False),
                            status=s.get("status", "Completado" if s.get("done", False) else "En progreso"),
                            created_at=s.get("created_at", ""),
                            due_date=s.get("due_date"),
                            comments=subtask_comments,
                            tags=s.get("tags", []),
                            priority=s.get("priority", 0)
                        )
                        subtasks.append(subtask)
                    
                    task_notes = [Note(
                        id=n["id"],
                        title=n.get("title", ""),
                        description=n.get("description", ""),
                        url=n.get("url"),
                        image_path=n.get("image_path"),
                        file_path=n.get("file_path"),
                        created_at=n.get("created_at", ""),
                        tags=n.get("tags", [])
                    ) for n in t.get("notes", [])]

                    task_voice_notes = [VoiceNote(
                        id=v["id"],
                        title=v.get("title", ""),
                        audio_path=v.get("audio_path", ""),
                        description=v.get("description", ""),
                        duration=v.get("duration", 0.0),
                        created_at=v.get("created_at", ""),
                        tags=v.get("tags", [])
                    ) for v in t.get("voice_notes", [])]

                    task_canvas_list = [Canvas(
                        id=c["id"],
                        title=c.get("title", ""),
                        width=c.get("width", 50),
                        height=c.get("height", 20),
                        grid=c.get("grid", [[" " for _ in range(c.get("width", 50))] for _ in range(c.get("height", 20))]),
                        created_at=c.get("created_at", "")
                    ) for c in t.get("canvas", [])]

                    task = Task(
                        id=t["id"], 
                        text=t["text"], 
                        done=t.get("done", False),
                        status=t.get("status", "Completado" if t.get("done", False) else "En progreso"),
                        created_at=t.get("created_at", ""), 
                        group_id=t.get("group_id"),
                        due_date=t.get("due_date"), 
                        comments=comments, 
                        tags=t.get("tags", []),
                        priority=t.get("priority", 0), 
                        subtasks=subtasks,
                        notes=task_notes,
                        voice_notes=task_voice_notes,
                        canvas_list=task_canvas_list
                    )
                    self.tasks.append(task)
        except Exception as e:
            self.tasks, self.groups, self.tags, self.notes, self.canvas_list = [], [], [], [], []
            self.next_task_id = self.next_group_id = self.next_tag_id = self.next_subtask_id = self.next_note_id = self.next_canvas_id = 1
    
    def check_konami_code(self, key: str) -> None:
        self.konami_sequence.append(key)
        
        if len(self.konami_sequence) > 10:
            self.konami_sequence.pop(0)
        
        if self.konami_sequence == self.konami_code:
            self.konami_sequence = []
            try:
                webbrowser.open("https://www.yout-ube.com/watch?v=dQw4w9WgXcQ")
            except:
                self.notify("🎮 Konami Code detected but couldn't open browser", severity="warning", timeout=3)
    
    def action_edit_day(self) -> None:
        if not self.calendar_mode:
            return
        
        selected_date = f"{self.cal_year:04d}-{self.cal_month:02d}-{self.cal_day:02d}"
        date_display = f"{self.cal_day}/{self.cal_month}/{self.cal_year}"
        
        has_items = any(
            t.due_date == selected_date or
            any(st.due_date == selected_date for st in t.subtasks)
            for t in self.tasks
        )
        
        if not has_items:
            self.notify("No hay tareas ni subtareas en este día", severity="information", timeout=2)
            return
        
        async def on_result(result: Optional[dict]) -> None:
            if result:
                self._save_undo_state()
                
                task_ids = result.get("task_ids", [])
                subtask_selections = result.get("subtask_selections", [])
                
                for task in self.tasks:
                    if task.id in task_ids:
                        task.due_date = None
                
                for task in self.tasks:
                    for subtask in task.subtasks:
                        if (task.id, subtask.id) in subtask_selections:
                            subtask.due_date = None
                
                count = len(task_ids) + len(subtask_selections)
                if count > 0:
                    self.save_data()
                    self.refresh_calendar()
                    self.update_stats()
                    self.notify(f"🗑️ {count} fecha(s) eliminada(s) (Ctrl+Z para deshacer)", 
                            severity="information", timeout=2)
        
        self.push_screen(EditDayItemsModal(self.tasks, self.groups, selected_date), on_result)
    
    def action_clear_day(self) -> None:
        if not self.calendar_mode:
            return
        
        selected_date = f"{self.cal_year:04d}-{self.cal_month:02d}-{self.cal_day:02d}"
        date_display = f"{self.cal_day}/{self.cal_month}/{self.cal_year}"
        
        task_count = sum(1 for t in self.tasks if t.due_date == selected_date)
        subtask_count = sum(
            1 for t in self.tasks 
            for st in t.subtasks 
            if st.due_date == selected_date
        )
        total_count = task_count + subtask_count
        
        if total_count == 0:
            self.notify("No hay tareas ni subtareas en este día", severity="information", timeout=2)
            return
        
        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                
                for task in self.tasks:
                    if task.due_date == selected_date:
                        task.due_date = None
                    
                    for subtask in task.subtasks:
                        if subtask.due_date == selected_date:
                            subtask.due_date = None
                
                self.save_data()
                self.refresh_calendar()
                self.update_stats()
                self.notify(f"🗑️ {total_count} fecha(s) eliminada(s) del {date_display} (Ctrl+Z para deshacer)", 
                        severity="information", timeout=2)
        
        self.push_screen(
            ConfirmModal(f"¿Vaciar el {date_display}?\n({task_count} tareas, {subtask_count} subtareas)"),
            on_confirm
        )
    
    def action_add_tag(self) -> None:
        async def on_result(name: Optional[str]) -> None:
            if name:
                self._save_undo_state()
                new_id = max([t.id for t in self.tags], default=0) + 1
                self.next_tag_id = max(self.next_tag_id, new_id + 1)
                tag = Tag(id=new_id, name=name)
                self.tags.append(tag)
                self.save_data()
                await self.refresh_view()
                self.notify("✅ Etiqueta creada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(InputModal("Nueva Etiqueta", placeholder="Nombre de la etiqueta..."), on_result)

    def action_edit_tag(self, target_tag: Tag = None) -> None:
        if target_tag:
            tag = target_tag
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "tag": tag = item[1]
            else: return
        elif self.current_group_id == self.TAGS_GROUP_ID:
            tags = self._get_filtered_tags()
            if not tags or self.selected_index >= len(tags): return
            tag = tags[self.selected_index]
        else:
            return

        async def on_result(name: Optional[str]) -> None:
            if name:
                self._save_undo_state()
                tag.name = name
                self.save_data()
                await self.refresh_view()
                self.notify("✅ Etiqueta actualizada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(InputModal("Editar Etiqueta", initial_text=tag.name), on_result)

    def action_delete_tag(self, target_tag: Tag = None) -> None:
        if target_tag:
            tag = target_tag
        elif self.current_group_id == self.GENERAL_GROUP_ID:
            item = self._get_selected_general_item()
            if item and item[0] == "tag": tag = item[1]
            else: return
        elif self.current_group_id == self.TAGS_GROUP_ID:
            tags = self._get_filtered_tags()
            if not tags or self.selected_index >= len(tags): return
            tag = tags[self.selected_index]
        else:
            return

        async def on_confirm(yes: bool) -> None:
            if yes:
                self._save_undo_state()
                self.tags.remove(tag)
                for t in self.tasks:
                    if tag.id in t.tags: t.tags.remove(tag.id)
                for n in self.notes:
                    if tag.id in n.tags: n.tags.remove(tag.id)
                for v in self.voice_notes:
                    if tag.id in v.tags: v.tags.remove(tag.id)
                for c in self.canvas_list:
                    if tag.id in c.tags: c.tags.remove(tag.id)
                self.save_data()
                await self.refresh_view()
                self.notify("🗑️ Etiqueta eliminada (Ctrl+Z para deshacer)", severity="information", timeout=2)

        self.push_screen(ConfirmModal(f"¿Eliminar etiqueta '{tag.name}'?"), on_confirm)

    def action_open_snake(self) -> None:
        if self.main_search_focused:
            return
        self.push_screen(SnakeModal())

    def on_key(self, event) -> None:
        if event.key.lower() == "ctrl+g":
            event.prevent_default()
            event.stop()
            self.action_open_snake()
            return
        if event.key.lower() == "ctrl+t":
            event.prevent_default()
            event.stop()
            self.action_open_clock()
            return
        if self.main_search_focused:
            if event.key == "tab":
                event.prevent_default()
                event.stop()
                self.action_blur_main_search()
            return
        key = event.key
        if key in ["up", "down", "left", "right"]:
            self.check_konami_code(key)
        elif key == "b":
            self.check_konami_code("b")
        elif key == "a":
            self.check_konami_code("a")
    
def main():
    TodoApp().run()

if __name__ == "__main__":
    main()  
