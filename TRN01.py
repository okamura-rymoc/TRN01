# TRN01.py
# FastAPI + SQLite + ReportLab で構成。
# Render/GitHubでそのまま動かせるワンファイル実装（テンプレートは文字列で内包）。

import os
import io
import sqlite3
from datetime import datetime, date, time as dtime, timedelta, timezone

# --- タイムゾーン（WindowsのZoneInfo不具合にフォールバック） ---
try:
    from zoneinfo import ZoneInfo
    try:
        TZ = ZoneInfo("Asia/Tokyo")
    except Exception:
        TZ = timezone(timedelta(hours=9))  # JST固定
        print("⚠️ ZoneInfo('Asia/Tokyo')が見つかりませんでした。JST固定(UTC+9)で代替します。")
except Exception:
    TZ = timezone(timedelta(hours=9))
    print("⚠️ zoneinfoモジュールを利用できません。JST固定(UTC+9)で代替します。")

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

# ====== PDF (ReportLab) ======
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ====== アプリ設定 ======
APP_TITLE = "食品衛生・動画視聴記録（手洗い）"
DB_PATH = os.environ.get("DB_PATH", "trn01.sqlite3")

app = FastAPI(title=APP_TITLE)   # ← ← ★これを先に定義！


# ====== 動画設定 ======
VIDEO_FILENAME = "TNG01.mp4"

from fastapi.responses import FileResponse

# TRN01.py と同じフォルダの mp4 を参照する設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(BASE_DIR, VIDEO_FILENAME)
app.mount("/media", StaticFiles(directory=BASE_DIR), name="media")

@app.get("/video")
def serve_video():
    """同じフォルダの mp4 を配信"""
    if not os.path.exists(VIDEO_PATH):
        return PlainTextResponse("動画ファイルが見つかりません。", status_code=404)
    return FileResponse(VIDEO_PATH, media_type="video/mp4")

# ====== フォント設定 ======
# TRN01.py と同じ場所に ipaexg.ttf を置いてください（IPAexゴシック）
JP_FONT_FILE = "ipaexg.ttf"
try:
    pdfmetrics.registerFont(TTFont("IPAexGothic", JP_FONT_FILE))
    PDF_FONT = "IPAexGothic"
    print("✅ フォント登録成功：IPAexGothic")
except Exception as e:
    print("⚠️ フォント登録エラー:", e)
    PDF_FONT = "Helvetica"  # 日本語は□になる可能性あり


# ====== DB 初期化 ======
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,           -- ISO8601（JST）
            affiliation TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """
    )
    con.commit()
    con.close()

init_db()

# ====== ユーティリティ ======
def now_jst_iso():
    return datetime.now(TZ).isoformat(timespec="seconds")

AFFILIATIONS = [
    "せんしょう",
    "せんしょう第2工場",
    "祇園おず",
    "おず おにぎり かふぇ",
]

# ====== HTML テンプレ ======
def page_base(body: str, title: str = APP_TITLE) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
<style>
  :root {{
    --bg: #f8fafc;
    --card: #ffffff;
    --ink: #0f172a;
    --accent: #2563eb;
    --muted: #64748b;
  }}
  body {{
    margin:0; padding:0; background:var(--bg); color:var(--ink);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
  }}
  .wrap {{
    max-width: 720px; margin: 0 auto; padding: 24px;
  }}
  .card {{
    background:var(--card); border-radius:16px; padding:20px; box-shadow:0 10px 20px rgba(2,6,23,.06);
  }}
  h1 {{ font-size:1.25rem; margin:0 0 12px; }}
  h2 {{ font-size:1.1rem; margin:12px 0; }}
  .grid {{ display:grid; gap:12px; }}
  .row {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
  .btn {{
    appearance:none; border:none; border-radius:999px; padding:12px 18px;
    background:var(--accent); color:#fff; font-weight:600; cursor:pointer;
  }}
  .btn.outline {{ background:#fff; color:var(--accent); border:2px solid var(--accent); }}
  .btn.muted {{ background:#e2e8f0; color:#0f172a; }}
  select, input[type="text"], input[type="date"] {{
    width:100%; padding:10px 12px; border:1px solid #e2e8f0; border-radius:10px; font-size:1rem;
    background:#fff;
  }}
  video {{ width:100%; max-height:60vh; background:#000; border-radius:12px; }}
  .hint {{ color:var(--muted); font-size:.9rem; }}
  .hr {{ height:1px; background:#e2e8f0; margin:16px 0; }}
  .right {{ text-align:right; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>{title}</h1>
    {body}
  </div>
</div>
</body>
</html>"""
    return HTMLResponse(html)


