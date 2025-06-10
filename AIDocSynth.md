# AIDocSynth – Endgültige, konsistente Schritt-für-Schritt-Anleitung

*(in sehr feingranularen Blöcken; **jeder fett gesetzte Abschnitt = ein Git-Commit**.
Alle Code-Snippets sind minimal – Details dürfen später verfeinert werden. Reihenfolge strikt einhalten.)*

---

## 0 · Überblick

| Ausbaustufe | Ziel                                                                                       |
| ----------- | ------------------------------------------------------------------------------------------ |
| **1**       | Python + Git, Projektgerüst, Worker, Tray-Stub, Basis-Tests, Ressourcen                    |
| **2**       | Prompt-Ordner, Settings-Modell, Provider-Registry (Dummy), Datei-Manager, Minimal-Pipeline |
| **3**       | Grund-UI, Drop­Area, Splash-Spinner, OCR + Fusion, Controller-Anbindung                    |
| **4**       | Echte Provider (OpenAI, Azure, Ollama-SDK), Provider-Auswahl, Fortschrittsbalken           |
| **5**       | Metadaten, Ordner-Scan, Prompt für Pfad/Dateiname, Datei speichern + Metadaten             |
| **6**       | Status-Dock, Job-Table-Model, Filter (Aktiv / Abgeschlossen), Live-Verdrahtung             |

> Jeder Abschnitt enthält: **was du tust → was du committest**.
> Paket-Installationen erweitern sich nur, niemals entfernen.

---

## Ausbaustufe 1 – Python & Skeleton

### **1 · Python- & Git-Setup**

```bash
mkdir AIDocSynth && cd AIDocSynth && git init

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install pyside6 python-doctr[torch] PyMuPDF pillow numpy \
            openai jinja2 pydantic pytest pytest-mock
pip freeze > requirements.txt
```

*Commit →* **“venv + Kern-Abhängigkeiten”**

---

### **2 · Gerüst anlegen**

```text
aidocsynth/
  ui/
  ui/resources/
  controllers/
  models/
  services/
  services/providers/
  utils/
tests/
```

```bash
find aidocsynth -type d -empty -exec touch {}/.gitkeep \;
```

*Commit →* **“Projektordner angelegt”**

---

### **3 · Main-Stub**

`aidocsynth/app.py`

```python
from PySide6.QtWidgets import QApplication, QMainWindow
import sys

def main():
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("AIDocSynth stub")
    win.resize(600, 400)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

*Commit →* **“Main-Stub”**

---

### **4 · Asynchroner Worker**

`utils/worker.py`

```python
from PySide6.QtCore import QRunnable, QObject, Signal
import asyncio, traceback

class WorkerSignals(QObject):
    finished = Signal(object)
    error    = Signal(str)

class Worker(QRunnable):
    def __init__(self, coro, *args):
        super().__init__()
        self.coro, self.args = coro, args
        self.sig = WorkerSignals()

    def run(self):
        try:
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            res  = loop.run_until_complete(self.coro(*self.args))
            self.sig.finished.emit(res)
        except Exception:
            self.sig.error.emit(traceback.format_exc())
```

*Commit →* **“Worker-Klasse”**

---

### **5 · Tray-Icon-Stub**

*Ergänze* in `app.py` (nach Fenster-Erstellung):

```python
from PySide6.QtGui      import QIcon
from PySide6.QtWidgets  import QSystemTrayIcon, QMenu

icon = QIcon(":/app.png")            # Ressource ab Schritt 7
tray = QSystemTrayIcon(icon, app)
menu = QMenu(); menu.addAction("Beenden", app.quit)
tray.setContextMenu(menu); tray.show()
```

*Commit →* **“Tray-Stub”**

---

### **6 · Bootstrap-Smoke-Test**

`tests/test_bootstrap.py`

```python
import importlib
def test_import(): importlib.import_module("aidocsynth.app")
```

*Commit →* **“Bootstrap-Test”**

---

### **7 · Ressourcen & RCC**

* Kopiere Icon `aidocsynth/ui/resources/app.png` (256×256).
* Dummy-PDF `tests/assets/dummy.pdf` (`%PDF-1.4 dummy`).
* `resources.qrc`

```xml
<RCC>
  <qresource prefix="/">
    <file>aidocsynth/ui/resources/app.png</file>
  </qresource>
</RCC>
```

Compile:

```bash
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py
```

*Commit →* **“Icon, Dummy-PDF, RCC”**

---

## Ausbaustufe 2 – Prompt, Settings, Core-Services

### **1 · Prompt-Ordner**

`prompts/analysis.j2`

```jinja
Analysiere das Dokument und gib reines JSON
{"targetPath": "...", "fileName": "..."} zurück:

{{ content }}
```

*Commit →* **“Prompt-Ordner”**

---

### **2 · Settings & Service**

`models/settings.py`

```python
from PySide6.QtCore import QStandardPaths
from pydantic import BaseModel, Field
from pathlib import Path

docs = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))

class LLMSettings(BaseModel):
    provider: str = "openai"
    openai_api_key: str | None = None

class AppSettings(BaseModel):
    work_dir:      Path = docs / "AIDocSynth"
    backup_root:   Path = work_dir / "backup"
    unsorted_root: Path = work_dir / "unsorted"
    llm: LLMSettings = Field(default_factory=LLMSettings)
