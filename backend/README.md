# Kairos Backend

FastAPI backend and local-first agent runtime.

```powershell
cd E:\Code\Kairos
python backend/app.py --root . --host 127.0.0.1 --port 8765
```

For direct module execution before installing the package:

```powershell
$env:PYTHONPATH="backend/src"
python -m kairos.cli doctor --root .
python -m kairos.cli chat-once "你好，Kairos" --root .
```

The repository root `app.py` remains a compatibility wrapper for `python app.py`.
