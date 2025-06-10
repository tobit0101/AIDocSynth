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