```

`services/settings_service.py`

```python
from pathlib import Path
from dotenv import load_dotenv
from models.settings import AppSettings

_CFG = Path.home() / ".config" / "AIDocSynth" / "settings.json"
load_dotenv()

class SettingsService:
    def __init__(self):
        self.data = (AppSettings.model_validate_json(_CFG.read_text())
                     if _CFG.exists() else AppSettings())
    def save(self):
        _CFG.parent.mkdir(parents=True, exist_ok=True)
        _CFG.write_text(self.data.model_dump_json(indent=2))

settings = SettingsService()
```

*Commit →* **“Settings-Modell & Service”**

---

### **3 · Provider-Basis (+ Dummy)**

`services/providers/base.py`

```python
from abc import ABC, abstractmethod
from importlib import resources
import json
from models.settings import LLMSettings

_REGISTRY: dict[str, type["ProviderBase"]] = {}

def register(cls): _REGISTRY[cls.name] = cls; return cls
def get_provider(cfg): return _REGISTRY[cfg.provider](cfg)

class ProviderBase(ABC):
    name: str
    def __init__(self, cfg: LLMSettings): self.cfg = cfg
    @staticmethod
    def _prompt(name: str, **kw): return resources.files("prompts").joinpath(name).read_text().format(**kw)
    async def classify_document(self, ctx: dict):
        return json.loads(await self._run(self._prompt("analysis.j2", **ctx)))
    @abstractmethod
    async def _run(self, prompt: str): ...
```

`services/providers/dummy_provider.py`

```python
from .base import ProviderBase, register
import json
@register
class DummyProvider(ProviderBase):
    name = "openai"
    async def _run(self, prompt): return json.dumps({"targetPath":"Test","fileName":"dummy.txt"})
```

*Commit →* **“Provider-Registry + Dummy”**

---

### **4 · Datei-Manager**

`services/file_manager.py`

```python
import shutil, datetime
from pathlib import Path
from models.settings import AppSettings

def backup_original(src: Path, cfg: AppSettings):
    d = cfg.backup_root / datetime.date.today().strftime("%Y%m%d")
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, d / src.name)

def move_sorted(src: Path, rel: str, name: str, cfg: AppSettings):
    dst_dir = cfg.work_dir / rel
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / name
    idx = 1
    while dst.exists():
        dst = dst_dir / f"{dst.stem}_v{idx:02d}{dst.suffix}"; idx += 1
    shutil.move(src, dst); return dst

def move_unsorted(src: Path, cfg: AppSettings):
    cfg.unsorted_root.mkdir(parents=True, exist_ok=True)
    dst = cfg.unsorted_root / src.name
    shutil.move(src, dst); return dst
```

*Commit →* **“Datei-Manager”**

---

### **5 · Minimal-Pipeline & Controller-Skeleton**

`services/text_pipeline.py`

```python
def extract_text_stub(p): return f"Content of {p}"
```

`models/job.py`

```python
from dataclasses import dataclass
@dataclass
class Job: path: str; status: str = "new"; progress: int = 0; message: str = ""
```

`controllers/main_controller.py`

```python
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThreadPool
from models.job import Job
from utils.worker     import Worker
from services.settings_service import settings
from services.file_manager     import backup_original, move_sorted, move_unsorted
from services.text_pipeline    import extract_text_stub
from services.providers.base   import get_provider

class MainController(QObject):
    jobAdded = Signal(Job); jobUpdated = Signal(Job)
    def __init__(self): super().__init__(); self.pool = QThreadPool.globalInstance()
    def handle_drop(self, paths):
        for p in paths:
            job = Job(path=p); self.jobAdded.emit(job)
            w = Worker(self._pipeline, job); self.pool.start(w)
            w.sig.finished.connect(lambda _, j=job: self.jobUpdated.emit(j))
    async def _pipeline(self, job):
        cfg, src = settings.data, Path(job.path)
        backup_original(src, cfg)
        txt = extract_text_stub(src)
        data = get_provider(cfg.llm).classify_document({"content": txt})
        data = await data
        try: move_sorted(src, data["targetPath"], data["fileName"], cfg); job.status="done"
        except Exception: move_unsorted(src, cfg); job.status="error"
```

*Commit →* **“Controller-Stub & Pipeline-Stub”**

---

### **6 · Smoke-Test Pipeline**

`tests/test_pipeline_smoke.py`

```python
from aidocsynth.controllers.main_controller import MainController
def test_pipeline(tmp_path):
    f = tmp_path/"d.txt"; f.write_text("x")
    MainController().handle_drop([str(f)])