from fastapi.responses import Response

# favicon を返す（ブラウザが自動で要求するので404を防ぐ）
@app.get("/favicon.ico")
def favicon():
    # 空のアイコンを返す（バイナリ0バイト）
    return Response(content=b"", media_type="image/x-icon")


# ====== ルーティング ======

@app.get("/", response_class=HTMLResponse)
def index():
    body = f"""
    <p class="hint">用途を選択してください。</p>
    <div class="grid">
      <form action="/watch" method="get">
        <button class="btn" type="submit">視聴</button>
      </form>
      <form action="/admin" method="get">
        <button class="btn outline" type="submit">管理者用</button>
      </form>
    </div>
    """
    return page_base(body)

@app.get("/watch", response_class=HTMLResponse)
def watch():
    # 音声設定 → 視聴開始 → 動画終了でフォーム解放 → 送信で保存＆タブを閉じる試行
    video_url = "/media/TNG01.mp4"
    body = f"""
    <h2>動画を視聴</h2>
    <div class="grid">
      <div>
        <label for="audioSel" style="color:#dc2626; font-weight:bold;">音声設定（開始前に選択）</label>
        <select id="audioSel">
          <option value="on" selected>音声オン</option>
          <option value="mute">ミュート</option>
        </select>
      </div>

      <div class="row">
        <button class="btn" id="startBtn" type="button">視聴開始</button>
        <button class="btn muted" id="replayBtn" type="button" disabled>最初から再生</button>
      </div>

      <p style="color:#dc2626; font-weight:bold; margin:0;">
        視聴後、所属と氏名を入力してください。
      </p>

      <video id="vid" playsinline></video>

      <div class="hr"></div>

      <form id="infoForm" method="post" action="/submit" style="display:none" onsubmit="return onSubmitClose();">
        <label for="aff">所属</label>
        <select id="aff" name="affiliation" required>
          {''.join([f'<option value="{a}">{a}</option>' for a in AFFILIATIONS])}
        </select>

        <label for="nm" style="margin-top:12px; display:block;">氏名（フルネーム）</label>
        <input id="nm" name="name" type="text" placeholder="氏名（フルネーム）を入力" required />

        <div class="right" style="margin-top:12px;">
          <button class="btn" type="submit">記録して終了</button>
        </div>
      </form>

      <p id="closeHint" class="hint" style="display:none;">ウィンドウを自動で閉じられない場合は、このタブを手動で閉じてください。</p>
    </div>

    <script>
      const startBtn = document.getElementById('startBtn');
      const replayBtn = document.getElementById('replayBtn');
      const v = document.getElementById('vid');
      const sel = document.getElementById('audioSel');
      const form = document.getElementById('infoForm');
      const closeHint = document.getElementById('closeHint');
      const SRC = "{video_url}";

      function setupAndPlay(fromStart=true) {{
        v.src = SRC + (fromStart ? "?t=" + Date.now() : "");
        const audioOn = sel.value === "on";
        v.muted = !audioOn;
        v.autoplay = true;
        v.controls = true;
        v.currentTime = 0;
        const p = v.play();
        if (p && p.catch) {{
          p.catch(()=>{{ /* ブラウザブロック時はユーザー操作で再生可 */ }});
        }}
      }}

      startBtn.addEventListener('click', () => {{
        setupAndPlay(true);
        replayBtn.disabled = false;
      }});

      replayBtn.addEventListener('click', () => {{
        setupAndPlay(true);
      }});

      v.addEventListener('ended', () => {{
        form.style.display = 'block';
        window.scrollTo({{top: document.body.scrollHeight, behavior: 'smooth'}});
      }});

      window.onSubmitClose = function() {{
        setTimeout(() => {{
          window.close();
          setTimeout(() => {{ closeHint.style.display = 'block'; }}, 400);
        }}, 100);
        return true;
      }}
    </script>
    """
    return page_base(body, title=APP_TITLE)

