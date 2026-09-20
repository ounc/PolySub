# -*- coding: utf-8 -*-
"""
PolySub - Cinema-grade Real-time Dual-language Subtitle & Translation Tool for Windows
Author: ounc (https://github.com/ounc/PolySub)
Copyright (C) 2026 ounc and PolySub Authors.
License: GNU General Public License v3.0 (GPL-3.0)
SPDX-License-Identifier: GPL-3.0-or-later
"""

import sys
import os
import time
import datetime
import threading
import queue
import re
import urllib.request
import urllib.parse
import json

APP_DIR = os.path.dirname(os.path.abspath(__file__))

log_dir = os.path.join(APP_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)
if sys.stdout is None:
    sys.stdout = open(os.path.join(log_dir, "stdout.log"), "a", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = open(os.path.join(log_dir, "stderr.log"), "a", encoding="utf-8", buffering=1)


portable_lt = os.path.join(APP_DIR, "LiveTranslate")
if os.path.exists(portable_lt):
    LIVETRANSLATE_DIR = portable_lt
else:
    LIVETRANSLATE_DIR = r"C:\Users\uovc\AppData\Local\Programs\LiveTranslate\LiveTranslate"

if LIVETRANSLATE_DIR not in sys.path:
    sys.path.insert(0, LIVETRANSLATE_DIR)

portable_models = os.path.join(APP_DIR, "models")
if os.path.exists(portable_models):
    os.environ["MODELSCOPE_CACHE"] = portable_models
elif os.path.exists(os.path.join(LIVETRANSLATE_DIR, "models", "modelscope")):
    os.environ["MODELSCOPE_CACHE"] = os.path.join(LIVETRANSLATE_DIR, "models", "modelscope")

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QPoint, QSize
from PyQt6.QtGui import QFont, QColor, QCursor, QAction, QIcon
import ctypes
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QMessageBox, QDialog, QTabWidget,
    QLineEdit, QTextEdit, QSlider, QCheckBox, QComboBox, QGroupBox,
    QFormLayout, QScrollArea, QStackedWidget, QGraphicsDropShadowEffect
)

import numpy as np
import pyaudiowpatch as pyaudio
# AutoModel lazy imported inside AudioWorker.run()

# Portable Config & Transcripts Path
local_cfg = os.path.join(APP_DIR, "setting.json")
appdata_cfg = os.path.expanduser(r"~\AppData\Local\Programs\PolySub\setting.json")
old_appdata_cfg = os.path.expanduser(r"~\AppData\Local\Programs\AAI-LiveTrans\setting.json")
CONFIG_PATH = local_cfg if os.path.exists(local_cfg) else (appdata_cfg if os.path.exists(appdata_cfg) else (old_appdata_cfg if os.path.exists(old_appdata_cfg) else local_cfg))