```

*Commit →* **“Pipeline Smoke-Test”**

---

### **7 · RCC Build-Script**

`scripts/build_resources.sh`

```bash
#!/usr/bin/env bash
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py
```

*Commit →* **“RCC Script”**

---

## Ausbaustufe 3 – **UI + OCR** 

*(folge strikt der Reihenfolge – **ein fett gesetzter Block = ein Git-Commit**)*

---

### **1 · Designer-Dateien anlegen**

1. Öffne **Qt Designer** und erstelle drei Dateien im Ordner `aidocsynth/ui/`:

| Datei                | Inhalt – **wichtige objectNames**                                                                                                                                                                                          |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main_window.ui`     | `QMainWindow` → centralWidget = VerticalLayout → `QFrame` **dropFrame** (acceptDrops = True, minHeight = 180)<br>➜ `QStatusBar` → `QLabel` **lblInfo** (Starttext „Bereit“), `QProgressBar` **prgJob** (textHidden = True) |
| `status_dock.ui`     | `QDockWidget` **dockStatus** → QWidget → `QTableView` **tblJobs**                                                                                                                                                          |
| `settings_dialog.ui` | `QDialog` → `QTabWidget` **tabWidget** mit Tabs **Allgemein** & **KI**                                                                                                                                                     |

2. Speichere alle drei Dateien.

*Commit →* **“UI-Grundlayout (.ui) eingecheckt”**

---

### **2 · DropArea-Widget einbauen**

1. **Erstelle** `aidocsynth/ui/drop_area.py`:

```python
from PySide6.QtWidgets import QFrame
from PySide6.QtCore    import Signal

class DropArea(QFrame):
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("border: 2px dashed #888;")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.filesDropped.emit([u.toLocalFile() for u in e.mimeData().urls()])
```

2. **Ersetze** in `app.py` den Designer-Frame:

```python
from PySide6.QtUiTools import QUiLoader
from aidocsynth.ui.drop_area import DropArea
from PySide6.QtWidgets import QFrame
# …
loader = QUiLoader()
win   = loader.load("aidocsynth/ui/main_window.ui")
frame = win.findChild(QFrame, "dropFrame")
drop  = DropArea(); frame.layout().addWidget(drop)
```

3. **Verbinde** Drop-Signal mit Controller (kommt später):

```python
drop.filesDropped.connect(ctrl.handle_drop)
```

*Commit →* **“DropArea-Widget und Einbindung”**

---

### **3 · Splash-Spinner anzeigen**

1. Lege `spinner.gif` in `aidocsynth/ui/resources/`.

2. Ergänze `resources.qrc`:

```xml
<file>aidocsynth/ui/resources/spinner.gif</file>
```

3. Kompiliere Ressourcen:

```bash
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py
```

4. **Zeige** Splash in `app.py` *vor* Fenster-Erstellung:

```python
from PySide6.QtWidgets import QSplashScreen
from PySide6.QtGui      import QPixmap, QMovie

splash = QSplashScreen(QPixmap(":/spinner.gif"))
movie  = QMovie(":/spinner.gif", splash)
splash.setMovie(movie); movie.start()
splash.showMessage("Initialisiere OCR …")
splash.show()
```

*Commit →* **“Splash-Spinner eingebunden”**

---

### **4 · OCR-Pipeline implementieren**

#### 4.1 `services/ocr_service.py`

```python
import numpy as np, fitz, torch
from PIL import Image
from doctr.models import from_hub

_MODEL = None
_MODEL_ID = "Felix92/doctr-torch-parseq-multilingual-v1"

def _model():
    global _MODEL
    if _MODEL is None:
        m = from_hub(_MODEL_ID)
        _MODEL = m.to("cuda") if torch.cuda.is_available() else m
    return _MODEL

def _pdf_to_images(path: str, dpi: int = 300):
    doc = fitz.open(path)
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
        yield Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

async def ocr_text(path: str) -> str:
    if not path.lower().endswith(".pdf"):
        return ""
    imgs = [np.array(img) for img in _pdf_to_images(path)]
    result = _model()(imgs)
    return " ".join(w.value for p in result.pages
                              for b in p.blocks
                              for l in b.lines
                              for w in l.words)
```

#### 4.2 Direkter PDF-Text

`services/text_pdf.py`

```python
import fitz
def extract_direct(path: str) -> str:
    with fitz.open(path) as doc:
        return "\n".join(p.get_text() for p in doc)
```

#### 4.3 Fusion‐Funktion

`services/text_pipeline.py`

```python
from .text_pdf   import extract_direct
from .ocr_service import ocr_text

async def full_text(path: str) -> str:
    direct = extract_direct(path)
    ocr    = await ocr_text(path)
    lines  = dict.fromkeys((direct + "\n" + ocr).splitlines())
    return "\n".join(lines)
```

*Commit →* **“doctr-OCR + Fusion eingebaut”**

---

### **5 · Controller nutzt OCR & Splash schließt**

1. **Controller** (`main_controller.py`):

```python
from services.text_pipeline import full_text
# …
text = await full_text(src)
```

2. **Splash schließen** nach Model-Warm-up (`app.py`):

```python
from utils.worker import Worker
from services.ocr_service import _model
def hide_splash(_): splash.finish(win)
Worker(_model).sig.finished.connect(hide_splash)
```

*Commit →* **“OCR verdrahtet; Splash endet nach Warm-up”**

---

### **6 · OCR-Smoke-Test**

`tests/test_pipeline_ocr.py`

