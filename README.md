# 食品衛生・動画視聴記録アプリ (TRN01)

FastAPI + SQLite + ReportLab によるワンファイル型アプリです。

## 起動方法（ローカル）
```bash
pip install -r requirements.txt
python TRN01.py
```

## Render / GitHub Deploy
1. GitHub に push
2. Render で新しい Web Service を作成
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn TRN01:app --host 0.0.0.0 --port $PORT`
3. （推奨）環境変数 `DB_PATH=/data/trn01.sqlite3` を追加し、/data にディスクをマウント

---

動画 (TNG01.mp4) とフォント (ipaexg.ttf) を同じフォルダに置いてください。