@app.post("/submit")
def submit(affiliation: str = Form(...), name: str = Form(...)):
    ts = now_jst_iso()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT INTO views (ts, affiliation, name) VALUES (?, ?, ?)", (ts, affiliation, name))
    con.commit()
    con.close()
    return RedirectResponse(url="/submitted", status_code=303)

@app.get("/submitted", response_class=HTMLResponse)
def submitted():
    body = """
    <p>記録しました。ウィンドウが閉じない場合は、このタブを手動で閉じてください。</p>
    <div class="grid">
      <a class="btn outline" href="/">トップに戻る</a>
    </div>
    """
    return page_base(body)

# ====== 管理者用 ======

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    today = date.today()
    s = today.replace(day=1).isoformat()
    e = today.isoformat()
    body = f"""
    <h2>管理者用：視聴記録PDF出力</h2>
    <form class="grid" method="get" action="/admin/export">
      <div>
        <label for="start">開始日</label>
        <input id="start" name="start" type="date" value="{s}" required />
      </div>
      <div>
        <label for="end">終了日</label>
        <input id="end" name="end" type="date" value="{e}" required />
      </div>
      <div class="row">
        <button class="btn" type="submit">PDF（A4縦）をダウンロード</button>
        <button class="btn outline" type="button" id="previewBtn">プレビュー（HTML）</button>
      </div>
      <p class="hint">出力項目：年月日 時分、所属、氏名（一覧）</p>
    </form>

    <script>
      const previewBtn = document.getElementById('previewBtn');
      previewBtn.addEventListener('click', () => {{
        const s = document.getElementById('start').value;
        const e = document.getElementById('end').value;
        if (!s || !e) {{
          alert('開始日と終了日を指定してください。');
          return;
        }}
        window.location.href = `/admin/preview?start=${{encodeURIComponent(s)}}&end=${{encodeURIComponent(e)}}`;
      }});
    </script>
    """
    return page_base(body)


def fetch_rows_between(start_date: date, end_date: date):
    # JST の 00:00:00 〜 23:59:59 で抽出
    try:
        start_dt = datetime.combine(start_date, dtime.min, tzinfo=TZ)
        end_dt = datetime.combine(end_date, dtime.max, tzinfo=TZ)
        s_iso = start_dt.isoformat(timespec="seconds")
        e_iso = end_dt.isoformat(timespec="seconds")
    except Exception as e:
        print("❌ 日付→ISO変換でエラー:", e)
        raise

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT ts, affiliation, name FROM views WHERE ts BETWEEN ? AND ? ORDER BY ts ASC",
        (s_iso, e_iso)
    )
    rows = cur.fetchall()
    con.close()

    out = []
    for ts, aff, nm in rows:
        try:
            dt = datetime.fromisoformat(ts)
            disp = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            disp = ts
        out.append((disp, aff, nm))
    return out