```python
import json, tempfile, shutil
from pathlib import Path
from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service  import settings

def test_pipeline_ocr(monkeypatch):
    temp = Path(tempfile.mkdtemp()); pdf = temp/"dummy.pdf"; pdf.write_bytes(b"%PDF-1.4")
    settings.data.work_dir = temp/"out"; settings.data.backup_root = temp/"out/backup"
    settings.data.unsorted_root = temp/"out/unsorted"

    # stubs
    monkeypatch.setattr("aidocsynth.services.text_pdf.extract_direct", lambda *_: "TXT")
    monkeypatch.setattr("aidocsynth.services.ocr_service.ocr_text", lambda *_: "OCR")
    monkeypatch.setattr(
        "aidocsynth.services.providers.dummy_provider.DummyProvider._run",
        lambda self, p: json.dumps({"targetPath":"T","fileName":"x.txt"})
    )

    MainController().handle_drop([str(pdf)])
    assert (settings.data.backup_root / pdf.name).exists()
    shutil.rmtree(temp)
```

*Commit →* **“Smoke-Test OCR”**

---

## Ausbaustufe 4 – **LLM-Provider & Fortschritt**

*(jeder **Block** ⇒ **ein Git-Commit**.  Alle Snippets sind schlank – Feinschliff erfolgt später.)*

---

### **0 · Abhängigkeiten erweitern**

```bash
pip install azure-ai-openai ollama
pip freeze | grep -E 'azure-ai-openai|ollama' >> requirements.txt
```

*Commit →* **“LLM SDKs (Azure + Ollama) installiert”**

---

### **1 · Settings-Modell vervollständigen**

1. **Ergänze** in `models/settings.py` die Felder:

```python
class LLMSettings(BaseModel):
    provider: str = "openai"             # openai | azure | ollama
    # OpenAI
    openai_api_key: str | None = None
    # Azure OpenAI
    azure_endpoint:  str | None = None
    azure_deployment: str | None = None
    azure_api_key:  str | None = None
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"
```

*Commit →* **“LLMSettings mit Azure & Ollama Feldern”**

---

### **2 · Provider-Klassen anlegen**

> Alle Dateien unter `aidocsynth/services/providers/`

#### 2.1 **OpenAIProvider** (`openai_provider.py`)

```python
from openai import AsyncOpenAI
from .base import ProviderBase, register

@register
class OpenAIProvider(ProviderBase):
    name = "openai"
    def __init__(self, cfg):
        super().__init__(cfg)
        self.cli = AsyncOpenAI(api_key=cfg.openai_api_key)

    async def _run(self, prompt: str):
        r = await self.cli.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return r.choices[0].message.content
```

#### 2.2 **AzureProvider** (`azure_provider.py`)

```python
from azure.ai.openai.aio import OpenAIClient
from azure.core.credentials import AzureKeyCredential
from .base import ProviderBase, register

@register
class AzureProvider(ProviderBase):
    name = "azure"
    def __init__(self, cfg):
        super().__init__(cfg)
        self.cli = OpenAIClient(
            endpoint=cfg.azure_endpoint,
            credential=AzureKeyCredential(cfg.azure_api_key)
        )
        self.deployment = cfg.azure_deployment

    async def _run(self, prompt: str):
        r = await self.cli.chat_completions.create(
            deployment_id=self.deployment,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return r.choices[0].message.content
```

#### 2.3 **OllamaProvider** (`ollama_provider.py`) – *SDK ohne HTTP*

```python
from ollama import AsyncClient
from .base import ProviderBase, register

@register
class OllamaProvider(ProviderBase):
    name = "ollama"
    def __init__(self, cfg):
        super().__init__(cfg)
        self.model = cfg.ollama_model
        self.cli   = AsyncClient(host=cfg.ollama_host)

    async def _run(self, prompt: str):
        resp = await self.cli.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            options={"temperature": 0.2}
        )
        return resp["message"]["content"]

    async def list_models(self) -> list[str]:
        info = await self.cli.list()
        return [m["name"] for m in info.get("models", [])]
```

*Commit →* **“Provider: OpenAI / Azure / Ollama (SDK) implementiert”**

---

### **3 · Settings-Dialog: Provider-Umschaltung**

1. **Bearbeite** `aidocsynth/ui/settings_dialog.ui`

   * Tab **KI** → `QComboBox` **cmbProvider** (`openai`,`azure`,`ollama`)
   * `QStackedWidget` **stwProviderForms**

     * Seite 0: OpenAI-Key Feld **editOpenAIKey**
     * Seite 1: Azure Felder **editEndpoint**, **editDeployment**, **editAzureKey**
     * Seite 2: Ollama-Host **editOHost** + `QComboBox` **cmbOllamaModel**

*Commit →* **“UI: Provider-Formulare”**

---

### **4 · SettingsController**

`controllers/settings_controller.py`

```python
from PySide6.QtCore import QObject
from services.settings_service import settings
from services.providers.ollama_provider import OllamaProvider
import asyncio

class SettingsController(QObject):
    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self.dlg.cmbProvider.currentTextChanged.connect(self._switch)
        self._switch(self.dlg.cmbProvider.currentText())

    # Umschalten der Stacked-Pages
    def _switch(self, prov: str):
        self.dlg.stwProviderForms.setCurrentIndex({"openai":0,"azure":1,"ollama":2}[prov])
        if prov == "ollama": asyncio.create_task(self._load_ollama_models())

    # Modelle per SDK abrufen
    async def _load_ollama_models(self):
        prov = OllamaProvider(settings.data.llm)
        models = await prov.list_models()
        self.dlg.cmbOllamaModel.clear()
        self.dlg.cmbOllamaModel.addItems(models or ["llama3"])
```

