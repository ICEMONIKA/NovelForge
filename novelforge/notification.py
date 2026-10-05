from __future__ import annotations

import os
import sys
from pathlib import Path


class NotificationManager:
    """完成/确认/失败提示：Windows 用 winsound，其它平台优先 QSoundEffect，失败则系统 beep。"""
    def __init__(self, parent, cfg, sound_dir: Path):
        self.parent = parent
        self.cfg = cfg
        self.sound_dir = Path(sound_dir)
        self.sound_dir.mkdir(parents=True, exist_ok=True)
        self.tray = None
        self._effects = []
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            from PySide6.QtGui import QIcon
            if QSystemTrayIcon.isSystemTrayAvailable():
                self.tray = QSystemTrayIcon(QIcon(), parent)
                self.tray.setToolTip('NovelForge')
                self.tray.show()
        except Exception:
            self.tray = None

    def notify(self, title: str, message: str, level='success'):
        if self.cfg.notify_sound:
            self.play(level)
        if self.cfg.notify_system and self.tray:
            try:
                from PySide6.QtWidgets import QSystemTrayIcon
                icon = {'error': QSystemTrayIcon.Critical, 'warning': QSystemTrayIcon.Warning}.get(level, QSystemTrayIcon.Information)
                self.tray.showMessage(title, message, icon, 6000)
            except Exception:
                pass
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.alert(self.parent, 1200)
        except Exception:
            pass

    def play(self, level='success'):
        filename = {'success':'completed.wav','warning':'confirm.wav','error':'error.wav','cancelled':'cancelled.wav'}.get(level,'completed.wav')
        path = self.sound_dir / filename
        if not path.exists():
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.beep()
            except Exception:
                pass
            return
        if sys.platform.startswith('win'):
            try:
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except Exception:
                pass
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect
            effect = QSoundEffect(self.parent)
            effect.setSource(QUrl.fromLocalFile(str(path)))
            effect.setVolume(max(0.0, min(1.0, float(self.cfg.notify_volume))))
            effect.play()
            self._effects.append(effect)
            effect.playbackStateChanged.connect(lambda e=effect: self._cleanup_effect(e))
            return
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        except Exception:
            pass

    def _cleanup_effect(self, effect):
        try:
            if effect.playbackState() == effect.PlaybackState.StoppedState:
                if effect in self._effects:self._effects.remove(effect)
                effect.deleteLater()
        except Exception:
            pass
