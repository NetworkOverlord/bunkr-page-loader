# Bunkr Headless Page Loader (v1 - Stable)

This script uses headless Chrome to visit stale video/image files hosted on Bunkr, refreshing their last visited timestamp.

## ✅ Features

- Filters by file type
- Concurrency via multiprocessing
- Diagnostic retry mode
- Failsafe logging (skips if empty)

## 🔧 Usage

```bash
python bunkr_headless_page_loader.py --videos-only
```

## 🐳 Docker Support

```bash
docker build -t bunkr-loader .
docker run --rm -v $HOME/bunkr_logs:/root/bunkr_logs bunkr-loader --videos-only
```