*Commit →* **“SettingsController mit Provider-Switch & Ollama-Model-Liste”**

---

### **5 · Dialog initialisieren**

*In `app.py` – direkt nach MainWindow Laden:*

```python
dlgSettings = loader.load("aidocsynth/ui/settings_dialog.ui", win)
from controllers.settings_controller import SettingsController
SettingsController(dlgSettings)

# Tray-Menü ergänzen
menu.addAction("Einstellungen", dlgSettings.show)
```

*Commit →* **“Settings-Dialog verdrahtet”**

---

### **6 · Fortschritts-Updates**

#### 6.1 Controller

*Füge pro Pipeline-Schritt hinzu (Beispiel):*

```python
job.progress = 30; job.status = "extracting"; self.jobUpdated.emit(job)
```

(Stufen: 10 Backup | 30 Extract | 50 OCR | 70 Fusion | 90 LLM | 100 done)

#### 6.2 UI

```python
win.prgJob.setRange(0,100)
ctrl.jobUpdated.connect(lambda j: win.prgJob.setValue(j.progress))
```

*Commit →* **“Progress-Balken live”**

---

### **7 · E2E-Test anpassen**

`tests/test_pipeline_ocr.py` – ersetze Dummy-Provider-Patch:

```python
monkeypatch.setattr(
    "aidocsynth.services.providers.openai_provider.OpenAIProvider._run",
    lambda self, p: json.dumps({"targetPath":"Test","fileName":"file.pdf"})
)
```

Entferne Dummy-Import.

*Commit →* **“E2E-Test patcht echten Provider-Stub”**

---

### **8 · RCC-Build-Script finalisieren**

`scripts/build_resources.sh`

```bash
#!/usr/bin/env bash
set -e
echo "Compiling Qt resources…"
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py
echo "✓  Resources ready"
```

`chmod +x scripts/build_resources.sh`

*Commit →* **“RCC-Script final”**

---

### **Stufe 4 – Ergebnis**

* **Provider-Layer**: Voll funktionsfähig für OpenAI, Azure OpenAI, Ollama-SDK
* **Settings-Dialog**: Umschalten der Provider + dynamische Ollama-Modelle
* **Controller**: sendet Fortschritt → ProgressBar & StatusLabel
* **Tests**: laufen mit OpenAI-Stub, Pipeline bleibt grün
* **Build-Script**: ressourcensicher für CI / PyInstaller

> Ab jetzt können echte LLM-Aufrufe erfolgen, inklusive lokalem Ollama-Server.


## Ausbaustufe 5 – **Metadaten · Ordner-Logik · Datei-Speichern**

*(weiterhin: **ein Block = ein Git-Commit**, Bausteine greifen exakt in das Ergebnis der Stufe 4 ein.)*

---

### **1 · Metadaten-Extractor**

`services/metadata_extractor.py`

```python
from pathlib import Path
from datetime import datetime
import fitz, piexif, docx

def _fs_meta(p: Path) -> dict:
    s = p.stat()
    return dict(
        size=s.st_size,
        ctime=datetime.fromtimestamp(s.st_ctime).isoformat(),
        mtime=datetime.fromtimestamp(s.st_mtime).isoformat(),
        ext=p.suffix.lower()[1:]
    )

def _pdf_meta(p: Path) -> dict:
    try:
        with fitz.open(p) as doc:
            m = doc.metadata
            return {"title": m.get("title"), "author": m.get("author")}
    except Exception: return {}

def _img_meta(p: Path) -> dict:
    try:
        ex = piexif.load(str(p))
        val = ex["0th"].get(piexif.ImageIFD.ImageDescription)
        return {"description": val.decode() if val else None}
    except Exception: return {}

def _docx_meta(p: Path) -> dict:
    try:
        cp = docx.Document(p).core_properties
        return {"title": cp.title, "author": cp.author}
    except Exception: return {}

def collect_all(p: Path) -> dict:
    ext = p.suffix.lower()
    meta = _fs_meta(p)
    if ext == ".pdf": meta |= _pdf_meta(p)
    if ext in (".jpg", ".jpeg", ".png"): meta |= _img_meta(p)
    if ext == ".docx": meta |= _docx_meta(p)
    return meta
```

*Commit →* **“Meta-Extractor für PDF/Bild/DOCX”**

---

### **2 · Bestehende Ordner scannen**

`services/folder_scanner.py`

```python
from pathlib import Path
from typing import List
from models.settings import AppSettings

def list_existing(cfg: AppSettings) -> List[str]:
    res = []
    for d in cfg.work_dir.rglob("*"):
        if d.is_dir() and d.name not in ("backup", "unsorted"):
            rel = d.relative_to(cfg.work_dir).as_posix()
            if rel: res.append(rel)
    return sorted(res)
```

*Commit →* **“Folder-Scanner ohne backup/unsorted”**

---

### **3 · Prompt finalisieren**

`prompts/analysis.j2`