TRANSCRIPTS_DIR = os.path.join(APP_DIR, "transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

THEMES = {
    "dark": {
        "name": "经典暗黑 (高对比白/蓝)",
        "bg": "14, 14, 16",
        "zh": "#ffffff",
        "en": "#d8e2ec",
        "badge": "#58a6ff"
    },
    "yellow": {
        "name": "高对比荧光黄 (清晰显眼)",
        "bg": "10, 10, 12",
        "zh": "#ffea60",
        "en": "#f0f6fc",
        "badge": "#ffc107"
    },
    "cyan": {
        "name": "清爽冰蓝 (柔和醒目)",
        "bg": "10, 20, 30",
        "zh": "#79c0ff",
        "en": "#f0f6fc",
        "badge": "#388bfd"
    },
    "green": {
        "name": "护眼翠绿 (鲜明清爽)",
        "bg": "12, 22, 16",
        "zh": "#7ee787",
        "en": "#f0f6fc",
        "badge": "#56d364"
    }
}

DIRECTIONS = {
    "EN_TO_ZH": {
        "label": "英 ➔ 中",
        "full_name": "🇬🇧 英语 ➔ 🇨🇳 中文",
        "deepl_target": "ZH",
        "google_source": "en",
        "google_target": "zh-CN",
        "mymemory_pair": "en|zh-CN",
        "prompt": "Translate English to fluent oral Chinese:"
    },
    "ZH_TO_EN": {
        "label": "中 ➔ 英",
        "full_name": "🇨🇳 中文 ➔ 🇬🇧 英语",
        "deepl_target": "EN",
        "google_source": "zh-CN",
        "google_target": "en",
        "mymemory_pair": "zh-CN|en",
        "prompt": "Translate Chinese to fluent oral English:"
    },
    "AUTO_TO_ZH": {
        "label": "自动 ➔ 中",
        "full_name": "🌐 自动检测 ➔ 🇨🇳 中文",
        "deepl_target": "ZH",
        "google_source": "auto",
        "google_target": "zh-CN",
        "mymemory_pair": "auto|zh-CN",
        "prompt": "Translate this into natural oral Chinese:"
    },
    "AUTO_TO_EN": {
        "label": "自动 ➔ 英",
        "full_name": "🌐 自动检测 ➔ 🇬🇧 英语",
        "deepl_target": "EN",
        "google_source": "auto",
        "google_target": "en",
        "mymemory_pair": "auto|en",
        "prompt": "Translate this into natural oral English:"
    },
    "JA_TO_ZH": {
        "label": "日 ➔ 中",
        "full_name": "🇯🇵 日语 ➔ 🇨🇳 中文",
        "deepl_target": "ZH",
        "google_source": "ja",
        "google_target": "zh-CN",
        "mymemory_pair": "ja|zh-CN",
        "prompt": "Translate Japanese to natural oral Chinese:"
    }
}

DEFAULT_CONFIG = {
    "ApiName": "Google", # Default to working Google / MyMemory
    "TargetLanguage": "zh-CN",
    "TransDirection": "EN_TO_ZH",
    "AsrSource": "SenseVoice",
    "Prompt": "Translate this sentence into natural oral Chinese. Only output translation:",
    "DeepL": {
        "ApiKey": "",
        "ApiUrl": "https://api-free.deepl.com/v2/translate"
    },
    "Ollama": {
        "ApiUrl": "http://127.0.0.1:11434",
        "ModelName": "qwen2.5:7b"
    },
    "OpenAI": {
        "ApiKey": "",
        "ApiUrl": "https://api.siliconflow.cn/v1",
        "ModelName": "Qwen/Qwen2.5-7B-Instruct"
    },
    "Overlay": {
        "FontSize": 16,
        "Opacity": 88,
        "DisplaySentences": 2,
        "Theme": "dark",
        "ShowLatency": True,
        "Topmost": True,
        "CaptionLayout": "ZH_TOP",
        "AlwaysShowToolbar": False
    }
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg = json.loads(json.dumps(DEFAULT_CONFIG))
                cfg.update(data)
                if "Overlay" not in cfg:
                    cfg["Overlay"] = {}
                if "CaptionLayout" not in cfg["Overlay"]:
                    cfg["Overlay"]["CaptionLayout"] = "ZH_TOP"
                if "AlwaysShowToolbar" not in cfg["Overlay"]:
                    cfg["Overlay"]["AlwaysShowToolbar"] = False
                if "FontSize" not in cfg["Overlay"] or cfg["Overlay"]["FontSize"] < 14:
                    cfg["Overlay"]["FontSize"] = 16
                return cfg
        except Exception:
            pass
    # Save default if not exists
    save_config(DEFAULT_CONFIG)
    return json.loads(json.dumps(DEFAULT_CONFIG))

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save config err:", e)

# ----------------- Translation Query -----------------
def translate_query(text, cfg):
    t0 = time.time()
    api = cfg.get("ApiName", "Google")
    dir_key = cfg.get("TransDirection", "EN_TO_ZH")
    d_info = DIRECTIONS.get(dir_key, DIRECTIONS["EN_TO_ZH"])
    prompt = d_info.get("prompt", cfg.get("Prompt", "Translate:"))
    
    # 1. Ollama
    if api == "Ollama":
        try:
            url = f"{cfg['Ollama']['ApiUrl'].rstrip('/')}/api/generate"
            payload = {
                "model": cfg['Ollama']['ModelName'],
                "prompt": f"{prompt}\n{text}",
                "stream": False
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                res_zh = data.get("response", "").strip()
                if res_zh:
                    return res_zh, int((time.time() - t0) * 1000)
        except Exception as e:
            print("Ollama err:", e)

    # 2. OpenAI / SiliconFlow
    if api == "OpenAI" and cfg['OpenAI'].get('ApiKey'):
        try:
            url = f"{cfg['OpenAI']['ApiUrl'].rstrip('/')}/chat/completions"
            payload = {
                "model": cfg['OpenAI']['ModelName'],
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ]
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={
                'Authorization': f"Bearer {cfg['OpenAI']['ApiKey']}",
                'Content-Type': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                zh = data['choices'][0]['message']['content'].strip()
                if zh:
                    return zh, int((time.time() - t0) * 1000)
        except Exception as e:
            print("OpenAI err:", e)

    # 3. DeepL
    if api == "DeepL" and cfg['DeepL'].get('ApiKey'):
        try:
            url = cfg['DeepL'].get('ApiUrl', 'https://api-free.deepl.com/v2/translate')
            target_lang = d_info.get("deepl_target", "ZH")
            data = urllib.parse.urlencode({'text': text, 'target_lang': target_lang}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={
                'Authorization': f"DeepL-Auth-Key {cfg['DeepL']['ApiKey']}",
                'User-Agent': 'Mozilla/5.0'
            })
            with urllib.request.urlopen(req, timeout=4) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                return res['translations'][0]['text'], int((time.time() - t0) * 1000)
        except Exception as e:
            print("DeepL err:", e)

    # 4. Google Free
    try:
        sl = d_info.get("google_source", "en")
        tl = d_info.get("google_target", "zh-CN")
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q=" + urllib.parse.quote(text)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            zh = "".join([part[0] for part in data[0] if part[0]])
            if zh:
                return zh, int((time.time() - t0) * 1000)
    except Exception:
        pass

    # 5. MyMemory Free Fallback
    try:
        pair = d_info.get("mymemory_pair", "en|zh-CN")
        url = f"https://api.mymemory.translated.net/get?q=" + urllib.parse.quote(text) + f"&langpair={pair}"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            zh = data['responseData']['translatedText']
            if zh and zh != text:
                return zh, int((time.time() - t0) * 1000)
    except Exception:
        pass

    return text, int((time.time() - t0) * 1000)

# ----------------- Audio & ASR Thread -----------------
class AudioWorker(threading.Thread):
    def __init__(self, callback, config_supplier):
        super().__init__(daemon=True)
        self.callback = callback
        self.config_supplier = config_supplier
        self.running = True
        self.paused = False
        self.model = None
        self.p = None
        self.stream = None

    def stop(self):
        self.running = False
        self.paused = True
        if self.stream is not None:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.p is not None:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

    def set_paused(self, paused):
        self.paused = paused
        if paused:
            if self.stream is not None:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            if self.p is not None:
                try:
                    self.p.terminate()
                except Exception:
                    pass
                self.p = None
        else:
            self.ensure_stream()

    def ensure_stream(self):
        try:
            if self.p is None:
                self.p = pyaudio.PyAudio()
            if self.stream is None:
                self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
        except Exception as e:
            print("Mic open err:", e)
            self.stream = None

    def run(self):
        portable_root = os.path.dirname(APP_DIR)
        local_m1 = os.path.join(APP_DIR, "models", "SenseVoiceSmall")
        local_m2 = os.path.join(portable_root, "models", "SenseVoiceSmall")
        cache_path = os.path.expanduser(r"~\.cache\modelscope\models\iic--SenseVoiceSmall\snapshots\master")
        lt_model = os.path.join(LIVETRANSLATE_DIR, "models", "SenseVoiceSmall")
        if os.path.exists(local_m2):
            model_target = local_m2
        elif os.path.exists(local_m1):
            model_target = local_m1
        elif os.path.exists(lt_model):
            model_target = lt_model
        elif os.path.exists(cache_path):
            model_target = cache_path
        else:
            model_target = "iic/SenseVoiceSmall"
        try:
            from funasr import AutoModel
            self.model = AutoModel(model=model_target, trust_remote_code=True, disable_update=True, device="cpu")
        except Exception as e:
            print("Model load err:", e)

        self.ensure_stream()

        audio_buffer = []
        silence_chunks = 0

        while self.running:
            if self.paused:
                time.sleep(0.2)
                continue
            if self.stream is None:
                self.ensure_stream()
                if self.stream is None:
                    time.sleep(0.5)
                    continue
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
            except Exception:
                time.sleep(0.1)
                continue

            audio_data = np.frombuffer(data, dtype=np.int16)
            energy = np.abs(audio_data).mean()

            if energy > 250:
                audio_buffer.extend(audio_data)
                silence_chunks = 0
            else:
                if len(audio_buffer) > 0:
                    audio_buffer.extend(audio_data)
                    silence_chunks += 1
                    if silence_chunks >= 8:
                        if len(audio_buffer) >= 16000 * 0.6:
                            segment = np.array(audio_buffer, dtype=np.int16)
                            self.process(segment)
                        audio_buffer = []
                        silence_chunks = 0

            if len(audio_buffer) > 16000 * 7:
                segment = np.array(audio_buffer, dtype=np.int16)
                self.process(segment)
                audio_buffer = []
                silence_chunks = 0

        self.stop()

    def process(self, audio_data):
        if self.model is None:
            return
        try:
            float_data = audio_data.astype(np.float32) / 32768.0
            res = self.model.generate(input=float_data, language="auto", use_itn=True)
            if res and len(res) > 0:
                raw_text = res[0].get("text", "")
                clean_en = re.sub(r'<\|[^|]+\|>', '', raw_text).strip()
                if clean_en and len(clean_en) >= 2:
                    cfg = self.config_supplier()
                    zh_trans, latency = translate_query(clean_en, cfg)
                    now_str = datetime.datetime.now().strftime("%H:%M:%S")
                    self.callback(now_str, clean_en, zh_trans, latency)
        except Exception as e:
            print("Process err:", e)


# ----------------- Windows 11 LiveCaptions UI Automation Worker -----------------
class LiveCaptionsWorker(threading.Thread):
    def __init__(self, callback, config_supplier, interim_callback=None):
        super().__init__(daemon=True)
        self.callback = callback
        self.config_supplier = config_supplier
        self.interim_callback = interim_callback
        self.running = True
        self.paused = False
        self.committed_text = ""

    def stop(self):
        self.running = False
        self.paused = True

    def set_paused(self, paused):
        self.paused = paused

    def run(self):
        last_seen = ""
        last_change_time = time.time()

        while self.running:
            if self.paused:
                time.sleep(0.3)
                continue

            try:
                import uiautomation as auto
                wnd = auto.WindowControl(searchDepth=3, ClassName="LiveCaptionsDesktopWindow")
                if not wnd.Exists(0.1):
                    time.sleep(0.8)
                    continue

                # Auto-heal: If LiveCaptions-Translator hid the window off-screen at (-25600, -25600) or 0x0
                try:
                    hwnd = wnd.NativeWindowHandle
                    if hwnd:
                        rect = (ctypes.c_long * 4)()
                        ctypes.windll.user32.GetWindowRect(hwnd, rect)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if rect[0] < -1000 or rect[1] < -1000 or w < 60 or h < 30:
                            ctypes.windll.user32.SetWindowPos(hwnd, 0, 450, 60, 680, 160, 0x0040)
                            ctypes.windll.user32.ShowWindow(hwnd, 5)
                except Exception:
                    pass

                texts = []
                for child, depth in auto.WalkControl(wnd, maxDepth=6):
                    if child.ControlTypeName in ["TextControl", "DocumentControl"]:
                        auto_id = child.AutomationId
                        if auto_id in ["ReadyToCaptionTextBlock", "SettingsButton", "CloseButton"]:
                            continue
                        name = child.Name or getattr(child, 'Value', '')
                        if name and not name.startswith("准备好") and name not in ["设置", "关闭", "关闭实时字幕窗口"]:
                            texts.append(name.strip())

                raw_all = " ".join(texts).strip()

                if raw_all != last_seen:
                    last_seen = raw_all
                    last_change_time = time.time()

                # Text buffer roll-over reset
                if len(raw_all) < len(self.committed_text):
                    self.committed_text = ""

                if raw_all and len(raw_all) > len(self.committed_text):
                    pending = raw_all[len(self.committed_text):].strip()
                    if pending and self.interim_callback:
                        self.interim_callback(pending)

                    match = re.search(r'([.?!。？！\n])\s*', pending)
                    if match:
                        end_pos = match.end()
                        sentence = pending[:end_pos].strip()
                        self.committed_text = raw_all[:len(self.committed_text) + end_pos].strip()
                        if len(sentence) >= 2:
                            cfg = self.config_supplier()
                            zh_trans, latency = translate_query(sentence, cfg)
                            now_str = datetime.datetime.now().strftime("%H:%M:%S")
                            self.callback(now_str, sentence, zh_trans, latency)

                    elif (time.time() - last_change_time > 1.6) and len(pending.split()) >= 3:
                        sentence = pending.strip()
                        self.committed_text = raw_all
                        if len(sentence) >= 2:
                            cfg = self.config_supplier()
                            zh_trans, latency = translate_query(sentence, cfg)
                            now_str = datetime.datetime.now().strftime("%H:%M:%S")
                            self.callback(now_str, sentence, zh_trans, latency)

                time.sleep(0.25)
            except Exception as e:
                time.sleep(0.5)

# ----------------- Settings Dialog (功能设置二级页面) -----------------
class SettingsDialog(QDialog):
    def __init__(self, parent, config, records, on_saved_callback, initial_tab=0):
        super().__init__(parent)
        self.config = json.loads(json.dumps(config))
        self.records = records
        self.on_saved_callback = on_saved_callback
        self.initial_tab = initial_tab
        self.setWindowTitle("⚙️ PolySub - 功能设置")
        app_dir = os.path.dirname(os.path.abspath(__file__))
        ico_file = os.path.join(app_dir, "app.ico")
        if os.path.exists(ico_file):
            self.setWindowIcon(QIcon(ico_file))
        self.resize(680, 520)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #c9d1d9;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                border-radius: 8px;
                background-color: #161b22;
                padding: 12px;
            }
            QTabBar::tab {
                background: #21262d;
                color: #8b949e;
                padding: 8px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #161b22;
                color: #58a6ff;
                border-bottom: 2px solid #58a6ff;
            }
            QLabel {
                color: #c9d1d9;
                font-size: 12px;
            }
            QLineEdit, QTextEdit {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #f0f6fc;
                padding: 5px 8px;
                font-family: 'Consolas', 'Microsoft YaHei UI';
            }
            QComboBox {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #ffffff;
                padding: 6px 12px;
                font-size: 13px;
                font-family: 'Microsoft YaHei UI';
            }
            QComboBox:hover {
                border-color: #58a6ff;
            }
            QComboBox QAbstractItemView {
                background-color: #1c2128;
                border: 1px solid #444c56;
                border-radius: 6px;
                color: #ffffff;
                selection-background-color: #1f6feb;
                selection-color: #ffffff;
                padding: 4px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 6px 12px;
                color: #ffffff;
                background-color: #1c2128;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #30363d;
                color: #ffffff;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #8b949e;
                margin-right: 8px;
            }
            QGroupBox {
                border: 1px solid #30363d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                font-weight: bold;
                color: #58a6ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
            QCheckBox {
                color: #c9d1d9;
            }
        """)

        tabs = QTabWidget()

        # Tab 1: 翻译引擎 (Translate API)
        tab_api = QWidget()
        layout_api = QVBoxLayout(tab_api)
        layout_api.setSpacing(10)

                # ASR Source Selection Row
        row_src = QHBoxLayout()
        lbl_s = QLabel("语音识别/听写来源:")
        lbl_s.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        row_src.addWidget(lbl_s)

        self.combo_source = QComboBox()
        self.combo_source.addItem("🧠 本地 SenseVoice AI 模型 (麦克风直采)", "SenseVoice")
        self.combo_source.addItem("🪟 Windows 11 自带实时字幕 (低内存/不锁麦)", "LiveCaptions")
        cur_s = self.config.get("AsrSource", "SenseVoice")
        self.combo_source.setCurrentIndex(1 if cur_s == "LiveCaptions" else 0)
        row_src.addWidget(self.combo_source, stretch=1)
        layout_api.addLayout(row_src)

        # Direction Selection Row
        row_dir = QHBoxLayout()
        lbl_d = QLabel("当前翻译方向:")
        lbl_d.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        row_dir.addWidget(lbl_d)

        self.combo_direction = QComboBox()
        cur_d = self.config.get("TransDirection", "EN_TO_ZH")
        for k, v in DIRECTIONS.items():
            self.combo_direction.addItem(v["full_name"], k)
        dir_idx = list(DIRECTIONS.keys()).index(cur_d) if cur_d in DIRECTIONS else 0
        self.combo_direction.setCurrentIndex(dir_idx)
        row_dir.addWidget(self.combo_direction, stretch=1)
        layout_api.addLayout(row_dir)

        # Engine Selection Row
        row_engine = QHBoxLayout()
        lbl_e = QLabel("当前首选翻译引擎:")
        lbl_e.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        row_engine.addWidget(lbl_e)

        self.combo_engine = QComboBox()
        self.combo_engine.addItems(["Google", "DeepL", "Ollama", "OpenAI"])
        self.combo_engine.setCurrentText(self.config.get("ApiName", "Google"))
        row_engine.addWidget(self.combo_engine, stretch=1)
        layout_api.addLayout(row_engine)

        # Dynamic Engine Details Stack
        self.engine_stack = QStackedWidget()

        # 0: Google Page
        page_google = QWidget()
        l_g = QVBoxLayout(page_google)
        lbl_g_info = QLabel("🟢 Google / MyMemory 免费源\n\n• 优势：永久免配置、无需任何 API Key，开箱即用。\n• 机制：内置多线路自动容灾，网络异常自动无感切换。")
        lbl_g_info.setStyleSheet("color: #3fb950; font-size: 12px; line-height: 1.6; padding: 10px;")
        lbl_g_info.setWordWrap(True)
        l_g.addWidget(lbl_g_info)
        l_g.addStretch()
        self.engine_stack.addWidget(page_google)

        # 1: DeepL Page
        page_deepl = QWidget()
        l_d = QVBoxLayout(page_deepl)
        grp_deepl = QGroupBox("DeepL API (官方开发者)")
        f_d = QFormLayout(grp_deepl)
        self.txt_deepl_key = QLineEdit(self.config["DeepL"].get("ApiKey", ""))
        self.txt_deepl_url = QLineEdit(self.config["DeepL"].get("ApiUrl", ""))
        f_d.addRow("API Key:", self.txt_deepl_key)
        f_d.addRow("API Endpoint:", self.txt_deepl_url)
        
        btn_test_deepl = QPushButton("🔍 测试 DeepL 连接与额度")
        self.lbl_deepl_status = QLabel("")
        btn_test_deepl.clicked.connect(self.test_deepl)
        f_d.addRow(btn_test_deepl, self.lbl_deepl_status)
        l_d.addWidget(grp_deepl)
        l_d.addStretch()
        self.engine_stack.addWidget(page_deepl)

        # 2: Ollama Page
        page_ollama = QWidget()
        l_o = QVBoxLayout(page_ollama)
        grp_ollama = QGroupBox("Ollama (本地大模型/纯离线)")
        f_o = QFormLayout(grp_ollama)
        self.txt_ollama_url = QLineEdit(self.config["Ollama"].get("ApiUrl", "http://127.0.0.1:11434"))
        self.txt_ollama_model = QLineEdit(self.config["Ollama"].get("ModelName", "qwen2.5:7b"))
        f_o.addRow("服务地址 (ApiUrl):", self.txt_ollama_url)
        f_o.addRow("模型名称 (ModelName):", self.txt_ollama_model)

        btn_test_ollama = QPushButton("🔍 测试 Ollama 本地模型")
        self.lbl_ollama_status = QLabel("")
        btn_test_ollama.clicked.connect(self.test_ollama)
        f_o.addRow(btn_test_ollama, self.lbl_ollama_status)
        l_o.addWidget(grp_ollama)
        l_o.addStretch()
        self.engine_stack.addWidget(page_ollama)

        # 3: OpenAI / SiliconFlow Page
        page_openai = QWidget()
        l_oa = QVBoxLayout(page_openai)
        grp_openai = QGroupBox("OpenAI 兼容端点 (硅基流动 / 本地端点)")
        f_oa = QFormLayout(grp_openai)
        self.txt_openai_key = QLineEdit(self.config["OpenAI"].get("ApiKey", ""))
        self.txt_openai_url = QLineEdit(self.config["OpenAI"].get("ApiUrl", "https://api.siliconflow.cn/v1"))
        self.txt_openai_model = QLineEdit(self.config["OpenAI"].get("ModelName", "Qwen/Qwen2.5-7B-Instruct"))
        f_oa.addRow("API Key:", self.txt_openai_key)
        f_oa.addRow("Base URL:", self.txt_openai_url)
        f_oa.addRow("Model Name:", self.txt_openai_model)
        l_oa.addWidget(grp_openai)
        l_oa.addStretch()
        self.engine_stack.addWidget(page_openai)

        # Sync stack with combo
        engine_map = {"Google": 0, "DeepL": 1, "Ollama": 2, "OpenAI": 3}
        self.engine_stack.setCurrentIndex(engine_map.get(self.combo_engine.currentText(), 0))
        self.combo_engine.currentTextChanged.connect(lambda txt: self.engine_stack.setCurrentIndex(engine_map.get(txt, 0)))

        layout_api.addWidget(self.engine_stack)

        # Prompt
        form_prompt = QFormLayout()
        self.txt_prompt = QLineEdit(self.config.get("Prompt", ""))
        form_prompt.addRow("系统提示词 (Prompt):", self.txt_prompt)
        layout_api.addLayout(form_prompt)

        tabs.addTab(tab_api, "🌐 翻译引擎 (API)")

        # Tab 2: 悬浮外观 (Appearance & Overlay)
        tab_overlay = QWidget()
        layout_overlay = QVBoxLayout(tab_overlay)
        layout_overlay.setSpacing(14)

        form_disp = QFormLayout()

        # Caption Layout Mode (LiveCaptions-Translator 风格排版)
        self.combo_caption_layout = QComboBox()
        self.combo_caption_layout.addItem("🇨🇳 中文在上，英文在下 (ZH_TOP 推荐)", "ZH_TOP")
        self.combo_caption_layout.addItem("🇬🇧 英文在上，中文在下 (EN_TOP 精听)", "EN_TOP")
        self.combo_caption_layout.addItem("🇨🇳 仅显示中文译文 (ZH_ONLY 电影模式)", "ZH_ONLY")
        self.combo_caption_layout.addItem("🇬🇧 仅显示英文原文 (EN_ONLY 原声模式)", "EN_ONLY")
        cur_l = self.config["Overlay"].get("CaptionLayout", "ZH_TOP")
        layout_keys = ["ZH_TOP", "EN_TOP", "ZH_ONLY", "EN_ONLY"]
        self.combo_caption_layout.setCurrentIndex(layout_keys.index(cur_l) if cur_l in layout_keys else 0)
        form_disp.addRow("双语排版模式 (Layout):", self.combo_caption_layout)

        # Theme
        self.combo_theme = QComboBox()
        for k, v in THEMES.items():
            self.combo_theme.addItem(f"🎨 {v['name']}", k)
        current_thm = self.config["Overlay"].get("Theme", "dark")
        idx_thm = list(THEMES.keys()).index(current_thm) if current_thm in THEMES else 0
        self.combo_theme.setCurrentIndex(idx_thm)
        form_disp.addRow("主题配色 (Theme):", self.combo_theme)

        # Font size
        self.slider_font = QSlider(Qt.Orientation.Horizontal)
        self.slider_font.setRange(10, 24)
        self.slider_font.setValue(self.config["Overlay"].get("FontSize", 13))
        self.lbl_font_val = QLabel(f"{self.slider_font.value()} pt")
        self.slider_font.valueChanged.connect(lambda v: self.lbl_font_val.setText(f"{v} pt"))
        row_font = QHBoxLayout()
        row_font.addWidget(self.slider_font, stretch=1)
        row_font.addWidget(self.lbl_font_val)
        form_disp.addRow("字体大小 (Font Size):", row_font)

        # Opacity
        self.slider_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_op.setRange(40, 100)
        self.slider_op.setValue(self.config["Overlay"].get("Opacity", 88))
        self.lbl_op_val = QLabel(f"{self.slider_op.value()} %")
        self.slider_op.valueChanged.connect(lambda v: self.lbl_op_val.setText(f"{v} %"))
        row_op = QHBoxLayout()
        row_op.addWidget(self.slider_op, stretch=1)
        row_op.addWidget(self.lbl_op_val)
        form_disp.addRow("背景透明度 (Opacity):", row_op)

        # Sentences to retain
        self.combo_sentences = QComboBox()
        self.combo_sentences.addItems(["1 句 (极简紧凑)", "2 句 (标准胶囊)", "3 句 (多行滚动)", "4 句 (长篇回顾)", "6 句 (大段追溯)"])
        s_val = self.config["Overlay"].get("DisplaySentences", 2)
        s_idx = [1, 2, 3, 4, 6].index(s_val) if s_val in [1, 2, 3, 4, 6] else 1
        self.combo_sentences.setCurrentIndex(s_idx)
        form_disp.addRow("字幕保留行数 (Display):", self.combo_sentences)

        layout_overlay.addLayout(form_disp)

        self.chk_latency = QCheckBox("显示翻译延迟毫秒 Badge (如 [ 239 ms ])")
        self.chk_latency.setChecked(self.config["Overlay"].get("ShowLatency", True))
        layout_overlay.addWidget(self.chk_latency)

        self.chk_topmost = QCheckBox("悬浮卡片始终置顶 (Always on Top)")
        self.chk_topmost.setChecked(self.config["Overlay"].get("Topmost", True))
        layout_overlay.addWidget(self.chk_topmost)

        self.chk_always_toolbar = QCheckBox("📌 常驻固定控制栏 (取消勾选为沉浸式字幕，鼠标悬停时自动展现)")
        self.chk_always_toolbar.setChecked(self.config["Overlay"].get("AlwaysShowToolbar", False))
        layout_overlay.addWidget(self.chk_always_toolbar)

        layout_overlay.addStretch()
        tabs.addTab(tab_overlay, "🎨 悬浮外观 (Display)")

        # Tab 3: 历史记录 (History)
        tab_history = QWidget()
        layout_hist = QVBoxLayout(tab_history)
        layout_hist.setSpacing(10)

        # Toolbar
        bar_hist = QHBoxLayout()
        bar_hist.addWidget(QLabel("选择日期:"))
        self.combo_hist_date = QComboBox()
        bar_hist.addWidget(self.combo_hist_date)

        bar_hist.addWidget(QLabel("搜索:"))
        self.txt_hist_search = QLineEdit()
        self.txt_hist_search.setPlaceholderText("过滤中英关键字...")
        self.txt_hist_search.textChanged.connect(self.filter_history)
        bar_hist.addWidget(self.txt_hist_search, stretch=1)

        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(self.load_selected_history)
        bar_hist.addWidget(btn_refresh)

        btn_copy_all = QPushButton("📋 复制全部")
        btn_copy_all.clicked.connect(self.copy_history_text)
        bar_hist.addWidget(btn_copy_all)

        btn_open_folder = QPushButton("📂 打开文件夹")
        btn_open_folder.clicked.connect(lambda: os.startfile(TRANSCRIPTS_DIR))
        bar_hist.addWidget(btn_open_folder)

        layout_hist.addLayout(bar_hist)

        # Rich text display for history
        self.txt_history_display = QTextEdit()
        self.txt_history_display.setReadOnly(True)
        self.txt_history_display.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                color: #f0f6fc;
                font-family: 'Segoe UI', 'Microsoft YaHei UI';
                font-size: 13px;
                padding: 10px;
                line-height: 1.6;
            }
        """)
        layout_hist.addWidget(self.txt_history_display)

        self.lbl_hist_count = QLabel("")
        self.lbl_hist_count.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout_hist.addWidget(self.lbl_hist_count)

        self.combo_hist_date.currentIndexChanged.connect(self.load_selected_history)
        self.refresh_hist_dates()

        tabs.addTab(tab_history, "📜 历史记录")

        # Tab 4: 本地存放路径 (Paths & Storage)
        tab_paths = QWidget()
        layout_paths = QVBoxLayout(tab_paths)
        layout_paths.setSpacing(12)

        paths_data = [
            ("📝 课堂双语笔记存档目录 (Transcripts)", TRANSCRIPTS_DIR, "存放每日全量双语课堂转写文本 (transcript_YYYY-MM-DD.txt)，自动持久化存储。"),
            ("🧠 SenseVoice AI 语音模型目录 (Model Cache)", os.path.expanduser(r"~\.cache\modelscope\models\iic--SenseVoiceSmall"), "本地离线运行的语音识别模型权重文件（约 900MB），纯离线推理无需联网。"),
            ("⚙️ 软件配置与主程序目录 (App & Config)", os.path.expanduser(r"~\AppData\Local\Programs\PolySub"), "存放主程序 app.pyw 与用户功能设置文件 setting.json。"),
            ("📁 软件根工作目录 (App Root)", APP_DIR, "软件运行与数据存储主目录。"),
            ("🖥️ 桌面一键启动快捷方式 (Desktop Shortcut)", os.path.expanduser(r"~\Desktop\PolySub.lnk"), "双击即可秒开同传胶囊悬浮框的桌面图标文件。")
        ]

        scroll_paths = QScrollArea()
        scroll_paths.setWidgetResizable(True)
        scroll_paths.setStyleSheet("border: none; background-color: transparent;")
        container_paths = QWidget()
        l_c_paths = QVBoxLayout(container_paths)
        l_c_paths.setSpacing(10)

        for title, p_val, desc in paths_data:
            grp = QGroupBox(title)
            l_g = QVBoxLayout(grp)
            l_g.setSpacing(6)

            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("color: #8b949e; font-size: 11px;")
            lbl_d.setWordWrap(True)
            l_g.addWidget(lbl_d)

            row_p = QHBoxLayout()
            txt_p = QLineEdit(p_val)
            txt_p.setReadOnly(True)
            txt_p.setStyleSheet("background-color: #0d1117; color: #79c0ff; border: 1px solid #30363d; padding: 6px; font-family: 'Consolas';")
            row_p.addWidget(txt_p, stretch=1)

            btn_copy_p = QPushButton("📋 复制")
            btn_copy_p.setToolTip("复制该路径到剪贴板")
            btn_copy_p.setStyleSheet("""
                QPushButton {
                    background-color: #21262d;
                    color: #c9d1d9;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    padding: 6px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #30363d;
                    color: #ffffff;
                }
            """)
            btn_copy_p.clicked.connect(lambda _, p=p_val: self.copy_single_path(p))
            row_p.addWidget(btn_copy_p)

            btn_open_p = QPushButton("📂 打开")
            btn_open_p.setToolTip("在资源管理器中定位并打开该路径")
            btn_open_p.setStyleSheet("""
                QPushButton {
                    background-color: rgba(56, 139, 253, 0.2);
                    color: #58a6ff;
                    border: 1px solid rgba(56, 139, 253, 0.4);
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(56, 139, 253, 0.35);
                    color: #ffffff;
                }
            """)
            btn_open_p.clicked.connect(lambda _, p=p_val: self.open_local_path(p))
            row_p.addWidget(btn_open_p)

            l_g.addLayout(row_p)
            l_c_paths.addWidget(grp)

        l_c_paths.addStretch()
        scroll_paths.setWidget(container_paths)
        layout_paths.addWidget(scroll_paths)

        tabs.addTab(tab_paths, "📁 本地存放路径")

        if self.initial_tab > 0:
            tabs.setCurrentIndex(self.initial_tab)

        layout.addWidget(tabs)

        # Footer Buttons
        footer = QHBoxLayout()
        footer.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_save = QPushButton("💾 保存并应用设置")
        btn_save.setStyleSheet("background-color: #1f6feb; color: #ffffff; border: none; padding: 7px 18px;")
        btn_save.clicked.connect(self.save_and_apply)
        footer.addWidget(btn_save)

        layout.addLayout(footer)

    def copy_single_path(self, p):
        QApplication.clipboard().setText(p)
        QMessageBox.information(self, "已复制", f"已复制路径到剪贴板：\n{p}")

    def open_local_path(self, target_path):
        target = target_path
        if os.path.isfile(target):
            subprocess.run(["explorer.exe", f"/select,{target}"])
        elif os.path.exists(target):
            os.startfile(target)
        else:
            parent_dir = os.path.dirname(target)
            if os.path.exists(parent_dir):
                os.startfile(parent_dir)
            else:
                QMessageBox.warning(self, "路径不存在", f"无法找到该路径：\n{target}")

    def refresh_hist_dates(self):
        self.combo_hist_date.blockSignals(True)
        self.combo_hist_date.clear()
        self.combo_hist_date.addItem("📌 实时当前对话流 (Memory)")
        if os.path.exists(TRANSCRIPTS_DIR):
            files = sorted([f for f in os.listdir(TRANSCRIPTS_DIR) if f.startswith("transcript_") and f.endswith(".txt")], reverse=True)
            for f in files:
                dt_str = f.replace("transcript_", "").replace(".txt", "")
                self.combo_hist_date.addItem(f"📅 {dt_str}", f)
        self.combo_hist_date.blockSignals(False)
        self.load_selected_history()

    def load_selected_history(self):
        idx = self.combo_hist_date.currentIndex()
        self.current_parsed_history = []
        
        if idx == 0:
            for item in self.records:
                ts, en, zh, lat = item if len(item) == 4 else (item[0], item[1], item[2], 0)
                self.current_parsed_history.append((ts, en, zh))
        else:
            fname = self.combo_hist_date.currentData()
            fpath = os.path.join(TRANSCRIPTS_DIR, fname) if fname else None
            if fpath and os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                blocks = content.strip().split("\n\n")
                for b in blocks:
                    lines = b.strip().split("\n")
                    if len(lines) >= 2:
                        ts_m = re.match(r'\[(.*?)\]', lines[0])
                        ts = ts_m.group(1) if ts_m else ""
                        en = re.sub(r'^\[.*?\]\s*EN:\s*', '', lines[0]).strip()
                        zh = re.sub(r'^\[.*?\]\s*ZH:\s*', '', lines[1]).strip()
                        self.current_parsed_history.append((ts, en, zh))

        self.filter_history(self.txt_hist_search.text().strip())

    def filter_history(self, search_text=""):
        if not hasattr(self, 'current_parsed_history'):
            return
        kw = search_text.lower()
        matched = []
        for ts, en, zh in self.current_parsed_history:
            if not kw or kw in en.lower() or kw in zh.lower():
                matched.append((ts, en, zh))

        html_parts = []
        for ts, en, zh in matched:
            html_parts.append(f"""
            <div style='margin-bottom: 8px; padding: 6px 10px; background-color: #161b22; border-radius: 6px; border-left: 3px solid #1f6feb;'>
                <div style='color: #8b949e; font-size: 11px; font-weight: bold;'>⏱️ [{ts}]</div>
                <div style='color: #ffffff; font-size: 13px; font-weight: 600; margin-top: 2px;'>{en}</div>
                <div style='color: #58a6ff; font-size: 13px; margin-top: 2px;'>{zh}</div>
            </div>
            """)
        
        self.txt_history_display.setHtml("".join(html_parts) if html_parts else "<div style='color: #8b949e; text-align: center; padding: 30px;'>暂无匹配的历史记录</div>")
        self.lbl_hist_count.setText(f"共展示: {len(matched)} 句记录 / 当前源共 {len(self.current_parsed_history)} 句")

    def copy_history_text(self):
        if not hasattr(self, 'current_parsed_history') or not self.current_parsed_history:
            return
        lines = []
        for ts, en, zh in self.current_parsed_history:
            lines.append(f"[{ts}] EN: {en}\n[{ts}] ZH: {zh}\n")
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "已复制", f"🎉 已将全部 {len(self.current_parsed_history)} 句双语记录复制到剪贴板！")

    def test_deepl(self):
        k = self.txt_deepl_key.text().strip()
        self.lbl_deepl_status.setText("⏳ 正在测试连接...")
        def run():
            try:
                url = "https://api-free.deepl.com/v2/usage"
                req = urllib.request.Request(url, headers={'Authorization': f'DeepL-Auth-Key {k}'})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    d = json.loads(resp.read().decode('utf-8'))
                    cnt = d.get("character_count", 0)
                    lim = d.get("character_limit", 0)
                    if cnt >= lim:
                        QTimer.singleShot(0, lambda: self.lbl_deepl_status.setText(f"⚠️ 额度已用尽 ({cnt}/{lim})"))
                    else:
                        QTimer.singleShot(0, lambda: self.lbl_deepl_status.setText(f"✅ 正常 (已用: {cnt}/{lim})"))
            except Exception as e:
                msg = str(e)
                QTimer.singleShot(0, lambda: self.lbl_deepl_status.setText(f"❌ 报错: {msg}"))
        threading.Thread(target=run, daemon=True).start()

    def test_ollama(self):
        u = self.txt_ollama_url.text().strip()
        m = self.txt_ollama_model.text().strip()
        self.lbl_ollama_status.setText("⏳ 正在连接本地模型...")
        def run():
            try:
                url = f"{u.rstrip('/')}/api/tags"
                with urllib.request.urlopen(url, timeout=3) as resp:
                    d = json.loads(resp.read().decode('utf-8'))
                    models = [mod['name'] for mod in d.get('models', [])]
                    if any(m in mod for mod in models):
                        QTimer.singleShot(0, lambda: self.lbl_ollama_status.setText(f"✅ 连接成功，找到模型: {m}"))
                    else:
                        avail = ", ".join(models[:3]) if models else "无"
                        QTimer.singleShot(0, lambda: self.lbl_ollama_status.setText(f"⚠️ 服务正常但未找到 {m} (本地已有: {avail})"))
            except Exception as e:
                msg = str(e)
                QTimer.singleShot(0, lambda: self.lbl_ollama_status.setText(f"❌ 无法连接 Ollama: {msg}"))
        threading.Thread(target=run, daemon=True).start()

    def save_and_apply(self):
        self.config["ApiName"] = self.combo_engine.currentText()
        if hasattr(self, 'combo_direction'):
            self.config["TransDirection"] = self.combo_direction.currentData()
        self.config["Prompt"] = self.txt_prompt.text().strip()

        self.config["DeepL"]["ApiKey"] = self.txt_deepl_key.text().strip()
        self.config["DeepL"]["ApiUrl"] = self.txt_deepl_url.text().strip()

        self.config["Ollama"]["ApiUrl"] = self.txt_ollama_url.text().strip()
        self.config["Ollama"]["ModelName"] = self.txt_ollama_model.text().strip()

        self.config["OpenAI"]["ApiKey"] = self.txt_openai_key.text().strip()
        self.config["OpenAI"]["ApiUrl"] = self.txt_openai_url.text().strip()
        self.config["OpenAI"]["ModelName"] = self.txt_openai_model.text().strip()

        sentence_vals = [1, 2, 3, 4, 6]
        self.config["Overlay"]["DisplaySentences"] = sentence_vals[self.combo_sentences.currentIndex()]
        self.config["Overlay"]["CaptionLayout"] = self.combo_caption_layout.currentData()
        self.config["Overlay"]["AlwaysShowToolbar"] = self.chk_always_toolbar.isChecked()
        self.config["Overlay"]["Theme"] = self.combo_theme.currentData()
        self.config["Overlay"]["FontSize"] = self.slider_font.value()
        self.config["Overlay"]["Opacity"] = self.slider_op.value()
        self.config["Overlay"]["ShowLatency"] = self.chk_latency.isChecked()
        self.config["Overlay"]["Topmost"] = self.chk_topmost.isChecked()

        self.config.pop("Notion", None)

        save_config(self.config)
        self.on_saved_callback(self.config)
        self.accept()

# ----------------- Floating Pill Window (悬浮卡片) -----------------
class FloatingPillWindow(QWidget):
    subtitle_signal = pyqtSignal(str, str, str, int)
    interim_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.records = []
        self.drag_position = QPoint()
        self.init_ui()

        self.subtitle_signal.connect(self.update_subtitles)
        self.interim_signal.connect(self.update_interim_text)
        self.worker = None
        self.start_selected_worker()

    def init_ui(self):
        topmost_flag = Qt.WindowType.WindowStaysOnTopHint if self.config["Overlay"].get("Topmost", True) else Qt.WindowType.Widget
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | topmost_flag | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("PolySub")
        app_dir = os.path.dirname(os.path.abspath(__file__))
        ico_file = os.path.join(app_dir, "app.ico")
        if os.path.exists(ico_file):
            self.setWindowIcon(QIcon(ico_file))

        screen = QApplication.primaryScreen().geometry()
        init_width = 820
        self.setMinimumWidth(620)
        self.resize(init_width, 100)
        self.move((screen.width() - init_width) // 2, int(screen.height() * 0.10))

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)

        # Pill Container
        self.pill = QFrame(self)
        self.pill.setObjectName("pill")
        self.pill_layout = QVBoxLayout(self.pill)
        self.pill_layout.setContentsMargins(18, 8, 18, 10)
        self.pill_layout.setSpacing(4)

        # Header Bar: wrapped in a widget for hover-reveal / auto-hide (LiveCaptions-Translator 沉浸模式)
        self.header_widget = QWidget(self.pill)
        self.header_row = QHBoxLayout(self.header_widget)
        self.header_row.setContentsMargins(0, 0, 0, 4)
        self.header_row.setSpacing(6)

        # Engine Badge / Latency
        self.lbl_latency = QLabel("[ 239 ms ]")
        self.lbl_latency.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.header_row.addWidget(self.lbl_latency)

        self.lbl_engine_badge = QLabel(f"⚡ {self.config.get('ApiName', 'Google')}")
        self.lbl_engine_badge.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold))
        self.header_row.addWidget(self.lbl_engine_badge)

        # 开始 / 暂停按钮
        self.is_paused = False
        self.btn_toggle_play = QPushButton("⏸️ 暂停")
        self.btn_toggle_play.setToolTip("暂停 / 继续语音同传监听")
        self.btn_toggle_play.setStyleSheet("""
            QPushButton {
                background: rgba(46, 160, 67, 0.28);
                color: #56d364;
                border: 1px solid #3fb950;
                font-size: 11px;
                padding: 3px 9px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(46, 160, 67, 0.45);
                color: #ffffff;
            }
        """)
        self.btn_toggle_play.clicked.connect(self.toggle_play_state)
        self.header_row.addWidget(self.btn_toggle_play)

        # 听写来源切换按钮 (SenseVoice / Windows 11 实时字幕)
        cur_src = self.config.get("AsrSource", "SenseVoice")
        src_label = "🪟 系统字幕" if cur_src == "LiveCaptions" else "🧠 AI 听写"
        self.btn_source = QPushButton(f"{src_label} ▾")
        self.btn_source.setToolTip("切换语音听写来源: 本地 AI 离线识别 / Windows 11 自带实时字幕")
        self.btn_source.setStyleSheet("""
            QPushButton {
                background: rgba(163, 113, 247, 0.18);
                color: #d2a8ff;
                border: 1px solid rgba(163, 113, 247, 0.45);
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(163, 113, 247, 0.35);
                color: #ffffff;
                border-color: #bc8cff;
            }
        """)
        self.btn_source.clicked.connect(self.show_source_menu)
        self.header_row.addWidget(self.btn_source)

        # 翻译方向选择按钮 (主页面)
        cur_dir = self.config.get("TransDirection", "EN_TO_ZH")
        dir_label = DIRECTIONS.get(cur_dir, DIRECTIONS["EN_TO_ZH"])["label"]
        self.btn_direction = QPushButton(f"🔀 {dir_label} ▾")
        self.btn_direction.setToolTip("切换翻译方向 (如 英➔中 / 中➔英)")
        self.btn_direction.setStyleSheet("""
            QPushButton {
                background: rgba(88, 166, 255, 0.18);
                color: #79c0ff;
                border: 1px solid rgba(88, 166, 255, 0.45);
                font-size: 11px;
                padding: 3px 9px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(88, 166, 255, 0.32);
                color: #ffffff;
                border-color: #58a6ff;
            }
        """)
        self.btn_direction.clicked.connect(self.show_direction_menu)
        self.header_row.addWidget(self.btn_direction)

        self.header_row.addStretch()

        btn_header_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.22);
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.25);
                color: #ffffff;
                border-color: #58a6ff;
            }
        """

        # 📌 钉住/常驻控制栏按钮 (LiveCaptions-Translator 风格)
        self.btn_pin = QPushButton()
        self.update_pin_button_ui()
        self.btn_pin.clicked.connect(self.toggle_pin_toolbar)
        self.header_row.addWidget(self.btn_pin)

        # 0. 双语排版切换按钮
        self.btn_layout = QPushButton("🔀 排版 ▾")
        self.btn_layout.setToolTip("切换双语排版模式 (中文在上 / 英文在上 / 纯中文 / 纯英文)")
        self.btn_layout.setStyleSheet(btn_header_style)
        self.btn_layout.clicked.connect(self.show_layout_menu)
        self.header_row.addWidget(self.btn_layout)

        # 1. 调整显示条数按钮
        cur_lines = self.config["Overlay"].get("DisplaySentences", 2)
        self.btn_lines = QPushButton(f"📑 {cur_lines}条 ▾")
        self.btn_lines.setStyleSheet(btn_header_style)
        self.btn_lines.clicked.connect(self.show_lines_menu)
        self.header_row.addWidget(self.btn_lines)

        # 2. 调整大小按钮
        self.btn_size = QPushButton("🔤 大小 ▾")
        self.btn_size.setStyleSheet(btn_header_style)
        self.btn_size.clicked.connect(self.show_size_menu)
        self.header_row.addWidget(self.btn_size)

        # 3. 调整颜色按钮
        self.btn_color = QPushButton("🎨 颜色 ▾")
        self.btn_color.setStyleSheet(btn_header_style)
        self.btn_color.clicked.connect(self.show_color_menu)
        self.header_row.addWidget(self.btn_color)

        # 4. 历史记录按钮
        self.btn_history = QPushButton("📜 历史")
        self.btn_history.setStyleSheet(btn_header_style)
        self.btn_history.clicked.connect(lambda: self.open_settings_dialog(initial_tab=2))
        self.header_row.addWidget(self.btn_history)

        # 5. 设置按钮
        self.btn_settings = QPushButton("⚙️ 设置")
        self.btn_settings.setStyleSheet(btn_header_style)
        self.btn_settings.clicked.connect(lambda: self.open_settings_dialog(initial_tab=0))
        self.header_row.addWidget(self.btn_settings)

        # 6. 关闭按钮
        self.btn_close = QPushButton("✕")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(200, 210, 225, 0.6);
                border: none;
                font-size: 12px;
                padding: 2px 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #f85149;
                color: #ffffff;
            }
        """)
        self.btn_close.clicked.connect(self.close)
        self.header_row.addWidget(self.btn_close)

        self.pill_layout.addWidget(self.header_widget)

        # Content Area: Dynamic Sentences Container
        self.content_container = QWidget(self.pill)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 2, 0, 0)
        self.content_layout.setSpacing(4)

        self.sentence_widgets = []
        self.pill_layout.addWidget(self.content_container)

        self.main_layout.addWidget(self.pill)

        # Initial visibility of header toolbar
        is_pinned = self.config["Overlay"].get("AlwaysShowToolbar", False)
        self.header_widget.setVisible(is_pinned)

        # Apply Theme & Layout
        self.apply_theme_and_style()
        self.rebuild_sentence_widgets()

    def toggle_pin_toolbar(self):
        cur = self.config["Overlay"].get("AlwaysShowToolbar", False)
        new_val = not cur
        self.config["Overlay"]["AlwaysShowToolbar"] = new_val
        save_config(self.config)
        self.update_pin_button_ui()
        if new_val:
            self.header_widget.setVisible(True)
        else:
            self.header_widget.setVisible(False)
        self.adjust_window_height()

    def update_pin_button_ui(self):
        is_pinned = self.config["Overlay"].get("AlwaysShowToolbar", False)
        if hasattr(self, 'btn_pin'):
            self.btn_pin.setText("📌" if is_pinned else "📍")
            self.btn_pin.setToolTip("已固定控制栏常驻 (点击开启沉浸式自动隐藏)" if is_pinned else "点击固定控制栏常驻显示 (当前为鼠标悬停自动呼出)")
            if is_pinned:
                self.btn_pin.setStyleSheet("""
                    QPushButton {
                        background: rgba(88, 166, 255, 0.35);
                        color: #ffffff;
                        border: 1px solid #58a6ff;
                        font-size: 11px;
                        padding: 3px 8px;
                        border-radius: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background: rgba(88, 166, 255, 0.5);
                    }
                """)
            else:
                self.btn_pin.setStyleSheet("""
                    QPushButton {
                        background: rgba(255, 255, 255, 0.12);
                        color: #ffffff;
                        border: 1px solid rgba(255, 255, 255, 0.22);
                        font-size: 11px;
                        padding: 3px 8px;
                        border-radius: 5px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background: rgba(255, 255, 255, 0.25);
                        border-color: #58a6ff;
                    }
                """)

    def enterEvent(self, event):
        if not self.header_widget.isVisible():
            self.header_widget.setVisible(True)
            self.adjust_window_height()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.config["Overlay"].get("AlwaysShowToolbar", False):
            self.header_widget.setVisible(False)
            self.adjust_window_height()
        super().leaveEvent(event)

    def adjust_window_height(self):
        QTimer.singleShot(10, self.adjustSize)

    def apply_theme_and_style(self):
        thm_key = self.config["Overlay"].get("Theme", "dark")
        thm = THEMES.get(thm_key, THEMES["dark"])
        op_val = self.config["Overlay"].get("Opacity", 88)
        op = op_val / 100.0

        if op_val <= 5:
            # 100% Transparent mode (pure floating subtitle with shadow)
            self.pill.setStyleSheet("""
                QFrame#pill {
                    background-color: transparent;
                    border: none;
                }
            """)
        else:
            self.pill.setStyleSheet(f"""
                QFrame#pill {{
                    background-color: rgba({thm['bg']}, {op});
                    border: 1px solid rgba(255, 255, 255, 0.16);
                    border-radius: 14px;
                }}
            """)
        self.lbl_latency.setStyleSheet(f"color: {thm['badge']}; background: transparent; font-weight: bold; font-size: 11px;")
        self.lbl_latency.setVisible(self.config["Overlay"].get("ShowLatency", True))

        engine = self.config.get("ApiName", "Google")
        engine_styles = {
            "Google": {"text": "⚡ Google", "bg": "rgba(66, 133, 244, 0.28)", "border": "#4285f4", "color": "#8ab4f8"},
            "DeepL": {"text": "⚡ DeepL", "bg": "rgba(15, 164, 206, 0.28)", "border": "#0fa4ce", "color": "#7ce7ff"},
            "Ollama": {"text": "⚡ Ollama", "bg": "rgba(240, 140, 0, 0.28)", "border": "#f08c00", "color": "#ffd33d"},
            "OpenAI": {"text": "⚡ OpenAI", "bg": "rgba(16, 163, 127, 0.28)", "border": "#10a37f", "color": "#56f0c0"},
        }
        st = engine_styles.get(engine, engine_styles["Google"])
        self.lbl_engine_badge.setText(st["text"])
        self.lbl_engine_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {st['bg']};
                border: 1px solid {st['border']};
                color: {st['color']};
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 4px;
            }}
        """)

    def rebuild_sentence_widgets(self):
        # Clear existing
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.sentence_widgets = []

        num_lines = self.config["Overlay"].get("DisplaySentences", 2)
        fs = self.config["Overlay"].get("FontSize", 16)
        thm_key = self.config["Overlay"].get("Theme", "dark")
        thm = THEMES.get(thm_key, THEMES["dark"])
        layout_mode = self.config["Overlay"].get("CaptionLayout", "ZH_TOP")

        for i in range(num_lines):
            line_box = QVBoxLayout()
            line_box.setSpacing(2)
            line_box.setContentsMargins(0, 0, 0, 0)

            lbl_primary = QLabel("等待语音输入... (对着麦克风说话或播放音视频)" if i == num_lines - 1 else "")
            lbl_primary.setWordWrap(True)

            lbl_secondary = QLabel("Speak into microphone or play audio to start real-time transcription." if i == num_lines - 1 else "")
            lbl_secondary.setWordWrap(True)

            # High-contrast drop shadows (LiveCaptions-Translator 影院轮廓特效)
            shadow_p = QGraphicsDropShadowEffect()
            shadow_p.setBlurRadius(8)
            shadow_p.setColor(QColor(0, 0, 0, 235))
            shadow_p.setOffset(0, 2)
            lbl_primary.setGraphicsEffect(shadow_p)

            shadow_s = QGraphicsDropShadowEffect()
            shadow_s.setBlurRadius(6)
            shadow_s.setColor(QColor(0, 0, 0, 200))
            shadow_s.setOffset(0, 1)
            lbl_secondary.setGraphicsEffect(shadow_s)

            if layout_mode == "ZH_TOP":
                lbl_primary.setFont(QFont("Microsoft YaHei UI", fs, QFont.Weight.Bold))
                lbl_primary.setStyleSheet(f"color: {thm['zh']}; background: transparent;")
                lbl_secondary.setFont(QFont("Segoe UI", max(11, fs - 3), QFont.Weight.Medium))
                lbl_secondary.setStyleSheet(f"color: {thm['en']}; background: transparent;")
                line_box.addWidget(lbl_primary)
                line_box.addWidget(lbl_secondary)
                lbl_zh = lbl_primary
                lbl_en = lbl_secondary
            elif layout_mode == "EN_TOP":
                lbl_primary.setFont(QFont("Segoe UI", fs, QFont.Weight.Bold))
                lbl_primary.setStyleSheet("color: #ffffff; background: transparent;")
                lbl_secondary.setFont(QFont("Microsoft YaHei UI", max(11, fs - 2), QFont.Weight.Medium))
                lbl_secondary.setStyleSheet(f"color: {thm['zh']}; background: transparent;")
                line_box.addWidget(lbl_primary)
                line_box.addWidget(lbl_secondary)
                lbl_en = lbl_primary
                lbl_zh = lbl_secondary
            elif layout_mode == "ZH_ONLY":
                lbl_primary.setFont(QFont("Microsoft YaHei UI", fs + 1, QFont.Weight.Bold))
                lbl_primary.setStyleSheet(f"color: {thm['zh']}; background: transparent;")
                lbl_secondary.setVisible(False)
                line_box.addWidget(lbl_primary)
                lbl_zh = lbl_primary
                lbl_en = lbl_secondary
            elif layout_mode == "EN_ONLY":
                lbl_primary.setFont(QFont("Segoe UI", fs + 1, QFont.Weight.Bold))
                lbl_primary.setStyleSheet("color: #ffffff; background: transparent;")
                lbl_secondary.setVisible(False)
                line_box.addWidget(lbl_primary)
                lbl_en = lbl_primary
                lbl_zh = lbl_secondary
            else:
                lbl_primary.setFont(QFont("Microsoft YaHei UI", fs, QFont.Weight.Bold))
                lbl_primary.setStyleSheet(f"color: {thm['zh']}; background: transparent;")
                lbl_secondary.setFont(QFont("Segoe UI", max(11, fs - 3), QFont.Weight.Medium))
                lbl_secondary.setStyleSheet(f"color: {thm['en']}; background: transparent;")
                line_box.addWidget(lbl_primary)
                line_box.addWidget(lbl_secondary)
                lbl_zh = lbl_primary
                lbl_en = lbl_secondary

            container = QWidget()
            container.setLayout(line_box)
            if i > 0:
                container.setStyleSheet("border-top: 1px solid rgba(255,255,255,0.08); padding-top: 4px; margin-top: 2px;")

            self.content_layout.addWidget(container)
            self.sentence_widgets.append((lbl_zh, lbl_en))

        self.adjust_window_height()

    def toggle_play_state(self):
        self.is_paused = not self.is_paused
        if hasattr(self, 'worker') and self.worker is not None:
            self.worker.set_paused(self.is_paused)
        if self.is_paused:
            self.btn_toggle_play.setText("▶️ 开始")
            self.btn_toggle_play.setStyleSheet("""
                QPushButton {
                    background: rgba(210, 153, 34, 0.25);
                    color: #d29922;
                    border: 1px solid rgba(210, 153, 34, 0.5);
                    font-size: 11px;
                    padding: 3px 9px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(210, 153, 34, 0.45);
                    color: #ffffff;
                }
            """)
            self.lbl_latency.setText("[ ⏸️ 已暂停 ]")
        else:
            self.btn_toggle_play.setText("⏸️ 暂停")
            self.btn_toggle_play.setStyleSheet("""
                QPushButton {
                    background: rgba(46, 160, 67, 0.2);
                    color: #3fb950;
                    border: 1px solid rgba(46, 160, 67, 0.4);
                    font-size: 11px;
                    padding: 3px 9px;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(46, 160, 67, 0.35);
                    color: #ffffff;
                }
            """)
            self.lbl_latency.setText("[ 监听中 ]")

    # 听写来源动态切换与启动
    def start_selected_worker(self):
        if hasattr(self, 'worker') and self.worker is not None:
            self.worker.stop()
            self.worker = None

        source = self.config.get("AsrSource", "SenseVoice")
        if source == "LiveCaptions":
            self.worker = LiveCaptionsWorker(self.on_worker_subtitle, lambda: self.config, interim_callback=self.on_worker_interim)
        else:
            self.worker = AudioWorker(self.on_worker_subtitle, lambda: self.config)

        self.worker.paused = self.is_paused
        self.worker.start()
        self.update_source_button_ui()

    def update_source_button_ui(self):
        cur_src = self.config.get("AsrSource", "SenseVoice")
        src_label = "🪟 系统字幕" if cur_src == "LiveCaptions" else "🧠 AI 听写"
        if hasattr(self, 'btn_source'):
            self.btn_source.setText(f"{src_label} ▾")

    def show_source_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #8957e5;
                color: #ffffff;
            }
        """)
        cur = self.config.get("AsrSource", "SenseVoice")
        sources = [
            ("🧠 本地 SenseVoice AI (离线麦克风直采)", "SenseVoice"),
            ("🪟 Windows 11 实时字幕 (系统原生/不锁麦)", "LiveCaptions")
        ]
        for title, key in sources:
            prefix = "✓ " if key == cur else "   "
            act = menu.addAction(prefix + title)
            act.setData(key)

        menu.addSeparator()
        act_fix = menu.addAction("🛠️ 恢复自带字幕位置 (解决两软件冲突/隐形)")
        act_fix.setData("FIX_LIVECAPTIONS")

        action = menu.exec(QCursor.pos())
        if action and action.data():
            selected = action.data()
            if selected == "FIX_LIVECAPTIONS":
                try:
                    import uiautomation as auto
                    wnd = auto.WindowControl(searchDepth=3, ClassName="LiveCaptionsDesktopWindow")
                    if wnd.Exists(0.5):
                        hwnd = wnd.NativeWindowHandle
                        ctypes.windll.user32.SetWindowPos(hwnd, 0, 450, 60, 680, 160, 0x0040)
                        ctypes.windll.user32.ShowWindow(hwnd, 5)
                        QMessageBox.information(self, "恢复成功", "已成功将 Windows 自带实时字幕拉回屏幕可见区域！")
                    else:
                        QMessageBox.warning(self, "提示", "未找到 Windows 实时字幕窗口，请按 Win+Ctrl+L 重新呼出。")
                except Exception as e:
                    QMessageBox.warning(self, "恢复失败", str(e))
                return

            self.config["AsrSource"] = selected
            save_config(self.config)
            self.start_selected_worker()
            self.lbl_latency.setText(f"[ {self.btn_source.text().replace(' ▾', '')} ]")

    def show_direction_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        cur_dir = self.config.get("TransDirection", "EN_TO_ZH")
        for k, v in DIRECTIONS.items():
            prefix = "✓ " if k == cur_dir else "   "
            act = menu.addAction(prefix + v["full_name"])
            act.setData(k)

        action = menu.exec(QCursor.pos())
        if action and action.data():
            sel_k = action.data()
            self.config["TransDirection"] = sel_k
            save_config(self.config)
            self.btn_direction.setText(f"🔀 {DIRECTIONS[sel_k]['label']} ▾")
            self.lbl_latency.setText(f"[ {DIRECTIONS[sel_k]['label']} ]")

    # 双语排版切换菜单 (LiveCaptions-Translator 模式)
    def show_layout_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        cur_l = self.config["Overlay"].get("CaptionLayout", "ZH_TOP")
        opts = [
            ("🇨🇳 中文在上，英文在下 (ZH_TOP 推荐)", "ZH_TOP"),
            ("🇬🇧 英文在上，中文在下 (EN_TOP 精听)", "EN_TOP"),
            ("🇨🇳 仅显示中文译文 (ZH_ONLY 电影模式)", "ZH_ONLY"),
            ("🇬🇧 仅显示英文原文 (EN_ONLY 原声模式)", "EN_ONLY")
        ]
        for title, key in opts:
            prefix = "✓ " if key == cur_l else "   "
            act = menu.addAction(prefix + title)
            act.setData(key)

        action = menu.exec(QCursor.pos())
        if action and action.data():
            self.config["Overlay"]["CaptionLayout"] = action.data()
            save_config(self.config)
            self.rebuild_sentence_widgets()
            self.render_records()

    # 1. 调整条数菜单
    def show_lines_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #388bfd;
                color: #ffffff;
            }
        """)
        options = [
            ("1 句 (单行极简)", 1),
            ("2 句 (标准胶囊)", 2),
            ("3 句 (多行滚动)", 3),
            ("4 句 (长篇回顾)", 4),
            ("6 句 (大段追溯)", 6)
        ]
        cur = self.config["Overlay"].get("DisplaySentences", 2)
        for label, val in options:
            prefix = "✓ " if val == cur else "   "
            act = menu.addAction(prefix + label)
            act.setData(val)

        action = menu.exec(QCursor.pos())
        if action and action.data():
            new_val = action.data()
            self.config["Overlay"]["DisplaySentences"] = new_val
            save_config(self.config)
            self.btn_lines.setText(f"📑 {new_val}条 ▾")
            self.rebuild_sentence_widgets()
            self.render_records()

    # 2. 调整大小菜单
    def show_size_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #388bfd;
                color: #ffffff;
            }
        """)
        act_plus = menu.addAction("➕ 放大字号 (A+)")
        act_minus = menu.addAction("➖ 缩小字号 (A-)")
        menu.addSeparator()
        presets = [("紧凑小号 (13 pt)", 13), ("标准清晰 (16 pt)", 16), ("大号醒目 (18 pt)", 18), ("巨幅影院 (22 pt)", 22)]
        cur_fs = self.config["Overlay"].get("FontSize", 16)
        for label, sz in presets:
            prefix = "✓ " if sz == cur_fs else "   "
            act = menu.addAction(prefix + label)
            act.setData(sz)

        action = menu.exec(QCursor.pos())
        if action == act_plus:
            self.change_font_size(cur_fs + 1)
        elif action == act_minus:
            self.change_font_size(max(10, cur_fs - 1))
        elif action and action.data():
            self.change_font_size(action.data())

    def change_font_size(self, new_sz):
        self.config["Overlay"]["FontSize"] = new_sz
        save_config(self.config)
        self.rebuild_sentence_widgets()
        self.render_records()

    # 3. 调整颜色与透明度菜单
    def show_color_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #388bfd;
                color: #ffffff;
            }
        """)
        cur_thm = self.config["Overlay"].get("Theme", "dark")
        for k, v in THEMES.items():
            prefix = "✓ " if k == cur_thm else "   "
            act = menu.addAction(prefix + v["name"])
            act.setData(k)

        menu.addSeparator()
        op_menu = menu.addMenu("🌓 背景透明度 (Opacity)")
        cur_op = self.config["Overlay"].get("Opacity", 88)
        for op, desc in [(0, "全透纯描边 (0%)"), (60, "毛玻璃半透 (60%)"), (75, "清爽半暗 (75%)"), (88, "经典暗黑 (88%)"), (100, "纯黑遮光 (100%)")]:
            prefix = "✓ " if op == cur_op else "   "
            act_op = op_menu.addAction(prefix + desc)
            act_op.setData(f"op_{op}")

        action = menu.exec(QCursor.pos())
        if action:
            data = str(action.data())
            if data.startswith("op_"):
                val = int(data.split("_")[1])
                self.config["Overlay"]["Opacity"] = val
            elif data in THEMES:
                self.config["Overlay"]["Theme"] = data
            save_config(self.config)
            self.apply_theme_and_style()
            self.rebuild_sentence_widgets()
            self.render_records()

    # 右键全功能便捷菜单 (无需呼出控制栏即可快捷调节)
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #30363d;
                margin: 4px 8px;
            }
        """)

        # 1. 常驻 / 自动隐藏切换
        is_pinned = self.config["Overlay"].get("AlwaysShowToolbar", False)
        act_pin = menu.addAction("📌 取消固定 (开启悬停自动呼出)" if is_pinned else "📌 固定顶部控制栏 (始终常驻)")

        # 2. 排版模式
        cur_l = self.config["Overlay"].get("CaptionLayout", "ZH_TOP")
        menu_layout = menu.addMenu("🔀 双语排版模式")
        layout_opts = [
            ("🇨🇳 中文在上，英文在下 (ZH_TOP 推荐)", "ZH_TOP"),
            ("🇬🇧 英文在上，中文在下 (EN_TOP 精听)", "EN_TOP"),
            ("🇨🇳 仅显示中文译文 (ZH_ONLY 电影模式)", "ZH_ONLY"),
            ("🇬🇧 仅显示英文原文 (EN_ONLY 原声模式)", "EN_ONLY")
        ]
        for title, key in layout_opts:
            prefix = "✓ " if key == cur_l else "   "
            act = menu_layout.addAction(prefix + title)
            act.setData(f"layout_{key}")

        # 3. 字体大小
        cur_fs = self.config["Overlay"].get("FontSize", 16)
        menu_fs = menu.addMenu("🔤 字体字号调节")
        fs_opts = [
            ("紧凑小号 (13 pt)", 13),
            ("标准清晰 (16 pt)", 16),
            ("大号醒目 (18 pt)", 18),
            ("巨幅影院 (22 pt)", 22)
        ]
        for title, sz in fs_opts:
            prefix = "✓ " if sz == cur_fs else "   "
            act = menu_fs.addAction(prefix + title)
            act.setData(f"fs_{sz}")

        # 4. 主题色彩
        cur_thm = self.config["Overlay"].get("Theme", "dark")
        menu_thm = menu.addMenu("🎨 主题色彩")
        for k, v in THEMES.items():
            prefix = "✓ " if k == cur_thm else "   "
            act = menu_thm.addAction(prefix + v["name"])
            act.setData(f"thm_{k}")

        # 5. 背景透明度
        cur_op = self.config["Overlay"].get("Opacity", 88)
        menu_op = menu.addMenu("🌓 背景透明度")
        for op, desc in [(0, "全透纯描边 (0%)"), (60, "毛玻璃半透 (60%)"), (75, "清爽半暗 (75%)"), (88, "舒适暗黑 (88%)"), (100, "纯黑遮光 (100%)")]:
            prefix = "✓ " if op == cur_op else "   "
            act_op = menu_op.addAction(prefix + desc)
            act_op.setData(f"op_{op}")

        # 6. 显示行数
        cur_lines = self.config["Overlay"].get("DisplaySentences", 2)
        menu_lines = menu.addMenu("📑 字幕条数")
        for n in [1, 2, 3, 4, 6]:
            prefix = "✓ " if n == cur_lines else "   "
            act = menu_lines.addAction(prefix + f"{n} 句")
            act.setData(f"lines_{n}")

        # 7. 听写来源
        cur_src = self.config.get("AsrSource", "SenseVoice")
        menu_src = menu.addMenu("🎙️ 听写来源")
        act_sv = menu_src.addAction(("✓ " if cur_src == "SenseVoice" else "   ") + "🧠 SenseVoice 本地 AI")
        act_sv.setData("src_SenseVoice")
        act_lc = menu_src.addAction(("✓ " if cur_src == "LiveCaptions" else "   ") + "🪟 Windows 11 实时字幕")
        act_lc.setData("src_LiveCaptions")

        menu.addSeparator()
        act_settings = menu.addAction("⚙️ 打开功能设置...")
        act_history = menu.addAction("📜 查看历史记录...")
        menu.addSeparator()
        act_close = menu.addAction("✕ 退出同传")

        action = menu.exec(event.globalPos())
        if not action:
            return
        if action == act_pin:
            self.toggle_pin_toolbar()
        elif action == act_settings:
            self.open_settings_dialog(0)
        elif action == act_history:
            self.open_settings_dialog(2)
        elif action == act_close:
            self.close()
        elif action.data():
            data = str(action.data())
            if data.startswith("layout_"):
                self.config["Overlay"]["CaptionLayout"] = data.replace("layout_", "")
                save_config(self.config)
                self.rebuild_sentence_widgets()
                self.render_records()
            elif data.startswith("fs_"):
                self.change_font_size(int(data.replace("fs_", "")))
            elif data.startswith("thm_"):
                self.config["Overlay"]["Theme"] = data.replace("thm_", "")
                save_config(self.config)
                self.apply_theme_and_style()
                self.rebuild_sentence_widgets()
                self.render_records()
            elif data.startswith("op_"):
                self.config["Overlay"]["Opacity"] = int(data.replace("op_", ""))
                save_config(self.config)
                self.apply_theme_and_style()
            elif data.startswith("lines_"):
                self.config["Overlay"]["DisplaySentences"] = int(data.replace("lines_", ""))
                save_config(self.config)
                self.btn_lines.setText(f"📑 {self.config['Overlay']['DisplaySentences']}条 ▾")
                self.rebuild_sentence_widgets()
                self.render_records()
            elif data.startswith("src_"):
                src = data.replace("src_", "")
                self.config["AsrSource"] = src
                save_config(self.config)
                self.start_selected_worker()

    def open_settings_dialog(self, initial_tab=0):
        dlg = SettingsDialog(self, self.config, self.records, self.on_config_applied, initial_tab)
        dlg.exec()
        return

    def on_config_applied(self, new_cfg):
        self.config = new_cfg
        cur_dir = self.config.get("TransDirection", "EN_TO_ZH")
        dir_label = DIRECTIONS.get(cur_dir, DIRECTIONS["EN_TO_ZH"])["label"]
        if hasattr(self, 'btn_direction'):
            self.btn_direction.setText(f"🔀 {dir_label} ▾")
        self.btn_lines.setText(f"📑 {self.config['Overlay'].get('DisplaySentences', 2)}条 ▾")
        self.update_pin_button_ui()
        if self.config["Overlay"].get("AlwaysShowToolbar", False):
            self.header_widget.setVisible(True)
        else:
            self.header_widget.setVisible(False)
        self.apply_theme_and_style()
        self.rebuild_sentence_widgets()
        self.render_records()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.config["Overlay"].get("Topmost", True))
        self.show()

    def on_worker_subtitle(self, ts, en, zh, latency):
        self.subtitle_signal.emit(ts, en, zh, latency)

    def on_worker_interim(self, pending):
        self.interim_signal.emit(pending)

    @pyqtSlot(str)
    def update_interim_text(self, text):
        if not self.sentence_widgets:
            return
        lbl_zh, lbl_en = self.sentence_widgets[-1]
        layout_mode = self.config["Overlay"].get("CaptionLayout", "ZH_TOP")
        thm_key = self.config["Overlay"].get("Theme", "dark")
        thm = THEMES.get(thm_key, THEMES["dark"])

        if layout_mode == "ZH_ONLY":
            lbl_zh.setText(f"🎙️ {text} ▍")
            lbl_zh.setStyleSheet(f"color: {thm['zh']}; background: transparent; font-weight: bold;")
        elif layout_mode in ["EN_TOP", "EN_ONLY"]:
            lbl_en.setText(f"{text} ▍")
            lbl_en.setStyleSheet("color: #79c0ff; background: transparent; font-weight: 600;")
            if layout_mode == "EN_TOP":
                if not lbl_zh.text() or "等待" in lbl_zh.text() or "正在" in lbl_zh.text():
                    lbl_zh.setText("🎙️ 正在实时翻译...")
                    lbl_zh.setStyleSheet(f"color: {thm['badge']}; background: transparent; font-size: 11px;")
        else: # ZH_TOP
            lbl_en.setText(f"{text} ▍")
            lbl_en.setStyleSheet(f"color: {thm['en']}; background: transparent; font-weight: 500;")
            if not lbl_zh.text() or "等待" in lbl_zh.text() or "正在" in lbl_zh.text():
                lbl_zh.setText("🎙️ 正在实时同传...")
                lbl_zh.setStyleSheet(f"color: {thm['badge']}; background: transparent; font-weight: bold;")
        self.lbl_latency.setText("[ 🎙️ 实时流 ]")
        self.adjust_window_height()

    @pyqtSlot(str, str, str, int)
    def update_subtitles(self, ts, en, zh, latency):
        self.records.append((ts, en, zh, latency))
        self.lbl_latency.setText(f"[ {latency} ms ]")

        # Save to local file
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(TRANSCRIPTS_DIR, f"transcript_{today}.txt")
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] EN: {en}\n[{ts}] ZH: {zh}\n\n")
        except Exception:
            pass

        self.render_records()

    def render_records(self):
        if not self.records or not self.sentence_widgets:
            return

        num_slots = len(self.sentence_widgets)
        recent = self.records[-num_slots:]
        fs = self.config["Overlay"].get("FontSize", 16)
        thm_key = self.config["Overlay"].get("Theme", "dark")
        thm = THEMES.get(thm_key, THEMES["dark"])
        layout_mode = self.config["Overlay"].get("CaptionLayout", "ZH_TOP")

        for i in range(num_slots):
            idx_in_recent = len(recent) - num_slots + i
            lbl_zh, lbl_en = self.sentence_widgets[i]
            is_latest = (i == num_slots - 1)

            if idx_in_recent >= 0:
                ts, en, zh, lat = recent[idx_in_recent]
                lbl_zh.setText(zh)
                lbl_en.setText(en)

                if is_latest:
                    # Latest newest sentence: prominent, vibrant, cinema contrast
                    if layout_mode == "ZH_TOP":
                        lbl_zh.setFont(QFont("Microsoft YaHei UI", fs + 1, QFont.Weight.Bold))
                        lbl_zh.setStyleSheet(f"color: {thm['zh']}; background: transparent;")
                        lbl_en.setFont(QFont("Segoe UI", max(11, fs - 2), QFont.Weight.Medium))
                        lbl_en.setStyleSheet(f"color: {thm['en']}; background: transparent;")
                    elif layout_mode == "EN_TOP":
                        lbl_en.setFont(QFont("Segoe UI", fs + 1, QFont.Weight.Bold))
                        lbl_en.setStyleSheet("color: #ffffff; background: transparent;")
                        lbl_zh.setFont(QFont("Microsoft YaHei UI", max(11, fs - 2), QFont.Weight.Medium))
                        lbl_zh.setStyleSheet(f"color: {thm['zh']}; background: transparent;")
                    elif layout_mode == "ZH_ONLY":
                        lbl_zh.setFont(QFont("Microsoft YaHei UI", fs + 2, QFont.Weight.Bold))
                        lbl_zh.setStyleSheet(f"color: {thm['zh']}; background: transparent;")
                    elif layout_mode == "EN_ONLY":
                        lbl_en.setFont(QFont("Segoe UI", fs + 2, QFont.Weight.Bold))
                        lbl_en.setStyleSheet("color: #ffffff; background: transparent;")
                else:
                    # Previous history sentences: softly dimmed (50% opacity)
                    if layout_mode in ["ZH_TOP", "ZH_ONLY"]:
                        lbl_zh.setFont(QFont("Microsoft YaHei UI", max(10, fs - 1), QFont.Weight.Normal))
                        lbl_zh.setStyleSheet("color: rgba(235, 240, 245, 0.55); background: transparent;")
                        lbl_en.setFont(QFont("Segoe UI", max(9, fs - 4)))
                        lbl_en.setStyleSheet("color: rgba(160, 174, 192, 0.45); background: transparent;")
                    elif layout_mode in ["EN_TOP", "EN_ONLY"]:
                        lbl_en.setFont(QFont("Segoe UI", max(10, fs - 1), QFont.Weight.Normal))
                        lbl_en.setStyleSheet("color: rgba(235, 240, 245, 0.55); background: transparent;")
                        lbl_zh.setFont(QFont("Microsoft YaHei UI", max(9, fs - 4)))
                        lbl_zh.setStyleSheet("color: rgba(160, 174, 192, 0.45); background: transparent;")
            else:
                lbl_zh.setText("")
                lbl_en.setText("")

        self.adjust_window_height()

    # Mouse drag anywhere on card
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker is not None:
            try:
                self.worker.stop()
            except Exception:
                pass
        # Ensure LiveCaptions window is in normal visible position if running
        try:
            hwnd = ctypes.windll.user32.FindWindowW("LiveCaptionsDesktopWindow", None)
            if hwnd:
                rect = (ctypes.c_long * 4)()
                ctypes.windll.user32.GetWindowRect(hwnd, rect)
                if rect[0] < -1000 or rect[1] < -1000 or (rect[2] - rect[0] < 60):
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 450, 60, 680, 160, 0x0040)
                    ctypes.windll.user32.ShowWindow(hwnd, 5)
        except Exception:
            pass
        event.accept()
        try:
            QApplication.instance().quit()
        except Exception:
            pass
        import os
        os._exit(0)

if __name__ == '__main__':
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PolySub.LiveTrans.App.1.0")
    except Exception:
        pass

    # Windows Single-Instance Mutex: Prevent duplicate instances from competing for mic
    _h_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\PolySub_SingleInstance_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        print("PolySub 已经在运行中，已忽略重复启动。")
        sys.exit(0)

    app = QApplication(sys.argv)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    ico_file = os.path.join(app_dir, "app.ico")
    if os.path.exists(ico_file):
        app.setWindowIcon(QIcon(ico_file))

    window = FloatingPillWindow()
    window.show()
    sys.exit(app.exec())