@app.get("/admin/preview", response_class=HTMLResponse)
def admin_preview(start: str = Query(...), end: str = Query(...)):
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        if s > e:
            raise ValueError("開始日が終了日より後です。")
        rows = fetch_rows_between(s, e)
        items = "".join([f"<tr><td>{d}</td><td>{a}</td><td>{n}</td></tr>" for d,a,n in rows]) or '<tr><td colspan="3">該当データはありません</td></tr>'
        body = f"""
        <h2>プレビュー：{s.isoformat()} ～ {e.isoformat()}</h2>
        <div class="hr"></div>
        <div style="overflow:auto;">
          <table style="width:100%; border-collapse:collapse;">
            <thead>
              <tr>
                <th style="text-align:left;border-bottom:1px solid #e2e8f0;padding:6px;">年月日 時分</th>
                <th style="text-align:left;border-bottom:1px solid #e2e8f0;padding:6px;">所属</th>
                <th style="text-align:left;border-bottom:1px solid #e2e8f0;padding:6px;">氏名</th>
              </tr>
            </thead>
            <tbody>
              {items}
            </tbody>
          </table>
        </div>
        <div class="hr"></div>
        <a class="btn" href="/admin">管理者画面へ戻る</a>
        """
        return page_base(body)
    except Exception as e:
        print("❌ /admin/preview エラー:", repr(e))
        return page_base(f'<p style="color:#dc2626">プレビューでエラーが発生しました：{e}</p><a class="btn outline" href="/admin">戻る</a>')

@app.get("/admin/export")
def admin_export(start: str = Query(...), end: str = Query(...)):
    # PDF 生成（A4縦）
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        if s > e:
            raise ValueError("開始日が終了日より後です。")
        rows = fetch_rows_between(s, e)

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4

        # 余白・行間設定
        lm, rm, tm, bm = 36, 36, 36, 36  # 0.5 inch
        y = height - tm

        # タイトル
        c.setFont(PDF_FONT, 14)
        title = f"{APP_TITLE} / 一覧（{s.isoformat()} ～ {e.isoformat()}）"
        c.drawString(lm, y, title)
        y -= 18

        # ヘッダ
        c.setFont(PDF_FONT, 11)
        c.drawString(lm, y, "年月日 時分")
        c.drawString(lm + 160, y, "所属")
        c.drawString(lm + 360, y, "氏名")
        y -= 12
        c.line(lm, y, width - rm, y)
        y -= 8

        # 本文
        c.setFont(PDF_FONT, 10)
        line_h = 14
        for d, a, n in rows or [("該当データはありません", "", "")]:
            if y < bm + 40:
                c.showPage()
                y = height - tm
                c.setFont(PDF_FONT, 11)
                c.drawString(lm, y, "年月日 時分")
                c.drawString(lm + 160, y, "所属")
                c.drawString(lm + 360, y, "氏名")
                y -= 12
                c.line(lm, y, width - rm, y)
                y -= 8
                c.setFont(PDF_FONT, 10)
            c.drawString(lm, y, d)
            c.drawString(lm + 160, y, a)
            c.drawString(lm + 360, y, n)
            y -= line_h

        c.showPage()
        c.save()
        pdf_bytes = buf.getvalue()
        buf.close()

        fname = f"view-log_{s.isoformat()}_{e.isoformat()}.pdf"
        return StreamingResponse(io.BytesIO(pdf_bytes),
                                 media_type="application/pdf",
                                 headers={"Content-Disposition": f'attachment; filename="{fname}"'})
    except Exception as e:
        print("❌ /admin/export エラー:", repr(e))
        return PlainTextResponse(f"PDF出力でエラーが発生しました：{e}", status_code=500)

# ====== ローカル起動用（自動で空きポート選択＆ブラウザを開く） ======
if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time as pytime
    import socket

    def find_free_port(preferred: int = 8000) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", preferred))
                return preferred
            except OSError:
                s.bind(("127.0.0.1", 0))  # OSに空きポートを割当
                return s.getsockname()[1]

    preferred_port = int(os.environ.get("PORT", "8000"))
    PORT = find_free_port(preferred_port)

    def open_browser():
        pytime.sleep(1.2)  # 起動待ち
        try:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