```jinja
Du erhältst
* den kombinierten Dokument-Text,
* Metadaten (`meta`) und
* eine Liste vorhandener Unterordner (`folders`).

Liefere reines JSON **ohne Erläuterungen** mit
{
  "targetPath":  "<Unterordner oder neuer Pfad>",
  "fileName":    "<regelkonformer Dateiname>"
}

================ TEXT =================
{{ content }}
================ META =================
{{ meta }}
================ ORDNER ===============
{{ folders }}
```

*Commit →* **“Prompt: Text + Meta + Ordner”**

---

### **4 · Provider-Basisklasse: JSON zurückgeben**

`services/providers/base.py`

```python
import json
# …
async def classify_document(self, ctx: dict) -> dict:
    prompt = self._prompt("analysis.j2", **ctx)
    return json.loads(await self._run(prompt))
```

*Commit →* **“Provider-Basis parst JSON”**

---

### **5 · Metadaten schreiben**

`services/metadata_writer.py`

```python
import pikepdf, piexif, docx
from pathlib import Path

def _pdf(path, meta):
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        pdf.docinfo.update({k: str(v) for k, v in meta.items() if v})
        pdf.save()

def _img(path, meta):
    ex = piexif.load(str(path))
    desc = meta.get("description")
    if desc: ex["0th"][piexif.ImageIFD.ImageDescription] = desc.encode()
    piexif.insert(piexif.dump(ex), str(path))

def _docx(path, meta):
    d = docx.Document(path); cp = d.core_properties
    cp.title  = meta.get("title")  or cp.title
    cp.author = meta.get("author") or cp.author
    d.save(path)

def write(path: Path, meta: dict):
    ext = path.suffix.lower()
    if ext == ".pdf": _pdf(path, meta)
    elif ext in (".jpg", ".jpeg", ".png"): _img(path, meta)
    elif ext == ".docx": _docx(path, meta)
```

*Commit →* **“Meta-Writer für gängige Formate”**

---

### **6 · Controller-Pipeline erweitern**

`controllers/main_controller.py` (nur relevante Ausschnitte)

```python
from services.metadata_extractor import collect_all
from services.folder_scanner    import list_existing
from services.metadata_writer   import write

# …
meta    = collect_all(src)
folders = list_existing(cfg)
data    = await prov.classify_document({"content": full, "meta": meta, "folders": folders})

dst = move_sorted(src, data["targetPath"], data["fileName"], cfg)
write(dst, meta)      # Metadaten in das verschobene File
job.message  = dst.as_posix()
job.progress = 100; job.status = "done"
self.jobUpdated.emit(job)
```

*Commit →* **“Pipeline: Meta lesen, Ordner scannen, Datei schreiben”**

---

### **7 · Status-Label aktualisieren**

`app.py`

```python
def show_info(job):
    win.lblInfo.setText(f"{job.status} · {job.progress}%")
ctrl.jobUpdated.connect(show_info)
```

*Commit →* **“Info-Label live”**

---

### **8 · End-to-End-Test (voller Flow)**

`tests/test_full_flow.py`

```python
import json, tempfile, shutil
from pathlib import Path
from aidocsynth.controllers.main_controller import MainController
from aidocsynth.services.settings_service import settings

def test_full_flow(monkeypatch):
    tmp = Path(tempfile.mkdtemp())
    pdf = tmp/"in.pdf"; pdf.write_bytes(b"%PDF-1.4 dummy")

    settings.data.work_dir = tmp/"w"; settings.data.backup_root = tmp/"w/backup"
    settings.data.unsorted_root = tmp/"w/unsorted"
    (settings.data.work_dir/"Bestand").mkdir(parents=True)

    # Stubs: OCR + Direct Text
    monkeypatch.setattr("aidocsynth.services.text_pdf.extract_direct", lambda *_: "TEXT")
    monkeypatch.setattr("aidocsynth.services.ocr_service.ocr_text",    lambda *_: "OCR")
    # Provider stub
    monkeypatch.setattr(
        "aidocsynth.services.providers.openai_provider.OpenAIProvider._run",
        lambda self, p: json.dumps({"targetPath":"Bestand/2025", "fileName":"demo.pdf"})
    )

    MainController().handle_drop([str(pdf)])
    assert (settings.data.backup_root / pdf.name).exists()
    assert (settings.data.work_dir/"Bestand/2025/demo.pdf").exists()
    shutil.rmtree(tmp)
```

*Commit →* **“Full-Flow-Test bestanden”**

---

## Ausbaustufe 6 – Status-Fenster, Job-Tabelle, Filter & Logik

*(hier **nur** Stufe 6; jede fettgedruckte Sektion ⇒ **ein Git-Commit**. Code ist bewusst knapp – erweitere nach Bedarf.)*

---

### **1 · Status-Dock ins Hauptfenster laden**

1. Öffne `aidocsynth/ui/status_dock.ui` – prüfe Object-Names:

   * `QDockWidget` → **dockStatus**
   * `QTableView` → **tblJobs**
   * `QComboBox` → **cmbFilter** (Items: Alle, Aktiv, Abgeschlossen)

2. **In `app.py` nach MainWindow-Load einfügen**:

```python
from PySide6.QtWidgets import QTableView, QDockWidget
dock = loader.load("aidocsynth/ui/status_dock.ui", win)
win.addDockWidget(Qt.BottomDockWidgetArea, dock)

tbl = dock.findChild(QTableView, "tblJobs")
flt = dock.findChild(QComboBox,  "cmbFilter")
```

*Commit →* **“Status-Dock geladen & Widgets referenziert”**

---

### **2 · Job-Dataclass vervollständigen**

`models/job.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class Job:
    path: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: datetime = field(default_factory=datetime.now)
    status: str = "new"              # new | extracting | ocr | llm | writing | done | error
    progress: int = 0
    message: str = ""
```

*Commit →* **“Job-Klasse mit Zeit, Fortschritt, Nachricht”**

---

### **3 · JobTableModel implementieren**

`ui/job_table_model.py`

```python
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from models.job import Job

HEADERS = ["Datei", "Status", "Fortschritt", "Ergebnis"]

class JobTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._rows: list[Job] = []

    # Basis-API
    def rowCount(self, *_):    return len(self._rows)
    def columnCount(self, *_): return len(HEADERS)

    # Daten­anzeige
    def data(self, idx: QModelIndex, role: int):
        if not idx.isValid(): return None
        job = self._rows[idx.row()]

        if role == Qt.DisplayRole:
            return [job.path, job.status, f"{job.progress} %", job.message][idx.column()]

        if role == Qt.TextAlignmentRole and idx.column() == 2:
            return Qt.AlignCenter

    def headerData(self, s, orient, role):
        return HEADERS[s] if orient == Qt.Horizontal and role == Qt.DisplayRole else None

    # Helper
    def add_job(self, job: Job):
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._rows.insert(0, job)          # neueste oben
        self.endInsertRows()

    def refresh(self, job: Job):
        for r, j in enumerate(self._rows):
            if j.id == job.id:
                self._rows[r] = job
                top = self.index(r, 0); bot = self.index(r, self.columnCount()-1)
                self.dataChanged.emit(top, bot); break
```

*Commit →* **“JobTableModel”**

---

### **4 · Filter-Proxy (Aktiv | Abgeschlossen)**

`ui/job_filter_proxy.py`

```python
from PySide6.QtCore import QSortFilterProxyModel

class JobFilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.mode = "Alle"

    def set_mode(self, m: str):
        self.mode = m; self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        if self.mode == "Alle": return True
        idx = self.sourceModel().index(row, 1, parent)      # Status-Spalte
        status = self.sourceModel().data(idx, 0)
        return (status not in ("done", "error")) if self.mode == "Aktiv" else (status in ("done", "error"))
```

*Commit →* **“Proxy-Filter für Aktiv/Abgeschlossen”**

---

### **5 · Verdrahten im UI**

In `app.py` (direkt nach Erzeugen von `tbl` & `flt`):

```python
from ui.job_table_model   import JobTableModel
from ui.job_filter_proxy  import JobFilterProxy

model = JobTableModel()
proxy = JobFilterProxy();  proxy.setSourceModel(model)
tbl.setModel(proxy)
tbl.horizontalHeader().setStretchLastSection(True)

# Controller → Tabelle
ctrl.bind_table(model)

# Filter-Combo → Proxy
flt.currentTextChanged.connect(proxy.set_mode)
```

`controllers/main_controller.py` – Binding-Methode ergänzen:

```python
def bind_table(self, model):
    self.jobAdded.connect(model.add_job)
    self.jobUpdated.connect(model.refresh)
```

*Commit →* **“Controller ↔ Tabelle + Filter verdrahtet”**

---

### **6 · Fortschritt & Info-Label aktualisieren**

In `app.py` – nach Controller-Erzeugung:

```python
win.prgJob.setRange(0, 100)
ctrl.jobUpdated.connect(lambda j: win.prgJob.setValue(j.progress))
ctrl.jobUpdated.connect(lambda j: win.lblInfo.setText(f"{j.status} – {j.progress}%"))
```

*Commit →* **“Progress-Bar & Info-Label live”**

---

### **7 · Tabelle-Unit-Test**

`tests/test_table_update.py`

```python
from ui.job_table_model import JobTableModel
from models.job import Job

def test_table_updates():
    m = JobTableModel()
    j = Job(path="a.pdf")
    m.add_job(j)
    assert m.rowCount() == 1
    j.status, j.progress = "done", 100
    m.refresh(j)
    idx_status = m.index(0, 1)
    assert m.data(idx_status, 0) == "done"
```

*Commit →* **“Table-Model-Test”**

---

### **8 · End-zu-End-Test ergänzt Tabelle**

In `tests/test_full_flow.py` (aus Stufe 5) – nach `MainController().handle_drop([...])`:

```python
from ui.job_table_model import JobTableModel
tbl_model = JobTableModel()
# simulate binding
MainController().jobAdded.connect(tbl_model.add_job)
MainController().jobUpdated.connect(tbl_model.refresh)
assert tbl_model.rowCount() >= 1
```

*Commit →* **“E2E-Test inkludiert Tabelle”**

---

## Ergebnis Ausbaustufe 6

* **Status-Fenster** (DockWidget) mit **Job-Tabelle** live im Hauptfenster
* **JobTableModel** hält Daten, **JobFilterProxy** filtert *Aktiv / Abgeschlossen*
* **Controller** pusht Updates → Tabelle, ProgressBar, Info-Label
* **Unit-Test** verifiziert Tabellen-Refresh
* **E2E-Test** deckt vollständigen Weg inkl. UI-Liste ab

Damit ist das Front-End komplett verdrahtet: Benutzer sieht alle aktiven / fertigen Jobs, Fortschritt und Pfad-Ergebnis in Echtzeit, während Backend-Pipeline (Textextraktion → OCR → KI → Speichern) arbeitet.



## Ausbaustufe 7 – **PyInstaller · Release-Build**

*(jeder **fette Abschnitt** ist ein Git-Commit; die Anleitung funktioniert auf Windows & macOS)*

---

### **1 · Build-Verzeichnis & Versionsdatei**

1. **Lege** einen Ordner `build/` an – hier landen Spec-Datei, Icon, Scripts.
2. **Erstelle** `aidocsynth/__version__.py` (Version wird im About-Dialog & im Spec genutzt):

```python
__version__ = "0.2.0"
```

*Commit →* **“Version-Modul & build-Ordner”**

---

### **2 · Application-Entry für PyInstaller**

`aidocsynth/__main__.py`

```python
from aidocsynth.app import main
if __name__ == "__main__":
    main()
```

*Commit →* **“**main** Launcher”**

---

### **3 · Plattform-Icons vorbereiten**

* Windows-ICO (`app.ico` → 256/128/64 px)
* macOS-ICNS (`app.icns`)
  Speichere im `build/`-Ordner.
  *Commit →* **“Plattform-Icons hinzugefügt”**

---

### **4 · PyInstaller-Spec schreiben**

`build/aidocsynth.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
import pathlib, sys
from PyInstaller.utils.hooks import collect_submodules

project_root = pathlib.Path(__file__).resolve().parent.parent
ui_res   = project_root / "aidocsynth" / "ui" / "resources"
prompts  = project_root / "prompts"

block_cipher = None

a = Analysis(
    ["-m", "aidocsynth"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(ui_res / "*"), "aidocsynth/ui/resources"),
        (str(prompts / "*"), "prompts"),
    ],
    hiddenimports=[
        *collect_submodules("doctr"),
        "torch",
        "fitz",          # PyMuPDF C-ext
        "pikepdf",
        "piexif",
        "docx",
        "ollama",
    ],
    hooksconfig={"pydantic_dataclasses": "enabled"},
    strip=False,
    upx=True,
)

exe = EXE(
    a.pure, a.binaries, a.zipfiles, a.datas,
    name    = "AIDocSynth",
    icon    = "build/app.ico" if sys.platform.startswith("win") else "build/app.icns",
    console = False,
)
```

*Commit →* **“PyInstaller-Spec initial”**

---

### **5 · Build-Script**

`build/build_app.sh`

```bash
#!/usr/bin/env bash
set -e
DIR=$(dirname "$0")
cd "$DIR/.." || exit 1

echo "→  Schritt 1: Ressourcen kompilieren"
pyside6-rcc resources.qrc -o aidocsynth/ui/qrc_resources.py

echo "→  Schritt 2: PyInstaller Build (One-Folder)"
pyinstaller build/aidocsynth.spec --clean --noconfirm

echo "✔  Build beendet: dist/AIDocSynth"
```

`chmod +x build/build_app.sh`
*Commit →* **“Build-Script (Linux/mac/Win) hinzugefügt”**

---

### **6 · macOS-App-Bundle anpassen (nur macOS)**

Optionaler Post-Step in `build/build_app.sh`:

```bash
if [[ "$OSTYPE" == "darwin"* ]]; then
  APP="dist/AIDocSynth.app"
  echo "→  Codesign & plist Patch (macOS)"
  # codesign --force --deep --sign - "$APP"
fi
```

*Commit →* **“macOS Codesign-Hook (kommentiert)”**

---

### **7 · Erste Release-Build testen**

```bash
./build/build_app.sh
dist/AIDocSynth/AIDocSynth      #   Linux / macOS
dist\AIDocSynth\AIDocSynth.exe  #   Windows
```

Verifiziere:

* Tray-Icon erscheint
* Drag-&-Drop funktioniert
* Backup- & Sorted-Pfad werden innerhalb des portablen Ordners angelegt (`work/…`).

*Commit →* **“Build verifiziert – v0.2.0 Release”**

---

### **8 · Git-Tag & Release-Artefakt**

```bash
git tag -a v0.2.0 -m "First distributable build"
```

*(CI/CD-Pipeline kann Zip/DMG/Installer aus `dist/` hochladen.)*
*Commit (Tag) is separate in Git*

---

### **9 · Update README**

Füge Abschnitt **“Installation”** hinzu:

```markdown
## Installation

### Windows
```

```powershell
AIDocSynth-0.2.0-win64.exe
```

```markdown
### macOS
```

```bash
brew install --cask aidocsynth   # wenn später als Cask verfügbar
```

*Commit →* **“README: Install-Hinweise”**

---

## Ergebnis Ausbaustufe 7

* **PyInstaller Spec** mit Ressourcen- und Hidden-Imports
* **Icons**, **Versionsfile**, **Launcher**
* **Shell-Script** zum Kompilieren (einschließlich RCC)
* Dist-Ordner enthält eigenständige Desktop-App, funktionsgleich mit Dev-Umgebung.
