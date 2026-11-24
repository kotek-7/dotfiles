#!/usr/bin/env python3
"""調べものの履歴を1枚のページ（index.html）にする。調査の置き場（既定 ~/research）を走査する。

人が後から見返すためのページ。ホームには調査をまたいだ集計を3つだけ置き、左の一覧から調査を選ぶと
その調査の詳細（調査の論点・周回・原文・文書へのリンク）が開く。

数字は手元の記録から機械で数え、どの記録から数えたかと、何件の調査に記録があったかを必ず添える。
古い調査には検索や取得の記録（queries.jsonl・fetch-log.jsonl）が無く、0 と区別して「記録なし」と出す。

使い方:
    dashboard.py [research_dir] [--runs runs.md] [--out index.html]
        research_dir … 調査の置き場（既定 ~/research）。直下のフォルダを1件の調査として読む
        --runs       … 回した記録の台帳（任意）。「調査を区切った理由」「感覚と合った？」の列を読む
        --out        … 書き出す先（既定 <research_dir>/index.html）
        --bundle DIR … ページと各調査の文書（詳細レポート・抜き書き・map.md・log.md）だけを DIR に写す。
                       原文（sources/）は写さない。スマホで見るためにどこかへ載せる束で、入れたファイルの一覧を出す
        --serve [PORT] … ページと文書を 127.0.0.1:PORT（既定 8765）で配る。読み取り専用で、合言葉つきの URL を出す。
                       合言葉は IMOZURU_SERVE_TOKEN で固定できる（スマホのブックマークを保つため）
"""

import base64
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import palette  # noqa: E402
from palette import THEMES  # noqa: E402
import skin  # noqa: E402  文書（md の表示）の見た目

esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731

# 区切った理由の自動分類。記録の文は書き手ごとに違うので、語で振り分ける。上から順に最初に当たったもの。
# 分類はページで「自動分類」と明示し、元の文を必ず並べて見せる（分類の誤りを読み手が確かめられるように）
# 区切った理由の分類ごとの標本の色（.rc1〜.rc4）。記録欠落は色を付けず破線
# 分類名は4字の熟語にそろえる（2026-10-21 かしぇ「長くてAIっぽくて統一感がなくて冗長」）
REASON_COLOR = {"論点充足": 1, "一部充足": 2, "期限到達": 3, "取得不可": 4}
REASON_RULES = (
    ("期限到達", ("約束", "打ち切", "試験運転", "上限")),
    ("取得不可", ("ログイン", "有料", "壁", "ボット", "CAPTCHA", "取れない", "取得できな", "購読")),
    ("情報飽和", ("飽和",)),
    ("周回上限", ("4周",)),
    ("論点充足", ("被覆", "根拠あり", "全部に原文", "全部付いた", "原文が付いた", "原文の場所が付いた")),
    ("一部充足", ("一部", "区切", "停止", "まで", "打ち止め", "判断")),
)
# 「論点6/6に原文」のように分子と分母が同じなら、全部そろったとみなす
ALL_ATTACHED = re.compile(r"(\d+)\s*/\s*\1\s*に原文")
ROUND_HEAD = re.compile(r"^#{2,4}\s*(\d+)\s*周目", re.M)
CHECK_ITEM = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.+)$", re.M)
SOURCE_ROW = re.compile(r"^\|(.+)\|\s*$", re.M)
URL = re.compile(r"https?://[^\s|)>\]]+")
# 日本語のフォルダ名を残しつつ、CSS の構文になる文字を一覧に入れない（2026-10-22 脆弱性レビュー）
SLUG = re.compile(r"[\w-]+")


def classify(reason: str) -> str:
    if ALL_ATTACHED.search(reason) and not any(w in reason for w in REASON_RULES[0][1] + REASON_RULES[1][1]):
        return "論点充足"
    for label, words in REASON_RULES:
        if any(w in reason for w in words):
            return label
    return "その他"


def section(text: str, heading: str) -> str:
    """map.md の「## 見出し」から次の「## 」までを返す。無ければ空。"""
    m = re.search(rf"^##\s*{re.escape(heading)}\s*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    n = re.search(r"^##\s", rest, re.M)
    return rest[:n.start()] if n else rest


def section_prefix(text: str, heading: str) -> str:
    """section() の、見出しの後ろに「（説明）」が付いていても拾う版。古い map.md は「## 場（学会・雑誌…）」と書いた"""
    m = re.search(rf"^##\s*{re.escape(heading)}\s*(?:[（(].*)?$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    n = re.search(r"^##\s", rest, re.M)
    return rest[:n.start()] if n else rest


# 一覧の検索で探す map.md の節。古い map.md は媒体を「場」と書いた
WORD_SECTIONS = (("用語", ("用語",)), ("人", ("人",)), ("媒体", ("媒体", "場")))
TITLE_MAX = 20  # 題の字数。スマホの一覧で1行に収まる長さ。超えたら作るときに警告する（切りはしない）
WORD_MAX = 120  # 1項目の長さ。説明の続きや場所の注記まで入れると、関係の無い語にも当たる


def map_words(map_text: str) -> list[tuple[str, str]]:
    """map.md の用語・人・媒体の箇条を（種類, 文）で返す。文は「 — 」より前（場所の注記は外す）"""
    words = []
    for kind, headings in WORD_SECTIONS:
        body = next((s for h in headings if (s := section_prefix(map_text, h))), "")
        for line in re.findall(r"^\s*-\s+(.+)$", body, re.M):
            head = re.split(r"\s+—\s*|\s*—\s+", line, maxsplit=1)[0].strip()
            if head:
                words.append((kind, head[:WORD_MAX]))
    return words


def topic_file(path: Path) -> bool:
    # 記録も文書も置き場の外を読ませない。内向きでもリンクは配らない（2026-10-22 脆弱性レビュー）
    try:
        if path.is_symlink() or path.parent.is_symlink():
            return False
        path.resolve().relative_to(path.parent.resolve())
        return path.is_file()
    except (OSError, ValueError, RuntimeError):
        return False


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if topic_file(path) else ""
    except OSError:
        return ""


def load_jsonl(path: Path) -> list[dict]:
    """1行1件の記録を読む。読めない行と、オブジェクトでない行は飛ばす（1行の崩れで一覧ごと落とさない）"""
    rows = []
    for line in read(path).splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_runs(path: Path | None) -> list[dict]:
    """回した記録の台帳の表を読む。列の名前で引くので、列が増えても読める。"""
    if not path:
        return []
    rows, header = [], None
    for line in read(path).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set(line.replace("|", "").strip()) <= set("-: "):
            continue
        # 途中から「回した人」の列を省いて書いた行がある。列が1つ足りなければ、その列を空として読む
        if len(cells) == len(header) - 1 and "回した人" in header:
            cells.insert(header.index("回した人"), "")
        rows.append(dict(zip(header, cells)))
    return rows


def match_run(slug: str, runs: list[dict]) -> dict | None:
    """台帳の行を話題のフォルダ名で探す。名前が書かれていない行とは結び付けない（取り違えるより記録なしのほうがよい）。
    同じ話題を何度か回したときは最後の行を使う。見張り（新着の確認）の行より、掘った行を優先する。"""
    hits = [r for r in runs if re.search(rf"(?<![\w-]){re.escape(slug)}(?![\w-])", r.get("話題", ""))]
    dug = [r for r in hits if "掘り" in r.get("型", "")]
    return (dug or hits or [None])[-1]


def count_sources(src: Path) -> int:
    """原文の本数。同じ名前の .pdf と .txt は1本と数える。"""
    if not src.is_dir():
        return 0
    stems = {p.stem for p in src.iterdir() if p.is_file() or p.is_symlink()}
    return len(stems)


def source_hosts(map_text: str) -> list[str]:
    """map.md の原文の表から、元の URL のホストを1行1つ拾う。"""
    hosts = []
    for row in SOURCE_ROW.findall(section(map_text, "原文（sources/）") or section(map_text, "原文")):
        if set(row.replace("|", "").strip()) <= set("-: "):
            continue
        m = URL.search(row)
        if m:
            # 外部由来の壊れた URL で、ほかの調査まで表示不能にしない（2026-10-22 脆弱性レビュー）
            try:
                host = urlsplit(m.group(0)).hostname
            except ValueError:
                continue
            if host:
                hosts.append(host.removeprefix("www."))
    return hosts


def topic_info(d: Path, runs: list[dict]) -> dict:
    map_text, log_text = read(d / "map.md"), read(d / "log.md")
    info: dict = {"slug": d.name, "has_map": bool(map_text)}
    q = re.search(r"^問い[:：]\s*(.+)$", map_text, re.M)
    info["question"] = q.group(1).strip() if q else ""
    # 一覧の検索で、漢字の語をひらがなやローマ字でも当てるための読み。調べるときに問いの主な語の読みを書く。
    # 読みの辞書は外部のデータしか無く（Migemo も Sudachi も）、標準ライブラリだけでは付けられない（2026-10-22 かしぇ「map.md に読みを書く」）
    r = re.search(r"^読み[:：]\s*(.+)$", map_text, re.M)
    info["reading"] = r.group(1).strip() if r else ""
    # 一覧と詳細の見出しに出す短い題。問いは調べる範囲を決める文で長くなるので、見出しは別に持つ
    # （2026-10-22 かしぇ「タイトルに文字数制限つけるか」→ 問いは縛らず、20字までの「題:」を足す）
    ti = re.search(r"^題[:：]\s*(.+)$", map_text, re.M)
    info["title"] = ti.group(1).strip() if ti else ""
    date = re.search(r"(20\d\d-\d\d-\d\d)", log_text) or re.search(r"(20\d\d-\d\d-\d\d)", map_text)
    info["date"] = date.group(1) if date else ""
    rounds = [int(n) for n in ROUND_HEAD.findall(log_text)]
    records = load_jsonl(d / "queries.jsonl")
    if records:
        rounds += [r.get("round", 0) for r in records if isinstance(r.get("round"), int)]
    # 周は SKILL.md の定義どおり、1周目以降にたどった周の数（0周目は地図づくりなので数えない）。
    # 台帳（runs.md）は行によって 0周目を数えたり数えなかったりするので、台帳の値は別に原文のまま見せる
    info["rounds"] = len({r for r in rounds if r >= 1}) if rounds else None
    info["sources"] = count_sources(d / "sources")
    info["hosts"] = source_hosts(map_text)
    info["words"] = map_words(map_text)

    claims = []
    for path in (d / "digest.json", d / "extracts.json"):
        try:
            data = json.loads(read(path) or "null")
        except ValueError:
            data = None
        if isinstance(data, dict):
            info.setdefault("stopped", data.get("stopped", ""))
            if not claims and isinstance(data.get("claims"), list):
                claims = [(c.get("claim", ""), c.get("status", "")) for c in data["claims"] if isinstance(c, dict)]
    if not claims:
        claims = [(text.strip(), "根拠あり" if mark.lower() == "x" else "未確認")
                  for mark, text in CHECK_ITEM.findall(section(map_text, "調査の論点"))]
    old = {"付いた": "根拠あり", "一部だけ": "一部のみ", "付かなかった": "根拠なし"}
    info["claims"] = [(c, old.get(s, s)) for c, s in claims]

    run = match_run(d.name, runs)
    info["run"] = run
    reason = (run or {}).get("調査を区切った理由") or info.get("stopped") or ""
    info["reason"] = reason
    info["reason_class"] = classify(reason) if reason else "記録欠落"

    info["searches"] = len(records) if records else None
    info["hits"] = sum(len(r.get("hits", [])) for r in records) if records else None
    fetches = load_jsonl(d / "fetch-log.jsonl")
    info["fetch_ok"] = sum(1 for f in fetches if f.get("status") == "OK") if fetches else None
    info["fetch_ng"] = sum(1 for f in fetches if f.get("status") == "FAIL") if fetches else None
    info["docs"] = [(name, label) for name, label in (("digest.html", "詳細レポート"), ("report.html", "抜き書き"),
                                                       ("map.md", "map.md"), ("log.md", "log.md"))
                    if topic_file(d / name)]
    return info


def write_bundle(topics: list[dict], root: Path, dest: Path) -> int:
    """ページと文書だけを dest に写す。文書の中の相対リンクは同じ並びのまま動く。
    束は調査の中身そのもの（原文からの引用を含む）なので、何を入れたかを1件ずつ出す（2026-10-21 council の Critic）"""
    # 途中まで書いてからリンクに気付くと、既存の束も壊すので先に全出力先を調べる（2026-10-22 脆弱性レビュー）
    paths = [dest / "index.html", dest / ICON.name]
    paths += [dest / t["slug"] for t in topics]
    paths += [dest / t["slug"] / name for t in topics for name, _ in t["docs"]]
    for path in paths:
        for p in (path, *path.parents):
            if p.is_symlink():
                raise ValueError(f"束の出力先にシンボリックリンクは使えない: {p}")
    if dest.resolve() == root.resolve() or root.resolve() in dest.resolve().parents:
        print(f"束の置き場は調査の置き場の外にする: {dest}", file=sys.stderr)
        return 2
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(render(topics, root), encoding="utf-8")
    files = ["index.html"]
    if ICON.is_file():
        shutil.copyfile(ICON, dest / ICON.name)
        files.append(ICON.name)
    for t in topics:
        for name, _ in t["docs"]:
            (dest / t["slug"]).mkdir(exist_ok=True)
            src = root / t["slug"] / name
            if not topic_file(src):
                continue
            if name.endswith(".html"):
                (dest / t["slug"] / name).write_bytes(with_back(name, src.read_bytes(), t["slug"]))
            else:
                shutil.copyfile(src, dest / t["slug"] / name)
            files.append(f'{t["slug"]}/{name}')
    size = sum((dest / f).stat().st_size for f in files)
    for f in files:
        print(f)
    print(f"→ {dest}（{len(files)} ファイル・{size / 1e6:.1f} MB。原文は入れていない）")
    print("注意: 詳細レポートと抜き書きには原文からの引用が入る。束を人に渡すときや公開の場所へ置くときは中身を確かめる")
    return 0


# 戻るボタンの色は palette.HUD_LIGHT・HUD_DARK。文書の地（象牙の紙・暗い設定では胡桃材）の明暗の反対側を当てる
HUD_ICON = ('<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>')


def hud_css(scheme: str) -> str:
    """scheme は "auto"（文書の明暗の切り替えに合わせる）か "dark"（暗い地に固定したページ）"""
    def vars_(k):
        return palette.css_vars(palette.HUD_DARK if k == "dark" else palette.HUD_LIGHT)
    css = (f'.imz-hud{{{vars_("dark" if scheme == "dark" else "light")};position:fixed;z-index:2147483647;'
           'left:max(14px,env(safe-area-inset-left));bottom:max(14px,env(safe-area-inset-bottom));'
           'width:46px;height:46px;border-radius:50%;display:grid;place-items:center;'
           'background:var(--hud-bg);color:var(--hud-fg);box-shadow:0 0 0 1px color-mix(in oklch,var(--hud-fg) 35%,transparent),0 6px 16px -6px color-mix(in oklch,var(--hud-umbra) 60%,transparent);'
           'transition:transform .15s}.imz-hud:active{transform:scale(.92)}'
           '.imz-hud:focus-visible{outline:2px solid var(--hud-fg);outline-offset:3px}')
    if scheme == "auto":
        css += f'@media (prefers-color-scheme:dark){{.imz-hud{{{vars_("dark")}}}}}'
    return css


# 文書だけを1枚のページとして開いたとき（窓口の ?print=1）に、文の根拠と問いの答えを開いて印刷の画面を出す。
# iPhone の Safari は、枠（iframe）の文書の印刷を頼んでも画面全体を刷り、一覧やボタンが付いて文書は1ページ目で切れた
# （2026-10-25 かしぇ「pdf印刷の時　文字以外の余計な要素がついてくる」）。書体が届いてから刷り、
# 読み込み直しで二度刷らないよう URL から ?print=1 を外す
PRINT_NOW_JS = ("(function(){function go(){document.querySelectorAll('details.s:not([open]),details.ans:not([open])').forEach(function(d){d.open=true});"
                "try{history.replaceState(null,'',location.pathname)}catch(x){}setTimeout(function(){window.print()},250)}"
                "function ready(){(document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve()).then(go)}"
                "if(document.readyState==='complete')ready();else addEventListener('load',ready)})();")


def allow_script(text: str, js: str) -> str:
    """書き出し済みの文書の CSP（meta）に、差し込むスクリプトのハッシュを足す。ほかの許可は変えない"""
    h = "'sha256-" + base64.b64encode(hashlib.sha256(js.encode()).digest()).decode() + "'"
    m = re.search(r'(<meta http-equiv="Content-Security-Policy" content=")([^"]*)(")', text)
    if not m:
        return text
    csp = m.group(2)
    csp = csp.replace("script-src ", f"script-src {h} ", 1) if "script-src " in csp else f"{csp}; script-src {h}"
    return text[:m.start(2)] + csp + text[m.end(2):]


def with_back(name: str, data: bytes, slug: str, hud: bool = True, print_now: bool = False) -> bytes:
    """文書は単体で書き出されていて、ダッシュボードへ戻る導線を持たない。配るときに左下へ戻るボタンを足す。
    map.md・log.md は文字のまま返すとボタンを置けないので、ダッシュボードと同じ胡桃材の地のページに包む。
    戻り先は相対（../index.html）にして、配る窓口でも束でも同じに動かす。
    print_now は、開いたらすぐ印刷の画面を出す（PRINT_NOW_JS）"""
    md = name.endswith(".md")
    # 文書はどれもダッシュボードと同じコルク板の暗い地に置く（skin.py）ので、戻るボタンは暗い地用の象牙色。
    # ダッシュボードの本体の枠（iframe）に出すときは、ヘッダーと一覧が残るので戻るボタンは要らない（hud=False・窓口の ?embed=1）。
    # 束を枠に出したときは消せないので、押したら枠ではなく画面全体を戻す（target=_top）
    hud = (f'<style>{hud_css("dark")}</style>'
           f'<a class="imz-hud" href="../index.html#t-{esc(slug)}" target="_top" aria-label="調査記録へ戻る">{HUD_ICON}</a>') if hud else ""
    text = data.decode("utf-8", errors="replace")
    if md:
        # map.md・log.md は、見出し・箇条書き・表などに組んで象牙の紙に載せる（2026-10-22 かしぇ「mdはちゃんとプレビューするようにしたい」）。
        # 中身は他人が書いた文を含むので、skin.md_html が全部エスケープしてから組む
        body = f'<article class="sheet md">{skin.md_html(text)}</article>{hud}'
        return skin.page(f"{slug} {name}", body, extra_head=f"<style>{skin.CSS}</style>",
                         scripts=(PRINT_NOW_JS,) if print_now else ()).encode()
    # 前に書き出した文書は印刷の見た目（skin.PRINT_CSS）を持たないので、配るときに足す。文書の CSP は style を許している
    hud += f"<style>{skin.PRINT_CSS}</style>"
    if print_now:
        text = allow_script(text, PRINT_NOW_JS)
        hud += f"<script>{PRINT_NOW_JS}</script>"
    i = text.lower().rfind("</body>")
    return (text[:i] + hud + text[i:] if i >= 0 else text + hud).encode()


def make_handler(root: Path, runs: list[dict], token: str):
    """ページと文書だけを返す読み取り専用の窓口。返す先は collect() の文書の一覧に在るものに限る＝
    パスを組み立てて開かないので、sources/ や置き場の外へは届かない。
    合言葉は最初に ?k= で受け取り、以後は cookie で通す（Tailscale の外へ出す道具で開いたときの最後の鍵）"""
    import secrets
    from http.server import BaseHTTPRequestHandler
    from urllib.parse import parse_qs, unquote

    extra_hosts = {h.strip().lower() for h in os.environ.get("IMOZURU_SERVE_HOSTS", "").split(",") if h.strip()}
    sw = sw_js().encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # DNS rebinding で敵のドメインを 127.0.0.1 に向けさせない。鍵があっても、cookie を持つブラウザの入口を制限する（2026-10-22 脆弱性レビュー）
            host = self.headers.get("Host", "").lower()
            if not (re.fullmatch(r"[a-z0-9_.-]+(?::[0-9]+)?", host) and (
                    host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")
                    or host.partition(":")[0].endswith(".ts.net")
                    or host in extra_hosts or host.partition(":")[0] in extra_hosts)):
                return self.reply(403, "text/plain; charset=utf-8", "許可されていない Host".encode())
            path, _, query = self.path.partition("?")
            # 日本語名も一覧と照合できるよう復号する。復号した文字列からファイルを開かない（2026-10-22 脆弱性レビュー）
            path = unquote(path)
            # ホーム画面のアイコンは合言葉なしで返す。iPhone はアイコンを取りに来るときに cookie を送らないことがある。
            # 中身はロゴの紋だけで、調査の中身は含まない
            if path in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png") and ICON.is_file():
                return self.reply(200, "image/png", ICON.read_bytes())
            # アプリとして入れたときのアイコンも同じ。ブラウザは入れるときに cookie を付けずに取りに来ることがある
            if path in APP_ICONS and APP_ICONS[path].is_file():
                return self.reply(200, "image/png", APP_ICONS[path].read_bytes())
            # service worker も合言葉なしで返す。ホーム画面のアプリは cookie を分けて持ち、更新の取得に合言葉が付かないことがある。
            # 中身は代わりの画面とその仕組みだけで、調査の題・中身・合言葉は含まない（sw_js）
            if path == "/sw.js":
                return self.reply(200, "text/javascript; charset=utf-8", sw)
            given = parse_qs(query).get("k", [""])[0]
            cookie = dict(c.strip().split("=", 1) for c in self.headers.get("Cookie", "").split(";") if "=" in c)
            # 非 ASCII の鍵も認証失敗として返し、比較の例外で接続を落とさない（2026-10-22 脆弱性レビュー）
            if token and not any(secrets.compare_digest(token.encode("utf-8", errors="surrogateescape"),
                                                       s.encode("utf-8", errors="surrogateescape"))
                                 for s in (given, cookie.get("imozuru", ""))):
                return self.reply(403, "text/plain; charset=utf-8", "合言葉が要る（起動したときに出た URL で開く）".encode())
            if path == "/manifest.webmanifest":
                return self.reply(200, "application/manifest+json", json.dumps(manifest(token), ensure_ascii=False).encode())
            topics = collect(root, runs)
            if path in ("/", "/index.html"):
                body = render(topics, root, served=True).encode()
                ctype = "text/html; charset=utf-8"
            else:
                slug, _, name = path.strip("/").partition("/")
                docs = {(t["slug"], n): root / t["slug"] / n for t in topics for n, _ in t["docs"]}
                src = docs.get((slug, name))
                if src is None or not topic_file(src):
                    return self.reply(404, "text/plain; charset=utf-8", "無い".encode())
                q = parse_qs(query)
                body = with_back(name, src.read_bytes(), slug, hud="embed" not in q, print_now="print" in q)
                ctype = "text/html; charset=utf-8"
            extra = {"Set-Cookie": f"imozuru={token}; Path=/; HttpOnly; SameSite=Strict"} if token and given else {}
            self.reply(200, ctype, body, extra)

        def reply(self, code, ctype, body, extra=None):
            self.send_response(code)
            for k, v in {"Content-Type": ctype, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                         "Referrer-Policy": "no-referrer", **(extra or {})}.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *a):
            # 既定の記録は ?k= の合言葉ごと URL を書き出す
            print(f"{getattr(self, 'command', '-')} {getattr(self, 'path', '').split('?')[0]} → {a[1] if len(a) > 1 else ''}", file=sys.stderr)

    return Handler


def manifest(token: str) -> dict:
    """アプリとして入れるための指定（2026-10-25 かしぇ「アプリとしてインストール推奨をもっと押し出したい（ＰＣも）」）。
    合言葉を持つ相手にだけ返し（窓口の合言葉の確認を通ったあと）、起動の URL に合言葉を入れる。
    iPhone のホーム画面のアプリは Safari と cookie を分けて持つので、合言葉の無い URL から起動すると開けない。
    id は合言葉を含まない / にして、合言葉を変えても同じアプリとして扱われるようにする。
    theme_color は置かない。iPhone で見た目の指定を足したとき、ホーム画面から開くと下に帯が出た（2026-10-22・render の注記）"""
    bg = palette.hex_of(palette.SWATCH[palette.DASH["side-bg"]])
    return {"name": "imozuru 調査記録", "short_name": "imozuru", "id": "/", "start_url": f"/?k={token}" if token else "/",
            "scope": "/", "display": "standalone", "lang": "ja", "background_color": bg,
            "icons": [{"src": p, "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any"}
                      for p, n in zip(APP_ICONS, (192, 512)) if APP_ICONS[p].is_file()]}


def serve(root: Path, runs: list[dict], port: int) -> int:
    """自分の PC の中（127.0.0.1）だけで開く。スマホへは Tailscale serve などで中継する。
    開くたびに置き場を読み直すので、調べものが増えても立て直さなくてよい"""
    import secrets
    from http.server import ThreadingHTTPServer
    token = os.environ.get("IMOZURU_SERVE_TOKEN")
    # 固定の短い鍵は総当たりできるので、生成する鍵と同様に十分な長さを求める（2026-10-22 脆弱性レビュー）
    if token is not None and len(token) < 16:
        print("IMOZURU_SERVE_TOKEN は16文字以上にしてください", file=sys.stderr)
        return 2
    token = token if token is not None else secrets.token_urlsafe(16)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root, runs, token))
    print(f"→ http://127.0.0.1:{port}/?k={token}", flush=True)
    print("この PC の中だけで開いている。スマホへは Tailscale serve で中継する（SKILL.md）。止めるときは Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def started_at(d: Path) -> float:
    """調査を始めた時刻の目安。取得の記録（fetch-log.jsonl）の時刻と、sources/ で一番古いファイル（最初に保存した原文）の
    早いほう。どちらも無ければ map.md・log.md の古いほう。リンクはたどらない。何も無ければ 0。
    ファイルの時刻は clone やコピーで新しくなるだけなので、早いほうを取れば記録の時刻が勝つ。
    2.2.0 より前の記録には時刻が無く、2.1.0 で始めて続きを取った調査はファイルの時刻のほうが早い"""
    logged = [t for f in load_jsonl(d / "fetch-log.jsonl") if (t := _epoch(f.get("at"))) is not None]
    times = []
    try:
        with os.scandir(d / "sources") as it:
            times = [e.stat(follow_symlinks=False).st_mtime for e in it if e.is_file(follow_symlinks=False)]
    except OSError:
        pass
    times += logged
    if not times:
        for name in ("map.md", "log.md"):
            try:
                st = (d / name).lstat()
            except OSError:
                continue
            if not (d / name).is_symlink():
                times.append(st.st_mtime)
    return min(times, default=0.0)


def _epoch(at: object) -> float | None:
    """取得の記録の時刻（ISO 8601）を秒にする。読めなければ None"""
    if not isinstance(at, str):
        return None
    try:
        return datetime.fromisoformat(at).timestamp()
    except ValueError:
        return None


def collect(root: Path, runs: list[dict]) -> list[dict]:
    topics = [topic_info(d, runs) for d in sorted(root.iterdir())
              if not d.is_symlink() and d.is_dir() and SLUG.fullmatch(d.name)]
    # 日付は日までしか無い。同じ日に始めた調査は、始めた時刻の新しい順に並べる
    # （前は slug の逆順で、新しい調査が下に来ることがあった・2026-10-28 かしぇ）
    started = {t["slug"]: started_at(root / t["slug"]) for t in topics}
    return sorted(topics, key=lambda t: (t["date"] or "0000", started[t["slug"]], t["slug"]), reverse=True)


def main() -> int:
    args = sys.argv[1:]
    runs_path = out = None
    if "--runs" in args:
        i = args.index("--runs")
        runs_path = Path(args[i + 1]).expanduser()
        del args[i:i + 2]
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1]).expanduser()
        del args[i:i + 2]
    bundle = None
    if "--bundle" in args:
        i = args.index("--bundle")
        bundle = Path(args[i + 1]).expanduser()
        del args[i:i + 2]
    root = Path(args[0] if args else "~/research").expanduser()
    if not root.is_dir():
        print(f"調査の置き場が無い: {root}", file=sys.stderr)
        return 2
    topics = collect(root, load_runs(runs_path))
    for t in topics:
        if len(t["title"]) > TITLE_MAX:
            print(f"題が長い（{len(t['title'])}字・{TITLE_MAX}字まで）: {t['slug']}/map.md「{t['title']}」", file=sys.stderr)
    if "--dump" in args:
        for t in topics:
            print("\t".join(str(x) for x in (t["slug"], t["date"], t["rounds"], t["sources"], len(t["hosts"]),
                                             t["reason_class"], (t["run"] or {}).get("周", "-"),
                                             (t["run"] or {}).get("原文", "-"))))
        return 0
    if bundle:
        try:
            return write_bundle(topics, root, bundle)
        except (OSError, ValueError) as e:
            print(f"束を書き出せない: {e}", file=sys.stderr)
            return 2
    if "--serve" in args:
        i = args.index("--serve")
        port = int(args[i + 1]) if i + 1 < len(args) and args[i + 1].isdigit() else 8765
        return serve(root, load_runs(runs_path), port)
    out = out or root / "index.html"
    # 固定名では事前に置かれたリンクを踏む。同じディレクトリなら置換も一度で済む（2026-10-22 脆弱性レビュー）
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix="." + out.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(render(topics, root))
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    print(f"→ {out}（調査 {len(topics)}件）")
    return 0


LOGO = Path(__file__).resolve().parent.parent / "assets" / "logo.svg"
SHOWN_HOSTS = 12

LOGO_LIGHT = LOGO.with_name("logo-light.svg")
# ホーム画面に追加したときのアイコン（ロゴの紋を胡桃材の地に置いた 180px 角）。make_textures.py が作る
ICON = LOGO.with_name("apple-touch-icon.png")

# 色はすべて palette.py に置く。ここでは役割の名前（CSS の変数）だけを使う
# IMOZURU_DASH_THEME は見た目を見比べるための開発用の切り替え。知らない値なら既定の 1 に戻す（起動の時点で落とさない）
THEME = THEMES.get(os.environ.get("IMOZURU_DASH_THEME", "1"), THEMES["1"])

# 引っぱって更新の札。弧（pathLength=1 で描いた量を CSS の dashoffset で決める）と、描き上がったときに付く矢じり。
# 矢じりは弧の終わり (4.4,9.5) を先端に、時計回りの接線の逆向きへ ±40° で開く（make の計算: 中心 (12,12)・長さ 3.4）
PTR_ICON = ('<div class="ptr" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path class="arc" pathLength="1" d="M12 4a8 8 0 1 1-7.6 5.5"/>'
            '<path class="head" d="M1.5 11.3L4.4 9.5L5.7 12.7"/></svg></div>')
HELP_ICON = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.2 9a2.9 2.9 0 0 1 5.6 1c0 2-2.8 2.6-2.8 4.3"/>'
             '<circle cx="12" cy="18" r=".6" fill="currentColor"/></svg>')


def line_icon(paths: str, size: int = 20) -> str:
    """ヘルプのボタンと同じ太さの線で描くアイコン"""
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')


# アプリとして入れる（下向きの矢印が受け皿に入る）・感想と要望を送る（吹き出し）・PDF で保存（紙に下向きの矢印）
INSTALL_ICON = line_icon('<path d="M12 4v10"/><path d="M8 10.5l4 4 4-4"/><path d="M5 15.5V18a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2.5"/>')
FEEDBACK_ICON = line_icon('<path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-7l-4 3.2V16H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"/>'
                          '<path d="M8 9.5h8M8 12.5h5"/>')
PRINT_ICON = line_icon('<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M12.5 10.5v6"/><path d="M10 14l2.5 2.5L15 14"/>')
CLOSE_ICON = line_icon('<path d="M7 7l10 10M17 7L7 17"/>', 18)

# アプリとして入れたときのアイコン（Chrome・Edge は 192px と 512px を求める）。ホーム画面のアイコンと同じ絵で、make_textures.py が作る
APP_ICONS = {f"/icon-{n}.png": LOGO.with_name(f"icon-{n}.png") for n in (192, 512)}


def imozuru_version() -> str:
    """変更履歴の一番上の版の番号（2.0.0 など）。フィードバックに添えて、どの版の話かを分かるようにする。
    スキルだけを写して入れた環境には変更履歴が無いので「不明」"""
    try:
        text = (LOGO.parents[3] / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        return "不明"
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.M)
    return m.group(1) if m else "不明"


# 感想・要望を送る先。作者の Google フォームの「事前入力したリンク」を、仮の値（種類=不具合・評価=5・内容=BODY・版=VERSION・環境=ENV）を
# 入れて取ったもの。項目の番号（entry.N）はこのリンクから読む。空ならボタンを出さない（2026-10-25 かしぇ「フォームに送る」）。
# 環境変数 IMOZURU_FEEDBACK_FORM で差し替えられ、off で消せる（フォークした人が自分のフォームへ向けるため）
FEEDBACK_FORM = ("https://docs.google.com/forms/d/e/1FAIpQLScmjsJ363aHtpUVy6-cDxQ_OnwAcQE0hp7CjigMFG57c-OjJA/viewform?usp=pp_url"
                 "&entry.1218111923=%E4%B8%8D%E5%85%B7%E5%90%88&entry.860970375=5&entry.1447275214=BODY&entry.1226542421=VERSION&entry.1935341889=ENV")
FEEDBACK_KINDS = ("不具合", "要望", "感想")


def feedback_form() -> dict | None:
    """事前入力のリンクから、送り先（formResponse）と各項目の番号を取り出す。読めなければ None（ボタンを出さない）"""
    from urllib.parse import parse_qsl, urlsplit
    link = os.environ.get("IMOZURU_FEEDBACK_FORM", FEEDBACK_FORM).strip()
    if not link or link == "off":
        return None
    u = urlsplit(link)
    m = re.fullmatch(r"/forms/d/e/([A-Za-z0-9_-]+)/viewform", u.path)
    if u.scheme != "https" or u.hostname != "docs.google.com" or not m:
        return None
    fields = {"BODY": "body", "VERSION": "version", "ENV": "env", "5": "rating"}
    out = {"action": f"https://docs.google.com/forms/d/e/{m.group(1)}/formResponse"}
    for k, v in parse_qsl(u.query):
        if re.fullmatch(r"entry\.\d+", k):
            out[fields.get(v, "kind" if v in FEEDBACK_KINDS else "")] = k
    out.pop("", None)
    return out if {"kind", "body"} <= out.keys() else None


def cork_svg() -> str:
    """コルクの粒を SVG のノイズで作り、地の色に掛け合わせるタイル（design-library knowledge/color/texture.md の「ノイズ＋照明」）。
    光だけで凹凸を出すと、しわの寄った革か紙に見えた。コルクは明るさの違う粒がまだらに詰まり、小さな穴が点々とあるので、
    粗いノイズ（.16）を段に切って粒の明暗にし、細かいノイズ（.75）のまれな値だけを暗い穴にする。粒には弱い光で凹凸を足す。
    光の向きは札の影と揃えて左上（azimuth 235）。出力は黒の透けだけで、地の色は palette の cork が決める。
    はじめは灰色の絵を background-blend-mode で地に掛け合わせたが、iPhone の Safari では掛け合わせが効かず、
    灰色がそのまま乗って地が白っぽく見えた（2026-10-22 かしぇ）。透けの絵を普通に重ねれば、掛け合わせに頼らずに済む"""
    gray ="1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"

    def steps(values):
        return "".join(f"<feFunc{c} type='discrete' tableValues='{values}'/>" for c in "RGB")
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'>"
           "<filter id='c' x='0' y='0' width='100%' height='100%' color-interpolation-filters='sRGB'>"
           "<feTurbulence type='fractalNoise' baseFrequency='.16' numOctaves='2' seed='3' stitchTiles='stitch'/>"
           f"<feColorMatrix type='matrix' values='{gray}'/>"
           f"<feComponentTransfer result='g'>{steps('.62 .8 .95 1 .88 .72')}</feComponentTransfer>"
           "<feTurbulence type='fractalNoise' baseFrequency='.75' numOctaves='1' seed='11' stitchTiles='stitch'/>"
           f"<feColorMatrix type='matrix' values='{gray}'/>"
           f"<feComponentTransfer result='p'>{steps('1 1 1 1 1 1 1 1 .5')}</feComponentTransfer>"
           "<feBlend in='g' in2='p' mode='multiply' result='m'/>"
           "<feDiffuseLighting in='g' lighting-color='white' surfaceScale='1.4' result='l'><feDistantLight azimuth='235' elevation='65'/></feDiffuseLighting>"
           "<feBlend in='m' in2='l' mode='multiply' result='t'/>"
           # 明るさを透けに直す: 黒の上の不透明度＝1−明るさ。黒を透けで重ねるのは掛け合わせと同じ見た目になる
           "<feColorMatrix in='t' type='matrix' values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -1 0 0 0 1'/>"
           "</filter><rect width='100%' height='100%' filter='url(#c)'/></svg>")
    return svg


def paper_svg() -> str:
    """象牙の台紙の繊維。横に長いノイズで紙の筋を出し、焦げ茶をごく薄く透かす"""
    return ("<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'><filter id='f'>"
            "<feTurbulence type='fractalNoise' baseFrequency='.012 .55' numOctaves='3' seed='9'/>"
            "<feColorMatrix values='0 0 0 0 .35 0 0 0 0 .27 0 0 0 0 .18 0 0 0 .08 0'/></filter>"
            "<rect width='100%' height='100%' filter='url(#f)'/></svg>")


# 質感の絵は make_textures.py が SVG から一度だけ描いた PNG（2倍の解像度）を埋め込む。
# SVG のフィルタのままだと、スマホで一覧を開くたびに本体が動き出す所でブラウザが絵を計算し直し、
# 一瞬だけ質感の無い面が見えてチラついた（2026-10-22 かしぇ）。PNG が無いときだけ SVG をそのまま使う
TEXTURES = {"cork": (LOGO.with_name("cork.png"), cork_svg, 240), "paper": (LOGO.with_name("paper.png"), paper_svg, 180)}


def texture_url(name: str) -> str:
    png, svg, _ = TEXTURES[name]
    if png.is_file():
        return 'url("data:image/png;base64,' + base64.b64encode(png.read_bytes()).decode() + '")'
    from urllib.parse import quote
    return "url(\"data:image/svg+xml," + quote(svg(), safe="/:=' ") + "\")"


# 本体の地はコルク板、グラフと詳細は象牙の台紙に載せる（2026-10-22 かしぇ「本体画面のグラデがダサい　テクスチャがほしい」
# 「その上に地でグラフとかおいてるのもなんかな」→「コルク板＋象牙の台紙」）。上からの光のグラデーションはやめた
CORK_CSS = f"""
/* 一番外側は本文と同じ地で塗る。塗らないと枠が足した上下の余白に後ろの画面が透け、
   頭の帯の色で塗ると本文の下に暗い帯が出た（2026-10-21 かしぇ「塗られるの回避出来てない」） */
html{{background:var(--cork)}}
body,main{{background-color:var(--cork);background-image:{texture_url("cork")};background-size:240px 240px;background-repeat:repeat}}
/* 台紙の中は象牙の上の文字の色に切り替え、標本の色も台紙用の濃い組（p-）にする */
.topic,.home .card{{--ink:var(--ivory-ink);--sub:var(--ivory-sub);--line:var(--ivory-line);
--r1:var(--p-r1);--r2:var(--p-r2);--r3:var(--p-r3);--r4:var(--p-r4);--bar:var(--p-bar);--src:var(--p-src)}}
.home .card{{margin:0 0 28px;padding:24px 28px 18px}}
.home .card>h3{{margin-top:0}}
.home .card summary{{color:var(--ivory-sub)}}
/* 総数の札。数字は欧文の EB Garamond で大きく、見出しと単位は小さく添える。2つの数は縦の線で分ける */
.home .tally{{margin:0 0 28px;padding:18px 28px 20px}}
/* 札の名前は標本箱の名札。小さく字間を広くとり、細い線で下の数と分ける。いちばん大きいのは数のまま */
.tally .plate-name{{margin:0 0 16px;padding-bottom:10px;border-bottom:1px solid var(--line);font-family:var(--head);
font-size:13px;font-weight:500;letter-spacing:.24em;color:var(--sub)}}
.plate-name span{{font-family:"EB Garamond",serif;font-size:15px;letter-spacing:.08em;margin-right:.3em}}
.tally dl{{display:grid;grid-template-columns:1fr 1fr;margin:0}}
.tally dl>div+div{{border-left:1px solid var(--line);padding-left:28px}}
.tally dt{{font-family:var(--head);font-size:15px;letter-spacing:.12em;color:var(--sub)}}
.tally dd{{margin:4px 0 0;font-family:var(--head);font-size:16px;color:var(--sub)}}
.tally b{{font-family:"EB Garamond",serif;font-weight:500;font-size:clamp(44px,5vw,64px);line-height:1;color:var(--ink);
font-variant-numeric:lining-nums tabular-nums;margin-right:6px}}
@media (max-width:760px){{.home .tally{{padding:14px 16px 14px}}.tally dl>div+div{{padding-left:16px}}.tally .plate-name{{margin-bottom:12px}}}}
/* 一覧のスクロールバーは細くし、地の色に沈める。触れているときだけ少し明るくする（2026-10-22 かしぇ「ブラウザ標準のものを使っていてダサい」）。
   一覧の端まで来たあとのスクロールは本文へ渡さない（同「本文側がスクロールされるバグ」） */
aside{{overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:{palette.mix("sub", 30)} transparent}}
aside:hover{{scrollbar-color:{palette.mix("sub", 60)} transparent}}
aside::-webkit-scrollbar{{width:8px}}
aside::-webkit-scrollbar-track{{background:transparent}}
aside::-webkit-scrollbar-thumb{{background:{palette.mix("sub", 30)};border-radius:4px;border:2px solid transparent;background-clip:padding-box}}
aside:hover::-webkit-scrollbar-thumb{{background-color:{palette.mix("sub", 60)}}}
/* 右上のボタンの列（アプリとして入れる・感想と要望を送る・ヘルプ）。列ごと画面の右上に固定し、スクロールしても見えるようにする
   （2026-10-22 かしぇ「スクロールで隠れる位置にあるのよくない」）。入れる・送るはヘルプの隣に並べる（2026-10-25 かしぇ） */
.tools{{position:fixed;z-index:6;top:max(14px,env(safe-area-inset-top,0px));right:max(16px,env(safe-area-inset-right,0px));
display:flex;gap:10px;transition:opacity .2s}}
.tbtn{{position:relative;flex:none;width:40px;height:40px;padding:0;border:0;border-radius:50%;display:grid;place-items:center;text-decoration:none;cursor:pointer;
background:var(--ivory);color:var(--ivory-ink);box-shadow:0 0 0 1px var(--ivory-line),0 6px 14px -6px {palette.mix("umbra", 70)};
transition:transform .15s}}
.tbtn[hidden]{{display:none}}
.tbtn:hover{{color:var(--brass-dark)}}
.tbtn:active{{transform:scale(.94)}}
.tbtn:focus-visible{{outline:2px solid var(--ivory);outline-offset:3px}}
body.open .tools{{opacity:0;pointer-events:none}}
@media (max-width:760px){{.home .card{{padding:18px 14px 14px}}
 /* スマホの本体は中でスクロールする箱。既定では地の模様が箱に貼りついて札だけが滑るので、模様も一緒に動かす（札はコルク板に留めた標本） */
 main{{background-attachment:local}}
 /* スマホでは帯と一緒に右へずらす。画面に残したまま薄くすると、帯から取り残されて見えた（2026-10-22 かしぇ「ヘルプボタンがズレてた」） */
 .tools{{top:max(10px,env(safe-area-inset-top,0px));transform:translateX(var(--x,0px));transition:transform .25s cubic-bezier(.2,.8,.2,1)}}
 body.open .tools{{opacity:1}}
 body.dragging .tools{{transition:none}}}}
/* 一覧の幅を変えるつまみは、標本箱の蝶番のような真鍮の金具。ねじ頭を2つ打つ */
@media (min-width:761px){{
 .grip::after{{content:"";position:absolute;top:50%;left:1px;width:10px;height:46px;margin-top:-23px;border-radius:3px;
  background:radial-gradient(circle at 50% 9px,var(--brass-dark) 1.5px,transparent 2.2px),
   radial-gradient(circle at 50% 37px,var(--brass-dark) 1.5px,transparent 2.2px),var(--brass);
  box-shadow:inset 0 0 0 1px var(--brass-dark),0 2px 4px {palette.mix("umbra", 60)}}}
 .grip:hover::after,body.dragging .grip::after{{filter:brightness(1.08)}}
}}
/* PC の文字の大きさ。スマホに合わせた小さな字（11〜13px）が、PC の距離では読みにくかった（2026-10-22 かしぇ）。
   明朝の和文は細いので、補助の文字でも 13px を下限にし、本文は 17px に上げる */
@media (min-width:761px){{
 body{{font-size:17px}}
 aside .q{{font-size:15.5px}}
 aside .m,aside .m .chip{{font-size:13px}}
 .chip,.st{{font-size:12.5px;padding:.05em .6em}}
 thead th{{font-size:13.5px}}
 td.lbl,td.n,.topic td{{font-size:15.5px}}
 .hosts span{{font-size:13.5px}}
 dl.facts dt,.topic .note,summary{{font-size:14.5px}}
 .topic .docs a{{font-size:15px}}
 .topic .card>h3{{font-size:18px}}
}}
"""

CSS = """
:root{@@DASH_VARS@@
--serif:"Noto Serif JP","Hiragino Mincho ProN","Yu Mincho",serif;--latin:"EB Garamond",Georgia,serif;color-scheme:dark}
*{box-sizing:border-box}
html,body{overflow-x:clip}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--serif);font-size:16px;line-height:1.7}
a{color:var(--ink)}
header{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:16px max(16px,env(safe-area-inset-right,0px)) 12px max(16px,env(safe-area-inset-left,0px));border-bottom:1px solid var(--line);background:var(--paper2)}
header .ttl{font-family:var(--head);font-weight:500;letter-spacing:.04em;font-size:1.15rem}
header .help{flex:none;width:30px;height:30px;border:1px solid var(--line);border-radius:50%;display:grid;place-items:center;color:var(--sub);text-decoration:none;font-size:.85rem}
header .help:hover,header .help:focus-visible{color:var(--ink);border-color:var(--sub)}
header .menu{display:none;position:relative;width:40px;height:40px;flex:none;border:1px solid var(--line);background:var(--card);border-radius:8px;padding:0;cursor:pointer}
/* 2本線が開くと X に変わる（design-library の menu-cross-morph・makery: translateY＋rotate、0.2s ease-out） */
header .menu span,header .menu span::before{position:absolute;left:11px;width:18px;height:2px;border-radius:1px;background:var(--ink)}
header .menu span{top:15px;transition:transform .2s ease-out}
header .menu span::before{content:"";left:0;top:8px;transition:transform .2s ease-out}
body.open header .menu span{transform:translateY(4px) rotate(45deg)}
body.open header .menu span::before{transform:translateY(-8px) rotate(-90deg)}
header .menu:focus-visible{outline:2px solid var(--src);outline-offset:2px}
.layout{display:grid;grid-template-columns:var(--side,18rem) minmax(0,1fr);min-height:calc(100vh - 72px)}
.layout>*{min-width:0}
.side{position:sticky;top:0;align-self:start;height:100vh;background:var(--paper2);border-right:1px solid var(--line)}
body.collapsed .layout{grid-template-columns:0 minmax(0,1fr)}
body.collapsed aside{visibility:hidden}
aside{height:100%;overflow-y:auto;overflow-x:hidden;padding:12px 10px}
aside h2{font-family:var(--head);font-size:.8rem;color:var(--sub);font-weight:500;letter-spacing:.08em;margin:4px 6px 8px}
aside ol{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:minmax(0,1fr);gap:6px}
aside li{min-width:0}
aside a{display:block;padding:8px 10px;text-decoration:none;background:var(--paper);border:1px solid var(--line);border-left:3px solid var(--line);border-radius:6px}
aside a:hover,aside a:focus-visible{background:var(--card);border-color:var(--sub)}
aside .q{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.9rem;line-height:1.5}
aside .m{display:flex;gap:6px;align-items:center;font-size:.72rem;color:var(--sub);margin-top:2px;min-width:0}
.grip{position:absolute;top:50%;right:-15px;transform:translateY(-50%);width:14px;height:72px;padding:0;border:1px solid var(--line);border-left:none;border-radius:0 8px 8px 0;background:var(--paper2);cursor:ew-resize;touch-action:none;z-index:5}
.grip::before{content:"";position:absolute;left:5px;top:22px;bottom:22px;width:2px;border-left:1px solid var(--sub);border-right:1px solid var(--sub)}
.grip:focus-visible{outline:2px solid var(--src);outline-offset:2px}
body.dragging,body.dragging *{cursor:ew-resize!important;user-select:none}
.shade{display:none}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 16px 14px;margin:16px 0}
.card>h3{margin-top:10px}
.chip{display:inline-block;font-size:.7rem;border:1px solid var(--sub);border-radius:99px;padding:0 .5em;white-space:nowrap;color:var(--sub)}
.chip.none{border-style:dashed}
main{padding:24px max(16px,env(safe-area-inset-right,0px)) 64px 24px;max-width:60rem}
main h2{font-family:var(--head);font-weight:500;letter-spacing:.04em;font-size:1.4rem;margin:0 0 8px;text-wrap:balance}
main h3{font-family:var(--head);font-weight:500;font-size:1.05rem;letter-spacing:.04em;margin:32px 0 4px;border-bottom:1px solid var(--line);padding-bottom:4px}
.note{color:var(--sub);font-size:.85rem;margin:4px 0}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.88rem;font-variant-numeric:tabular-nums}
th,td{padding:5px 8px;text-align:left;vertical-align:middle}
thead th{font-weight:400;color:var(--sub);border-bottom:1px solid var(--line);font-size:.78rem}
td.n,th.n{text-align:right;width:3.5em;white-space:nowrap}
td.bar{width:45%;min-width:5rem}
td.bar span{display:block;height:10px;background:var(--bar);border-radius:0 4px 4px 0}
td.bar.src span{background:var(--src)}
td.lbl{overflow-wrap:anywhere}
.topic{display:none}
/* #t-… の札へ飛ぶときは、本体の一番上に着地させる（着地点を札の上端より上にずらすと、0 で止まる）。
   札の上端へ合わせると、札の頭が固定した頭の帯の裏に隠れた */
.topic{scroll-margin-top:100vh}
.topic:target{display:block}
main:has(.topic:target) .home{display:none}
/* スクリプトが動くとき（body.js）は、出す札を # ではなく印（.on）で決める。iPhone の録画で、札を切り替えるときに
   一瞬ホームが映った（2026-10-22 かしぇ）。# の書き換えの途中で、どの札も :target でないコマが描かれたと見ている。
   印は # の書き換えと同じ処理の中で付け替えるので、札の無いコマが描かれない。スクリプトが動かないときは # のまま */
body.js .topic:target{display:none}
body.js .topic.on{display:block}
body.js main:has(.topic:target) .home{display:block}
body.js main:has(.topic.on) .home{display:none}
/* 文書の枠。本体の頭の余白から下を、文書の枠でちょうど埋める。文書は枠の中でスクロールする */
.docview{display:none}
body.js .docview.on{display:block}
body.js main:has(.docview.on) .home{display:none}
.docview iframe{display:block;width:100%;border:0;background:transparent}
/* 文書の戻るボタン（形と色は文書の側の .imz-hud と同じ）。文書を開いている間だけ出し、一覧を開いている間は本体と一緒に退いて消える */
.dochud{display:none!important}
body.doc .dochud{display:grid!important;transform:translateX(var(--x,0px));transition:transform .25s cubic-bezier(.2,.8,.2,1),opacity .25s}
body.doc.open .dochud,body.doc.dragging .dochud{opacity:0;pointer-events:none}
body.dragging .dochud{transition:none}
/* パソコンではサイドバーが左に出たままなので、戻るボタンを紙面の左下（サイドバーの右）に置く。
   画面の左下のままだと、サイドバーの底のページ送りに重なった（2026-10-22 説明の図を撮って見つけた） */
@media (min-width:761px){body.doc .dochud{left:calc(var(--side,18rem) + 18px)}body.doc.collapsed .dochud{left:18px}}
/* スマホの本文（.view）は引っぱって更新のために transform を持ち、枠の位置の基準になる。高さを本体いっぱいにしておく */
@media (max-width:760px){body.doc main{padding:0;overflow:hidden}body.doc .view{height:100%}
 /* 枠（iframe）は上下の位置だけでは伸びない（既定の 150px のままだった）ので、高さを指定する */
 .docview iframe{position:absolute;left:0;right:0;top:calc(max(10px,env(safe-area-inset-top,0px)) + 51px);
  height:calc(100% - max(10px,env(safe-area-inset-top,0px)) - 51px)}}
@media (min-width:761px){body.doc main{padding:0;height:100vh;overflow:hidden}body.doc .view{max-width:none}.docview iframe{height:100vh}}
/* 文書の待ちと失敗の札（2026-10-25 かしぇ「詳細レポートとかで白い画面になるときに　読み込み中なのか　それとも鯖が立ってないのか判別つかない」）。
   止まったサーバーの手前の Tailscale は 502 を中身なしで返し、枠は読み込み中と同じく白いままだった。
   枠の真ん中に詳細の札と同じ象牙の紙を1枚置き、待ちの文と、失敗したら理由と次の行動を出す。待ちと失敗の間は枠を透かし、
   前の文書や白い失敗の画面を見せない。札の位置は枠と同じで、スマホは頭の帯の下から（上の .docview iframe と同じ式） */
.docview iframe{transition:opacity .2s}
.docview.pend iframe,.docview.fail iframe{opacity:0}
.docwait{position:absolute;inset:0;z-index:1;display:grid;place-items:center;padding:16px;pointer-events:none}
.docwait[hidden]{display:none}
@media (min-width:761px){.docview{position:relative}}
@media (max-width:760px){.docwait{top:calc(max(10px,env(safe-area-inset-top,0px)) + 51px)}}
.docwait .in{pointer-events:auto;width:min(26rem,100%);padding:20px 22px 18px;border-radius:3px;background-color:var(--ivory);background-image:@@PAPER@@;
 color:var(--ivory-ink);box-shadow:0 0 0 1px var(--ivory-line),0 16px 32px -14px color-mix(in oklch,var(--umbra) 85%,transparent);
 animation:docwait-in .3s cubic-bezier(.2,.8,.2,1);word-break:auto-phrase;line-break:strict}
@keyframes docwait-in{from{opacity:0;transform:translateY(6px)}}
.docwait .nm{margin:0 0 2px;font-size:.8rem;line-height:1.6;color:var(--ivory-sub);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.docwait h2{margin:0;font:600 1.05rem/1.5 var(--head),serif;letter-spacing:.04em}
.docwait .lead{margin:6px 0 0;font-size:.86rem;line-height:1.7;color:var(--ivory-sub);text-wrap:pretty}
.docwait .lead:empty{display:none}
/* 待ちの線。長さの分からない待ちなので、墨の短い線が罫の上を左から右へ流れる（parts/loader.md の線形の indeterminate）。
   落ち着いた画面なので、点滅や回転にせず、1.6秒のゆっくりした出入りの曲線で流す */
.docwait .bar{position:relative;display:block;height:2px;margin-top:14px;overflow:hidden;background:var(--ivory-line)}
.docwait .bar::before{content:"";position:absolute;top:0;bottom:0;left:0;width:32%;background:var(--ivory-ink);animation:docwait-bar 1.6s cubic-bezier(.45,0,.55,1) infinite}
/* 線の幅（32%）の何倍動かせば罫の端から端まで渡るか: 100% ÷ 32% = 312.5% */
@keyframes docwait-bar{from{transform:translateX(-100%)}to{transform:translateX(312.5%)}}
.docwait .acts{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
/* 上の display の指定は .docwait [hidden] と同じ強さで後ろにあり、hidden を付けても線とボタンが残った。強い指定で隠す */
.docwait .bar[hidden],.docwait .acts[hidden]{display:none}
/* 動きを減らす設定では、線を真ん中で止める。待ちであることは文で分かる */
@media (prefers-reduced-motion:reduce){.docview iframe{transition:none}.docwait .in{animation:none}.docwait .bar::before{animation:none;left:34%}}
/* 項目ごとに下へ細い罫を引いて、行の区切りを見せる（2026-10-22 かしぇ「区分けとかなく並べられてて読みづらい」）。
   罫が項目名と値の間で切れないよう、列の隙間は 0 にして項目名の右の余白で空ける */
dl.facts{display:grid;grid-template-columns:minmax(0,9rem) minmax(0,1fr);gap:0;margin:8px 0}
dl.facts dt,dl.facts dd{padding:9px 0;border-bottom:1px solid var(--line)}
dl.facts dt:last-of-type,dl.facts dd:last-of-type{border-bottom:0}
dl.facts dt{color:var(--sub);font-size:.85rem;padding-right:16px}
dl.facts dd{margin:0;overflow-wrap:anywhere}
ul.claims{list-style:none;padding:0;margin:8px 0}
ul.claims li{display:flex;gap:8px;align-items:baseline;margin:6px 0}
.st{flex:none;font-size:.7rem;border:1px solid var(--ink);border-radius:99px;padding:0 .5em}
.st.part{border-style:dotted}
.st.no{border-style:dashed;color:var(--sub);border-color:var(--sub)}
.docs{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.docs a{border:1px solid var(--ink);border-radius:6px;padding:4px 12px;text-decoration:none;font-size:.9rem;background:var(--card)}
.docs a:hover,.docs a:focus-visible{background:var(--paper2)}
.hosts{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.hosts span{font-size:.78rem;border:1px solid var(--line);border-radius:4px;padding:0 6px;overflow-wrap:anywhere}
.hosts b{color:var(--src);font-weight:600;margin-left:4px}
details{margin:8px 0;font-size:.85rem}
summary{cursor:pointer;color:var(--sub)}
footer{color:var(--sub);font-size:.78rem;margin-top:48px;border-top:1px solid var(--line);padding-top:12px}
@media (max-width:760px){
 .layout{grid-template-columns:minmax(0,1fr)}
  /* Discord 型（takubase の OverlappingPanes に合わせた）。一覧は下に敷き、頭と本文が右へ退いて見せる */
 /* 上下は画面の安全域（ノッチ・下のバー）の内側に合わせる。Artifact などの枠は :root に安全域ぶんの余白を足すので、
    一覧だけ端まで伸びると本文より上下に大きく見えた（2026-10-21 かしぇ） */
 /* 下端は画面の下まで伸ばす。本文は下の安全域の奥まで続くので、一覧だけ手前で切ると隙間に後ろの地が見えた */
 .side{position:fixed;left:0;top:env(safe-area-inset-top,0px);bottom:0;height:auto;align-self:stretch;width:84vw;z-index:0;border-right:none}
 /* グリッドの子なので、パソコン用の align-self:start が固定配置にも効き、中身の高さ（24px）まで縮んだ。伸ばす指定に戻す */
 header,main{position:relative;z-index:1;transform:translateX(var(--x,0px));transition:transform .25s cubic-bezier(.2,.8,.2,1),border-radius .25s cubic-bezier(.2,.8,.2,1)}
 /* 頭の帯は画面の上に固定する。流れのままだと、下へ読んだあと一覧を開くボタンまで戻らないといけなかった（2026-10-22 かしぇ）。
    固定すると高さを取るので、ボタンと件数を1段に並べる。右端は固定した説明のボタンの分だけ空ける。
    重なりは本体の縁の影の板（.frame・4）より上の 5。板の内側の影が帯の左端にかかって暗くなり、帯の色がずれて見えた
    （2026-10-22 かしぇ「ヘッダーは暗くならないようにしたい　色がずれるから」）。説明のボタン（6）はさらに上 */
 header{position:fixed;top:0;left:0;right:0;z-index:5;flex-wrap:nowrap;
  padding:max(10px,env(safe-area-inset-top,0px)) 68px 10px max(16px,env(safe-area-inset-left,0px))}
 /* 文書はスクロールさせず、本体を画面いっぱいの箱にして中でスクロールさせる（2026-10-22 レビュー: 両者の推奨）。
    前は文書のスクロールのまま、開くたびに body を固定し直し、ページの高さの本体を画面の座標で切り抜いていた。
    iPhone の Safari で、閉じた直後の約0.3秒、本体と一覧の上半分が描かれず黒く見えた（ops/reviews/2026-10-22-imozuru-dash-mobile-pane.md）。
    箱にすると、開閉でスクロール位置に触れず、角丸も箱の border-radius で切れる。代わりに Safari のツールバーはスクロールで縮まない。
    開いている間のスクロールは、本体を覆う暗い面（touch-action:none）が受け止める */
 /* 文書がずれる余地を残さない。iPhone の Safari は body の overflow:hidden では指のスクロールを止めず、
    外枠（.layout）の min-height（100vh はツールバーを畳んだ大きいほうの高さ）が見えている範囲より長いぶん、ページ全体が上へずれて
    ロゴが切れ、下にコルクの帯が出た（2026-10-22 かしぇの実機スクショ）。body は開閉にかかわらず常に画面へ固定し、バウンドも止める */
 html,body{height:100%;overflow:hidden;overscroll-behavior:none}
 body{position:fixed;inset:0}
 .layout{min-height:0}
 /* 端を越えて弾ませない。弾むと箱の外の描かれていない所が黒く見えた（2026-10-22 かしぇ「黒い見切れ」）。
    上端で下へ引いたときは、弾みの代わりに下の「引っぱって更新」を出す */
 main{position:fixed;inset:0;overflow-y:auto;overscroll-behavior:none}
 /* 引っぱって更新。--pull は本文を下げる量、--pp は進み具合（0〜1）。弧が描き上がると矢じりが付き、離せば読み込み直す */
 .view{transform:translateY(var(--pull,0px));transition:transform .3s cubic-bezier(.2,.8,.2,1)}
 body.pulling .view{transition:none}
 /* 重なりは 本体(1) < この札(2) < 帯(5)。札は帯の下から本体の上へ降りてくる */
 .ptr{display:grid;place-items:center;position:fixed;z-index:2;left:50%;top:calc(max(10px,env(safe-area-inset-top,0px)) + 62px);
  width:40px;height:40px;margin-left:-20px;border-radius:50%;background:var(--ivory);color:var(--ivory-ink);
  box-shadow:0 0 0 1px var(--ivory-line),0 6px 14px -6px color-mix(in oklch,var(--umbra) 70%,transparent);pointer-events:none;
  opacity:var(--pp,0);transform:translateX(var(--x,0px)) translateY(calc(var(--pull,0px) - 52px)) scale(calc(.6 + var(--pp,0) * .4));
  transition:opacity .3s,transform .3s cubic-bezier(.2,.8,.2,1)}
 body.pulling .ptr{transition:none}
 .ptr svg{transform:rotate(calc(var(--pp,0) * 270deg))}
 .ptr .arc{stroke-dasharray:1;stroke-dashoffset:calc(1 - var(--pp,0))}
 .ptr .head{opacity:0;transition:opacity .12s}
 body.ready .ptr .head{opacity:1}
 body.ready .ptr{color:var(--brass-dark)}
 body.refreshing .ptr svg{animation:ptr-spin .8s linear infinite}
 @keyframes ptr-spin{to{rotate:360deg}}
 /* 角丸は開いている間ずっと付け、閉じるときだけ四角へ動かす。開くときに動かすと角が徐々に丸くなって見え（2026-10-21 かしぇ「ずっと角丸にできない？」）、
    閉じるときに一度に外すと戻った瞬間に角が切り替わって見えた（同「ダサい」）。遷移は行き先の状態の指定が使われるので、開いた側から border-radius を外す */
 body.open main,body.dragging main{border-radius:34px 0 0 34px;transition-property:transform}
 body.open header,body.dragging header{border-top-left-radius:34px;transition-property:transform}
 /* 縦にスクロールする要素には、その要素自身に pan-y を宣言する。ブラウザは触れた所から最寄りの
    スクロールする祖先までしか touch-action を見ず、無いと横の操作をブラウザが取って中断する（takubase の規約） */
 html,body,header,main,aside,.tablewrap,pre{touch-action:pan-y}
 /* 表の箱は、はみ出していなくても横にスクロールする箱として扱われ、横の操作をブラウザが取った（20px で中断）。
    本当にはみ出す表だけスクリプトが横スクロールを戻し、そこから始めた操作は表に譲る */
 body.dragging header,body.dragging main,body.dragging .shade{transition:none}
 /* --p は開き具合（0〜1）。ドラッグ中はスクリプトが指の位置から入れ、暗い面と角丸がそれに合わせて濃くなる。
    開いた瞬間に暗さが最大まで跳ぶと、動きが途切れて見えた（2026-10-21 かしぇ「一瞬で暗くなる」） */
 body.open{--x:84vw;--p:1;overflow:hidden}
 body.collapsed .layout,.layout{grid-template-columns:minmax(0,1fr)}
 body.collapsed aside{visibility:inherit}
 /* 閉じている間は一覧を隠す。本文がページの下端で終わると、その下に一覧が透けて見えた（2026-10-21 かしぇ）。
    隠すのは閉じる動きが終わってから（遅らせないと、本体が戻る途中で一覧が消える） */
 .side{visibility:hidden;transition:visibility 0s .3s}
 body.open .side,body.dragging .side{visibility:visible;transition-delay:0s}
 /* 一覧の中身は、開くと奥から手前へ来る（少し小さく・ぼけて・薄い状態から、元の大きさでくっきり）。閉じると奥へ下がりながらぼける
    （2026-10-22 かしぇ「奥からぼかしを解除しながら出てくる　退場時に奥にぼけていく」）。
    開き具合 --p（0〜1）につなぐので、指で引いている途中も同じ変化が途中まで進む。
    動かすのは中身の包み（.side-in）1つだけ。ロゴの帯と一覧を別々に縮めると、それぞれの中心へ寄ってばらばらに動いて見えた
    （同日かしぇ「要素がばらついて縮小拡大しちゃう　全体をってことできない？」）。1つにまとめると、ぼかしの描き直しも1枚で済む。
    開くときは長め（0.34秒・減速）、閉じるときは短く（0.22秒・加速） */
 .side-in{opacity:var(--p,0);filter:blur(calc((1 - var(--p,0)) * 6px));transform:scale(calc(.94 + var(--p,0) * .06));transform-origin:30% 45%;
  transition:opacity .22s cubic-bezier(.4,0,1,1),filter .22s cubic-bezier(.4,0,1,1),transform .22s cubic-bezier(.4,0,1,1)}
 body.open .side-in{transition-duration:.34s;transition-timing-function:cubic-bezier(.2,.8,.2,1)}
 body.dragging .side-in{transition:none}
 @media (prefers-reduced-motion:reduce){.side-in{filter:none;transform:none;transition:none}}
 .grip{display:none}
 .shade{display:block;position:fixed;inset:0;z-index:2;touch-action:none;background:rgba(72,36,4,.25);transform:translateX(var(--x,0px));transition:transform .25s cubic-bezier(.2,.8,.2,1),opacity .25s cubic-bezier(.2,.8,.2,1);opacity:var(--p,0);pointer-events:none;border:0;padding:0}
 body.open .shade,body.dragging .shade{pointer-events:auto}
 header .menu{display:inline-block}
 @media (prefers-reduced-motion:reduce){header .menu span,header .menu span::before{transition:none}}
 header{gap:10px 12px;padding-bottom:10px}
 td.bar{width:35%}
 main{padding:calc(66px + max(10px,env(safe-area-inset-top,0px))) max(16px,env(safe-area-inset-right,0px)) calc(48px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px))}
 dl.facts{grid-template-columns:minmax(0,7.8rem) minmax(0,1fr)}  /* 「ユーザーの反応」が1行に収まる幅 */
 dl.facts dt{padding-right:10px}
 main h2{font-size:1.15rem}
}
@media (prefers-reduced-motion:reduce){header,main,.shade,.view,.ptr{transition:none!important}body.refreshing .ptr svg{animation:none}}
/* --- 標本箱（2026-10-21 協議: カードの一式をやめ、大胆さは詳細の紙面1か所に集める） --- */
/* ロゴは一覧の頭に固定し、項目はその下へ流れて消える（2026-10-21 かしぇ「ロゴの下をぼけながらフェードアウト」）。
   ロゴの面は一覧の上に重ね、背景のぼかしと地の色を下へ向けて薄くする。一覧はロゴの高さぶん下から始める */
.brand{position:absolute;top:0;left:0;right:0;height:var(--brand-h);z-index:2;pointer-events:none;display:flex;flex-direction:column;align-items:flex-start;padding:18px 18px 0}
/* ロゴの帯の下端のぼかしと薄れは外した。一覧がスクロールしていた頃、ロゴの下へ流れ込む項目を薄く見せるためのものだった。
   ページ送りになって項目はロゴの下へ入らなくなり、薄れだけが一覧の先頭に影のようにかかった（2026-10-22 かしぇ「不要な影が一覧の先頭にかかってる」） */
/* 一覧の検索。打つたびに一覧を絞る。iPhone は 16px 未満の入力欄に触れると画面を拡大するので、スマホでは 16px にする */
.find{position:relative;display:flex;align-items:center;align-self:stretch;margin-top:12px;pointer-events:auto}
.find .lens{position:absolute;left:11px;color:var(--sub);pointer-events:none}
.find input{width:100%;height:38px;margin:0;padding:0 34px;border:1px solid var(--line);border-radius:8px;
background:color-mix(in oklch,var(--glass) 6%,transparent);color:var(--ink);font:inherit;font-size:14.5px;-webkit-appearance:none;appearance:none}
.find input::placeholder{color:var(--sub);opacity:.85}
.find input:focus{outline:none;border-color:var(--sub);background:color-mix(in oklch,var(--glass) 10%,transparent)}
.find input::-webkit-search-cancel-button{-webkit-appearance:none;display:none}
.find .clear{position:absolute;right:4px;width:30px;height:30px;padding:0;border:0;border-radius:6px;background:none;color:var(--sub);cursor:pointer;display:none;place-items:center}
.find.has .clear{display:grid}
.find .clear:hover,.find .clear:focus-visible{color:var(--ink)}
@media (max-width:760px){.find input{font-size:16px}}
/* 当たった用語・人・媒体は、項目の下に1行で添える。題名で当たったときは出さない */
aside .hit{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.74rem;line-height:1.5;color:var(--sub);margin-top:2px}
aside .hit b{font-weight:600;color:var(--ink);margin-right:.6em}
aside li.off{display:none}
.find-none{margin:12px 10px 0 16px;color:var(--ink);font-size:.88rem}
.find-none[hidden]{display:none}
.find-none p{margin:0 0 4px}.find-none .where{color:var(--sub);font-size:.78rem}
.find-none button{margin-top:10px;padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card2);color:var(--ink);font:inherit;font-size:.82rem;cursor:pointer}
.find-none button:focus-visible{outline:2px solid var(--src);outline-offset:2px}
/* 当たった文字の印。デジタル庁のデザインシステムの検索ハイライト（薄い地＋濃い縁）に合わせ、色は標本の琥珀から取る */
aside mark{background:color-mix(in oklch,var(--bar) 30%,transparent);color:inherit;border-radius:2px;box-shadow:inset 0 -2px 0 color-mix(in oklch,var(--bar) 85%,transparent)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
/* ページ送り。一覧は画面に収まる分ずつ見せ、中ではスクロールさせない（2026-10-22 かしぇ「多くなってくると画面絶対重くなる」）。
   PC は一覧の底に、上のロゴの帯と対になる帯を置いて横に並べる。スマホは開いた一覧の右に残る本体の帯へ、× の下に縦に並べる */
.pager{display:flex;align-items:center;gap:6px;color:var(--sub);font-family:var(--latin);font-variant-numeric:lining-nums tabular-nums}
.pager button{width:36px;height:36px;display:grid;place-items:center;padding:0;border:1px solid var(--line);border-radius:8px;background:var(--card2);color:var(--ink);cursor:pointer}
.pager button:disabled{opacity:.35;cursor:default}
.pager button:focus-visible,.pager input:focus-visible{outline:2px solid var(--src);outline-offset:2px}
.pager input{width:2.4em;height:34px;margin:0;padding:0;text-align:center;border:1px solid transparent;border-radius:6px;background:none;color:var(--ink);font:inherit;font-size:18px}
.pager input:focus{outline:none;border-color:var(--sub);background:color-mix(in oklch,var(--glass) 8%,transparent)}
.pager .t{font-size:16px}
.pager.sp{display:none}
.pager.pc{position:absolute;left:0;right:0;bottom:0;height:64px;justify-content:center;z-index:2;padding-top:8px}
aside{padding-bottom:66px}
body.collapsed .pager.pc{visibility:hidden}
body.pg-one .pager{display:none}
@media (max-width:760px){
 .pager.pc{display:none}
 aside{padding-bottom:calc(12px + env(safe-area-inset-bottom,0px))}
 /* 頭の帯の子にして、本体と一緒に右へ退かせる。暗い面（z-index 2）より上の帯（3）に乗るので押せる */
 /* 帯の下は本体の札の上なので、頭の帯と同じ地の細長い板に載せる。板が無いと数字が札の文字と重なって読めなかった */
 .pager.sp{display:flex;flex-direction:column;gap:2px;position:absolute;left:max(16px,env(safe-area-inset-left,0px));top:calc(100% + 12px);width:40px;
  padding:0 0 2px;border:1px solid var(--line);border-radius:10px;background:var(--paper2);
  box-shadow:0 8px 18px -8px color-mix(in oklch,var(--umbra) 80%,transparent);opacity:0;pointer-events:none;transition:opacity .2s}
 .pager.sp button{border:0;background:none}
 body.open .pager.sp{opacity:1;pointer-events:auto}
 body.open.pg-one .pager.sp{display:none}
 .pager.sp button{width:40px;height:40px}
 .pager.sp input{width:40px}
 .pager.sp .rule{width:16px;height:1px;background:var(--sub)}
}
@media (prefers-reduced-motion:reduce){.pager.sp{transition:none}}
.brand .home-link>svg{height:58px;width:auto;max-width:100%;pointer-events:auto}
/* ロゴを押すとホームへ戻る（2026-10-22 かしぇ）。面は下の一覧を通すので、リンクだけ押せるようにする */
.brand .home-link{pointer-events:auto;display:inline-flex;border-radius:6px}
.brand .home-link:focus-visible{outline:2px solid var(--src);outline-offset:4px}
.brand .ttl{font-family:var(--head);font-size:1.5rem;letter-spacing:.06em;display:block}
aside{padding-top:calc(var(--brand-h) - 22px)}
body.collapsed .brand{visibility:hidden}
@media (max-width:760px){body.collapsed .brand{visibility:inherit}}
/* スマホでは一覧の地を右へ 48px 延ばす。本体の角を丸く切った外側は一覧の幅より右にあり、
   延ばさないとそこだけページの地の色が見えた（2026-10-21 かしぇ「角丸の部分の背景色がわかたれて」） */
@media (max-width:760px){.side{box-shadow:48px 0 0 var(--side-bg)}}
/* head には、ホーム画面の中での見え方を変える指定（apple-mobile-web-app-capable・status-bar-style・theme-color）を置かない。
   2026-10-22 に時刻の帯の色を合わせようとして足したところ、ホーム画面から開くと下に帯が出て本体が下まで届かなくなった。
   足す前は下まで伸びていた（かしぇ「サイドバー上部いじる前は下まで伸びてた」）ので、足したものを外して元に戻した。
   ホーム画面のアイコンは追加したときの指定を覚えているらしく、指定を変えたら追加し直す。
   安全域があるとき（横向き・ブラウザの全画面）に備え、一覧は上端から敷き、ロゴは安全域の下に置く */
@media (max-width:760px){.side{top:0;padding-top:env(safe-area-inset-top,0px)}}
/* 中身の包み。一覧の地（.side）の内側いっぱいに置き、ロゴの帯の基準にする。安全域の分は .side の上の余白で下がる */
.side-in{position:relative;height:100%}
/* ホーム画面から開いたとき（body.app・スクリプトが付ける）だけの指定。ブラウザで開いたときの見た目は変えない
   （2026-10-22 かしぇ「ブラウザで開いたときの見た目には影響しなくてほしくて」）。
   判定は display-mode の媒体指定ではなく navigator.standalone で行う。iPhone の実機で display-mode:standalone が当たらなかった（同日のスクショ） */
@media (max-width:760px){
 /* 一覧を時刻の帯の下へ沈んだ板に見せる。左端と上端は画面の端に付けたまま、左上をおよそ半径 47px（iPhone の画面の角と同じくらい）に丸め、
    左と上の内側に、ほんの少しだけぼかした影を落とす（かしぇ「左上を角丸に」「沈み込むような段差」「左のラインってのはあくまで左端に接地」
    「しずみこみはハードな影で描写するのみ」「ほんのちょっとだけぼかしいれて」）。
    角の外にはページの地が見えるので、本体の頭の帯と同じ色にする（かしぇ「左上に出てるコルクは本体画面のヘッダーの色にする」）。
    角で中身（ロゴの帯の地）がはみ出さないよう、板の外へ出る中身は切る。右へ延ばした地（box-shadow）は切られない */
 :root:has(body.app),body.app{background:var(--paper2)}
 body.app .side{border-top-left-radius:47px;overflow:hidden}
 body.app .side::before{content:"";position:absolute;inset:0;z-index:3;border-radius:inherit;pointer-events:none;
  box-shadow:inset 6px 6px 3px color-mix(in oklch,var(--umbra) 85%,transparent)}
}
/* 一覧は頭の帯より一段暗い地に置く。本体と一覧の境が見分けやすくなる（2026-10-21 かしぇ「もっと暗い色に」） */
.side{background:var(--side-bg)}
:root{--brand-h:172px;}
/* 折りたたみの中身は、高さと透明度を動かして開閉する（スクリプトが付ける） */
details.more>.more-body{overflow:hidden}
/* 折りたたみの三角は自前で描き、開閉に合わせて回す。閉じる動きの間（.closing）は、もう閉じた向きへ戻す */
summary{list-style:none;cursor:pointer}summary::-webkit-details-marker{display:none}
summary::before{content:"";display:inline-block;width:0;height:0;margin-right:.5em;vertical-align:.08em;border-style:solid;
border-width:.32em 0 .32em .5em;border-color:transparent transparent transparent currentColor;transition:transform .25s cubic-bezier(.2,.8,.2,1)}
details[open]:not(.closing)>summary::before{transform:rotate(90deg)}
@media (prefers-reduced-motion:reduce){summary::before{transition:none}}
header{background:var(--paper2);border-bottom:1px solid var(--line)}
main h2,main h3,aside h2{font-family:var(--head);font-weight:700}
summary,.note{color:var(--sub)}
a{color:var(--ink)}

/* 一覧: カードをやめて、罫線で区切った密な目録。左端の太い帯が区切った理由の色＝色で探せる */
aside ol{gap:0}
aside a{background:none;border:0;border-radius:0;box-shadow:none;padding:9px 10px 9px 16px;position:relative}
/* 区切りの罫線は途中から右へ薄れて消える（2026-10-21 かしぇ） */
aside a::after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;background:linear-gradient(90deg,var(--line) 40%,transparent)}
aside a::before{content:"";position:absolute;left:2px;top:9px;bottom:9px;width:5px;border-radius:3px;background:var(--c,transparent);box-shadow:0 0 8px -1px var(--c,transparent)}
aside a.none::before{background:none;border:1px dashed var(--line);width:3px}
aside a:hover,aside a:focus-visible{background:color-mix(in oklch,var(--glass) 5%,transparent)}
aside .m .chip{border:0;background:none;padding:0;color:var(--sub)}
aside .m .chip::before{display:none}

/* ホーム: 集計は箱に入れず、木の地に直接置く。見出しの書体と罫線で区切り、棒は太くして色の面積を増やす */
.home .card{background:none;border:0;box-shadow:none;padding:0;margin:36px 0 44px}
.home .card>h3{font-size:1.25rem;margin:0 0 6px;border-bottom:1px solid var(--line);padding-bottom:6px}
td.bar span{height:14px;border-radius:0 3px 3px 0;background:var(--bar)}
td.bar.src span{background:var(--src)}
/* 「class に rc を含む」で書くと src も当たって原文の棒が消えた。番号で名指しする */
td.bar.rc1 span,td.bar.rc2 span,td.bar.rc3 span,td.bar.rc4 span{background:var(--c)}
thead th{border-bottom-color:var(--line)}

/* チップ: 文字は墨のまま、標本の色は点で（文字を系列の色にしない） */
.chip,.st{border:1px solid var(--line);color:var(--ink);background:color-mix(in oklch,var(--paper2) 45%,transparent)}
.chip::before,.st::before{content:"";display:inline-block;width:.6em;height:.6em;border-radius:50%;margin-right:.35em;vertical-align:.02em;background:var(--c,var(--sub))}
.chip.none,.st.no{border-style:dashed;color:var(--sub)}
.rc1{--c:var(--r1)}.rc2{--c:var(--r2)}.rc3{--c:var(--r3)}.rc4{--c:var(--r4)}
.st{--c:var(--r1)}.st.part{--c:var(--r3);border-style:solid}.st.no{--c:transparent}

/* 詳細とホームの札: コルク板にピンで留めた象牙色の紙。ページの中で一番明るい面＝大胆さはここだけ。
   紙の繊維は SVG のノイズを一度だけ絵にして敷く（スクロールのたびに計算させない）。
   紙は板に貼り付いているので、大きくぼけた落ち影は付けない。前は板から浮いて見えた（2026-10-22 かしぇ「コルクにたいしてカードが浮いて影ついてるの意味わかんない」）。
   影は、紙の縁が板に触れる所の細い影と、下の両角が少し反った所の影（::after）だけにする */
.topic,.home .card{position:relative;background-color:var(--ivory);color:var(--ivory-ink);border-radius:3px;padding:30px 30px 24px;margin-top:8px;
background-image:@@PAPER@@;
box-shadow:0 1px 0 color-mix(in oklch,var(--glass) 50%,transparent) inset,0 0 0 1px color-mix(in oklch,var(--umbra) 16%,transparent),0 1px 2px color-mix(in oklch,var(--umbra) 45%,transparent)}
/* ピンは上の真ん中に1本。頭は紙の内側に刺さっている位置に置き、右下へ小さな影を落とす。詳細は区切った理由の色、ホームの札は真鍮 */
.home .card{--c:var(--brass)}
.topic::before,.home .card::before{content:"";position:absolute;top:8px;left:50%;width:16px;height:16px;margin-left:-8px;border-radius:50%;z-index:1;
background:radial-gradient(circle at 35% 30%,color-mix(in oklch,var(--glass) 80%,transparent),var(--c,var(--ivory-sub)) 45%,var(--paper2) 100%);
box-shadow:1px 2px 2px color-mix(in oklch,var(--umbra) 55%,transparent)}
/* 下の両角が板から少し反った影。札のすぐ下に、左右の端だけ濃く、内側へ向けて消える細い帯を置く */
.topic::after,.home .card::after{content:"";position:absolute;left:3px;right:3px;top:100%;height:9px;pointer-events:none;
background:radial-gradient(farthest-side at 0 0,color-mix(in oklch,var(--umbra) 50%,transparent),transparent) left top/44px 9px no-repeat,
radial-gradient(farthest-side at 100% 0,color-mix(in oklch,var(--umbra) 50%,transparent),transparent) right top/44px 9px no-repeat}
.topic h2,.topic a{color:var(--ivory-ink)}
/* 題の下の問いの全文。見出しより一段小さく、本文と同じ墨で */
.topic .question{margin:.1rem 0 .3rem;font-size:.95rem;line-height:1.75;color:var(--ivory-ink)}
.topic .note,.topic dt,.topic summary{color:var(--ivory-sub)}
.topic .card{background:none;border:0;box-shadow:none;padding:0;margin:22px 0 0}
.topic .card>h3{border-bottom-color:var(--ivory-line);font-size:1.02rem}
.topic .chip,.topic .st{border-color:var(--ivory-line);color:var(--ivory-ink);background:color-mix(in oklch,var(--glass) 45%,transparent)}
.topic .docs a{background:color-mix(in oklch,var(--glass) 50%,transparent);border:1px solid var(--ivory-line);color:var(--ivory-ink)}
.topic .docs a:hover,.topic .docs a:focus-visible{border-color:var(--ivory-ink)}
.topic .hosts span{border-color:var(--ivory-line);background:color-mix(in oklch,var(--glass) 40%,transparent)}
.topic .hosts b{color:var(--ivory-sub)}
/* 画面の切り替えの動きはスクリプトが本文（.view）にだけ付ける。説明の表の分類名は折り返さない */
.guide td{vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--ivory-line)}.guide td:first-child{white-space:nowrap}
.guide p,.guide li{line-height:1.8}.guide table{font-size:.85rem}.topic.guide::before{display:none}
/* 説明の節。流れの各段の下に、それが出る画面の項目を小さく添える。畳んだ中身は札の中で一段下げる */
.guide .lead{font-size:1.06rem;margin:6px 0 4px}
/* スキルのフローは段を1つずつ枠で囲み、番号を枠の左に置く（2026-10-22 かしぇ「一個ごとに囲って見やすくする」）。
   番号は SKILL.md の段と同じく0から数える */
.guide ol.flow{list-style:none;padding:0;margin:12px 0 4px;counter-reset:step -1}
.guide ol.flow li{counter-increment:step;display:grid;grid-template-columns:auto minmax(0,1fr);gap:12px;align-items:start;
 margin:8px 0;padding:11px 14px 12px 12px;border:1px solid var(--ivory-line);border-radius:10px;
 background:color-mix(in oklch,var(--glass) 30%,transparent)}
.guide ol.flow li::before{content:counter(step);width:1.7em;height:1.7em;border-radius:50%;display:grid;place-items:center;margin-top:.1em;
 font:700 .85rem/1 var(--head),serif;color:var(--ivory);background:var(--ivory-ink)}
.guide ol.flow .to{display:block;margin-top:4px;font-size:.84rem;color:var(--sub)}.guide ol.flow .to::before{content:"→ "}
.guide ul.parts{list-style:none;padding:0}.guide ul.parts li{margin:.35em 0}
.guide ul.parts b{display:inline-block;min-width:3.2em;margin-right:.6em;font-family:var(--head)}
.guide details.more{margin-top:10px}.guide details.more .more-body{padding:4px 0 2px 1.1em}
.guide code{overflow-wrap:anywhere}
/* 行き先を data-href へ移したリンクにも、押せる印の指の形を出す */
a[data-href]{cursor:pointer}
/* 右上のボタンは、パソコンでマウスを乗せると名前の札を下に出す（2026-10-22 かしぇ）。触る画面には乗せる動作が無いので出さない */
@media (hover:hover){.tbtn::after{content:attr(data-tip);position:absolute;top:calc(100% + 8px);right:0;white-space:nowrap;
 padding:4px 10px;border-radius:6px;background:var(--side-bg);color:var(--ivory);font:500 12.5px/1.5 var(--head),serif;letter-spacing:.08em;
 box-shadow:0 4px 12px -4px color-mix(in oklch,var(--umbra) 70%,transparent);opacity:0;transform:translateY(-3px);
 transition:opacity .15s,transform .15s;pointer-events:none}
 .tbtn:hover::after,.tbtn:focus-visible::after{opacity:1;transform:none}}
/* アプリとして入れる帯。急ぎの知らせではないので、フォーカスは奪わず、見出しつきの区画として画面の下に出す
   （design-library parts/alert.md「静的に置く枠は見出しを付けて region」）。閉じたら二度と出さない（右上のボタンは残る）。
   文書を読んでいる間とスマホで一覧を開いている間は、左下のボタンや一覧に重ならないよう出さない */
.inst-bar{position:fixed;z-index:7;left:max(16px,env(safe-area-inset-left,0px));right:max(16px,env(safe-area-inset-right,0px));
 bottom:max(16px,env(safe-area-inset-bottom,0px));margin-inline:auto;max-width:34rem;display:flex;align-items:center;gap:12px;
 padding:12px 10px 12px 14px;border-radius:10px;background:var(--ivory);color:var(--ivory-ink);
 box-shadow:0 0 0 1px var(--ivory-line),0 16px 32px -14px color-mix(in oklch,var(--umbra) 85%,transparent)}
.inst-bar[hidden],body.doc .inst-bar,body.open .inst-bar{display:none}
.inst-bar .ic{flex:none;width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:var(--side-bg);color:var(--ivory)}
.inst-bar .tx{flex:1;min-width:0}
.inst-bar h2{margin:0;font:600 .95rem/1.5 var(--head),serif;letter-spacing:.04em}
.inst-bar p{margin:0;font-size:.8rem;line-height:1.55;color:var(--ivory-sub)}
.inst-bar .x{flex:none;width:36px;height:36px;padding:0;border:0;border-radius:50%;display:grid;place-items:center;background:none;color:var(--ivory-sub);cursor:pointer}
.inst-bar .x:hover{color:var(--ivory-ink)}
.inst-bar .x:focus-visible{outline:2px solid var(--beni);outline-offset:1px}
/* 押せる面のボタン。主の操作は胡桃材の地に象牙の字、そのほかは線だけ */
.btn{flex:none;min-height:40px;padding:0 18px;border-radius:99px;border:1px solid var(--ivory-line);background:transparent;color:var(--ivory-ink);
 font:600 .92rem/1 var(--head),serif;letter-spacing:.06em;cursor:pointer;transition:transform .15s}
.btn.pri{background:var(--side-bg);border-color:var(--side-bg);color:var(--ivory)}
.btn:active{transform:scale(.96)}
.btn:focus-visible{outline:2px solid var(--beni);outline-offset:2px}
/* 小窓（感想と要望・アプリとして入れる手順）。標準の dialog を使い、背後を操作できなくする・Esc で閉じる・中でフォーカスを回すのはブラウザに任せる
   （parts/modal.md の解剖・APG）。見た目は詳細の札と同じ象牙の紙 */
dialog.dlg{width:min(31rem,calc(100vw - 32px));max-height:calc(100dvh - 48px);padding:0;border:0;border-radius:10px;overflow:auto;overscroll-behavior:contain;
 background-color:var(--ivory);background-image:@@PAPER@@;color:var(--ivory-ink);
 box-shadow:0 0 0 1px var(--ivory-line),0 24px 60px -20px color-mix(in oklch,var(--umbra) 90%,transparent)}
dialog.dlg::backdrop{background:color-mix(in oklch,var(--umbra) 55%,transparent)}
.dlg .in{position:relative;padding:22px 22px 18px}
.dlg h2{margin:0 40px 6px 0;font:600 1.15rem/1.5 var(--head),serif;letter-spacing:.05em}
.dlg .lead{margin:0 0 16px;font-size:.88rem;color:var(--ivory-sub)}
.dlg .x{position:absolute;top:12px;right:12px;width:40px;height:40px;padding:0;border:0;border-radius:50%;display:grid;place-items:center;background:none;color:var(--ivory-sub);cursor:pointer}
.dlg .x:hover{color:var(--ivory-ink)}
.dlg .x:focus-visible{outline:2px solid var(--beni);outline-offset:1px}
.dlg fieldset{border:0;padding:0;margin:0 0 16px;min-width:0}
.dlg legend,.dlg .lbl{padding:0;margin-bottom:6px;font:600 .9rem/1.5 var(--head),serif;letter-spacing:.04em}
.dlg legend small,.dlg .lbl small{font:400 .78rem var(--serif);color:var(--ivory-sub);margin-left:.4em}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chips label{position:relative}
.chips input{position:absolute;inset:0;margin:0;opacity:0;cursor:pointer}
.chips span{display:block;min-width:44px;min-height:36px;padding:6px 14px;text-align:center;border:1px solid var(--ivory-line);border-radius:99px;font-size:.9rem;line-height:1.5;
 transition:background-color .15s,border-color .15s,color .15s,transform .12s}
.chips input:checked+span{background:var(--side-bg);border-color:var(--side-bg);color:var(--ivory)}
/* iPhone は押した要素の箱に半透明の黒を一瞬かぶせる。札の上に重ねた四角い入力欄にそれが出て、丸い札に黒い四角が見えた
   （2026-10-25 かしぇ「種類　評価選択するときのアニメの挙動がなんか変（黒いシカクが一瞬出る）」）。
   小窓と帯の中ではそれを消し、押した反応は札が少し縮む動きで出す */
dialog.dlg *,.inst-bar *{-webkit-tap-highlight-color:transparent}
.chips input:active+span{transform:scale(.95)}
@media (prefers-reduced-motion:reduce){.chips span{transition:none}.chips input:active+span{transform:none}}
.chips input:focus-visible+span{outline:2px solid var(--beni);outline-offset:2px}
.dlg textarea{display:block;width:100%;min-height:8.5rem;resize:vertical;padding:10px 12px;border:1px solid var(--ivory-line);border-radius:8px;
 background:color-mix(in oklch,var(--glass) 30%,transparent);color:var(--ivory-ink);font:16px/1.7 var(--serif)}
.dlg textarea:focus-visible{outline:2px solid var(--beni);outline-offset:1px}
.dlg .what{margin:12px 0 0;font-size:.8rem;line-height:1.6;color:var(--ivory-sub)}
.dlg .acts{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}
.dlg .done{display:none}
.dlg.sent form{display:none}
.dlg.sent .done{display:block}
.dlg ol.how{margin:0;padding-left:1.4em}
.dlg ol.how li{margin:.35em 0}
.dlg [data-plat][hidden]{display:none}
/* 文書を PDF で保存するボタン。戻るボタンの右に、同じ形で並べる。文書を開いている間だけ出す */
.docprint{display:none!important;border:0;padding:0;cursor:pointer}
body.doc .docprint{display:grid!important;left:calc(max(14px,env(safe-area-inset-left,0px)) + 56px);transform:translateX(var(--x,0px));transition:transform .25s cubic-bezier(.2,.8,.2,1),opacity .25s}
body.doc.open .docprint,body.doc.dragging .docprint{opacity:0;pointer-events:none}
body.dragging .docprint{transition:none}
@media (min-width:761px){body.doc .docprint{left:calc(var(--side,18rem) + 74px)}body.doc.collapsed .docprint{left:74px}}
@media (max-width:760px){.inst-bar{gap:10px;padding:10px 8px 10px 12px}.inst-bar .ic{display:none}}
/* ダッシュボードの画面ごと刷られたとき（ブラウザの印刷を直接使ったときなど）は、一覧・ボタン・帯・地の質感を刷らない
   （2026-10-25 かしぇ「pdf印刷の時　文字以外の余計な要素がついてくる」） */
@media print{
 html,body,main{background:none!important}
 .side,header,.tools,.inst-bar,.docwait,.imz-hud,body.doc .dochud,body.doc .docprint,.ptr,.grip,.shade,.frame,.pager{display:none!important}
 .layout{display:block!important}
 body.doc main{height:auto!important;overflow:visible!important;padding:0!important}
}
/* 画面の図。スマホの図は紙の幅いっぱいでも 340px まで（PC で大きく出しすぎない）。番号の丸は絵の中の印と同じ紅紫 */
.guide figure.shot{margin:14px 0 18px}.guide figure.shot img{display:block;width:auto;max-width:min(100%,560px);max-height:560px;height:auto;border-radius:8px;
 box-shadow:0 0 0 1px var(--ivory-line),0 4px 10px -6px color-mix(in oklch,var(--umbra) 60%,transparent)}
.guide figure.shot figcaption{margin:0 0 8px;font-family:var(--head);font-weight:700;font-size:1.12rem;letter-spacing:.06em}
.guide figure.shot img{margin-bottom:8px}
.guide ol.legend{list-style:none;padding:0;margin:0}.guide ol.legend li{display:flex;gap:8px;align-items:baseline;margin:.3em 0}
.guide ol.legend .n{flex:none;width:1.45em;height:1.45em;border-radius:50%;background:var(--beni);color:var(--glass);font:700 .78rem/1.45em system-ui,sans-serif;text-align:center}
.guide ol.legend .n.only{background:none;color:var(--beni);box-shadow:inset 0 0 0 1.5px var(--beni)}

.grip{background:var(--paper2);border-color:var(--line)}
.grip::before{border-color:var(--sub)}
header .menu{background:var(--card2);border-color:var(--line)}
.shade{background:color-mix(in oklch,var(--umbra) 38%,transparent)!important}
/* 暗い面も本体と同じ角丸にする。四角のままだと、丸く切った角の外の一覧まで暗くなった（2026-10-21 かしぇ「影が角丸の外にもない？」） */
@media (max-width:760px){.shade{border-radius:34px 0 0 34px}}
/* 一覧を開くと、退いた本体の四隅をスマホの画面と同じ角丸に見せる（2026-10-21 かしぇ）。
   角は頭と本文の border-radius で丸く切り、外側には後ろの一覧がそのまま見える。
   この面は角丸に沿った内側の影だけを持つ。本体と一緒に動く */
.frame{display:none}
/* 引っぱって更新はスマホだけ。スマホ用の指定より後ろにあるので、幅で絞って上書きしないようにする */
@media (min-width:761px){.ptr{display:none}}
@media (max-width:760px){
 .frame{display:block;position:fixed;inset:0;z-index:4;pointer-events:none;opacity:0;transform:translateX(var(--x,0px));
 transition:transform .25s cubic-bezier(.2,.8,.2,1),opacity .25s cubic-bezier(.2,.8,.2,1);border-radius:34px 0 0 34px;
 /* 角の外側を色で塗ると、その下の一覧の文字が隠れた（2026-10-21 かしぇ「そっちこそ透けて欲しい」）。
    外へ広がる輪は、一覧の上にはみ出して縁取りに見えた。影は内側だけにする（かしぇ「いい感じだった影」） */
 box-shadow:inset 14px 0 22px -14px color-mix(in oklch,var(--umbra) 90%,transparent)}
 /* 角丸と影は引き始めから出しきる。引いた距離に合わせて出すと、角が徐々に丸くなるように見えた（2026-10-21 かしぇ「ずっと角丸にできない？」） */
 body.open .frame,body.dragging .frame{opacity:1}
 body.dragging .frame{transition:none}
}
@media (max-width:760px){.topic{padding:24px 16px 18px}.topic h2{font-size:1.05rem;font-weight:600;line-height:1.55}}
/* PC では一覧を画面の上端から下端まで通し、頭の帯は出さない（中身の一覧を開くボタンはスマホだけ）。説明のボタンは画面の右上に固定する。
   帯を全幅に渡すと、一覧のロゴの上に何も無い段ができた。本文の地は右端まで敷き、読む幅だけ .view で絞って中央に置く
   （main に最大幅を付けると、その右に別の地が縦の帯になって見えた・2026-10-22 かしぇ「PC 側の UI が終わってる」） */
@media (min-width:761px){
 header{display:none}
 .layout{min-height:100vh}
 main{max-width:none;padding:74px 28px 64px 24px}
 .view{max-width:60rem;margin-inline:auto}
 /* 幅を変えるつまみは境の線そのものにする。触れたときだけ線が明るくなる。線の中ほどに真鍮の金具を付け、畳んだときも左端に金具が残る */
 .grip{top:0;right:-6px;transform:none;width:12px;height:100%;border:0;border-radius:0;background:none}
 .grip::before{left:5px;top:0;bottom:0;width:0;border:0;border-left:2px solid transparent;transition:border-color .15s}
 .grip:hover::before,.grip:focus-visible::before,body.dragging .grip::before{border-left-color:var(--sub)}
 body.collapsed .grip{right:-14px}
}
"""
CSS = CSS.replace("@@DASH_VARS@@", palette.css_vars(palette.DASH))
CSS += CORK_CSS
CSS = CSS.replace("@@PAPER@@", texture_url("paper"))

# 文書の待ちと失敗の札の文（見出し・説明）。wait の見出しは文書の名前の後ろに付ける。
# サーバーに届かないときに service worker が返す代わりの画面（offline_html）も、down・local・nonet の文をここから取る
DOC_STATES = {
    "wait": ["を読み込んでいます", ""],
    "check": ["確かめています", "文書を開けなかったので、サーバーの様子を確かめています。"],
    "slow": ["時間がかかっています", "PC のサーバーからの返事を待っています。止まっていないかも確かめています。"],
    "alive": ["まだ読み込んでいます", "サーバーは動いています。大きな文書は時間がかかります。"],
    "down": ["サーバーが止まっています", "PC には届きましたが、ダッシュボードのサーバー（dashboard.py --serve）が動いていません。起動してから、もう一度読み込んでください。"],
    "local": ["サーバーが止まっています", "この PC のサーバー（dashboard.py --serve）が動いていません。起動してから、もう一度読み込んでください。"],
    "nonet": ["PC に届きません", "PC が起動しているか、この端末から PC へつながっているか（Tailscale など）を確かめてから、もう一度読み込んでください。"],
    "forbidden": ["合言葉を確かめられません", "起動したときに表示された、合言葉つきの URL で開き直してください。"],
    "missing": ["この文書は見つかりません", "調査のフォルダから消えたか、名前が変わった可能性があります。ページを読み込み直すと、一覧が今の中身に変わります。"],
    "other": ["文書を読み込めませんでした", "もう一度読み込んでください。"],
}


# 一覧の開閉。広い画面は一覧の右端のつまみをドラッグして幅を変える・畳む（押すだけでも開閉）。
# 狭い画面は takubase の OverlappingPanes（Discord 型）に合わせ、本文のどこでも横にスワイプして開閉する:
#  - 指が 15px 動くまでは何もせず、縦の動きが横の 1.5 倍以上なら縦スクロールに任せる（軸のロック）
#  - 画面の左右 24px から始めた操作は受けない（iOS の「戻る」スワイプに譲る）
#  - 0.3px/ms 以上で払えば向きで決め、ゆっくりなら動き始めから 72px で開閉を切り替える
#    （「半分以上」で決めると 84% 幅の一覧は大きく動かさないと開かない。takubase で実際に戻りが起きた）
#  - 開くと履歴を1つ積み、端末の戻るで閉じる。開いている間は本文に暗い面をかけ、押すと閉じる
# 幅と開閉は localStorage に覚える。スクリプトが動かなくても一覧は CSS だけで出ている
SIDE_JS = """(function(){var b=document.body,s=document.getElementById('side'),g=s.querySelector('.grip'),
// ホーム画面から開いたか。iPhone は navigator.standalone、ほかは display-mode で見る（CSS の body.app の指定が使う）
app=b.classList.toggle('app',navigator.standalone===true||matchMedia('(display-mode: standalone)').matches),
m=matchMedia('(max-width:760px)'),K='imozuru-side',LOCK=15,RATIO=1.5,EDGE=24,FLICK=0.3,COMMIT=72,last=288,pushed=false;
function st(v){try{localStorage.setItem(K,v)}catch(e){}}
try{var v=localStorage.getItem(K);if(v==='0')b.classList.add('collapsed');else if(v){last=+v;b.style.setProperty('--side',v+'px')}}catch(e){}
function W(){return s.getBoundingClientRect().width}
var mb=document.querySelector('header .menu'),mn=document.querySelector('main');
// スマホでは本体が画面いっぱいの箱で、その中がスクロールする。開閉は class を付け替えるだけで、スクロール位置にも角にも触れない
// （角丸と動きは CSS。前の body の固定と clip-path の切り抜きは、iPhone で閉じた直後に黒い帯を出した）
// 一覧を開くと履歴を1つ積み、閉じると戻る。iPhone は履歴を戻ったとき、#t-… の札の位置まで本体を自分でスクロールし直し、
// どこまで読んでいても同じ位置へ飛んだ（2026-10-22 かしぇ「サイドバーから復帰するときのスクロール位置が固定されちゃってて　そこにすっとぶ」）。
// ブラウザの位置の復元を止め、開いたときの読む位置を覚えておき、同じ札のまま閉じたらそこへ戻す。
// 戻る操作の popstate はあとから届くので、閉じた直後の popstate でも戻し、さらに2コマ後にもう一度戻す
try{history.scrollRestoration='manual'}catch(x){}
var keep=null;function hold(){if(!keep||keep.h!==location.hash)return;var y=keep.y;mn.scrollTop=y;
requestAnimationFrame(function(){requestAnimationFrame(function(){mn.scrollTop=y})})}
function setOpen(o,fromPop){if(o===b.classList.contains('open'))return;b.classList.toggle('open',o);mb.setAttribute('aria-expanded',String(o));
if(o){keep=m.matches?{h:location.hash,y:mn.scrollTop,t:0}:null;history.pushState({imozuruPane:1},'');pushed=true}
else{if(keep){keep.t=Date.now();hold()}if(pushed&&!fromPop){pushed=false;history.back()}else pushed=false}}
addEventListener('popstate',function(){if(b.classList.contains('open'))setOpen(false,true);else if(keep&&Date.now()-keep.t<800)hold()});
// 引っぱって更新（スマホ・本体の上端で下へ引いたとき）。本体の弾みは止めてあるので、自前で引く量を出す。
// 指の動きは pointer ではなく touch で受ける（縦の操作はブラウザがスクロールとして握り、pointer は途中で中断される）。
// 10px までは向きを決めず、横か上向きなら引かない（一覧を開く横のドラッグと分ける）。引く量は指の半分にして重さを出す
var PULL=64,pl=null;function pset(d){b.style.setProperty('--pull',d+'px');b.style.setProperty('--pp',Math.min(1,d/PULL).toFixed(3));b.classList.toggle('ready',d>=PULL)}
function pclear(){b.classList.remove('pulling','ready');b.style.removeProperty('--pull');b.style.removeProperty('--pp')}
mn.addEventListener('touchstart',function(e){pl=null;if(!m.matches||b.classList.contains('open')||b.classList.contains('refreshing')||mn.scrollTop>0||e.touches.length!==1)return;
pl={x:e.touches[0].clientX,y:e.touches[0].clientY,d:0,on:false}},{passive:true});
mn.addEventListener('touchmove',function(e){if(!pl)return;var dx=e.touches[0].clientX-pl.x,dy=e.touches[0].clientY-pl.y;
if(!pl.on){if(Math.hypot(dx,dy)<10)return;if(dy<=0||Math.abs(dx)>=Math.abs(dy)||mn.scrollTop>0){pl=null;return}pl.on=true;pl.y0=pl.y+dy;b.classList.add('pulling')}
if(e.cancelable)e.preventDefault();pl.d=Math.max(0,Math.min(PULL*1.6,(e.touches[0].clientY-pl.y0)*.5));pset(pl.d)},{passive:false});
function pend(){if(!pl)return;var g2=pl;pl=null;if(!g2.on)return;b.classList.remove('pulling');
if(g2.d>=PULL){b.classList.add('refreshing');pset(PULL);setTimeout(function(){location.reload()},450)}else pclear()}
mn.addEventListener('touchend',pend);mn.addEventListener('touchcancel',pend);
// 開いたまま幅 760px を越えたら閉じる（横向きにしたときなど）。PC の配置に開いた状態が残らないように
m.addEventListener('change',function(e){if(!e.matches&&b.classList.contains('open'))setOpen(false)});
document.querySelector('header .menu').addEventListener('click',function(){setOpen(!b.classList.contains('open'))});
document.querySelector('.shade').addEventListener('click',function(e){if(e.detail>0&&e.timeStamp-endAt<250)return;setOpen(false)});
// 画面の切り替え（ホーム・各調査・説明）は、どれも同じ1枚の中の節を出し分ける。# に合わせて show() が節に印（.on）を付ける。ページの読み込みは起きない。
// 動きは1種類にそろえる: 本文（.view）だけを短く薄くしてから差し替え、先頭へ戻して、上から留まるように出す。
// ページ全体の重ね合わせ（View Transitions）は、一覧が戻る動きと重なって変に見えたのでやめた（2026-10-21 かしぇ）
var vw=document.querySelector('.view'),RM=matchMedia('(prefers-reduced-motion:reduce)').matches,busy=null,ours=false;
function top0(){if(m.matches)mn.scrollTop=0;else scrollTo(0,0)}
function enter(){if(!RM&&vw.animate)vw.animate([{opacity:0,transform:'translateY(-8px)'},{opacity:1,transform:'none'}],{duration:240,easing:'cubic-bezier(.2,.8,.2,1)'})}
// 出す札に印（.on）を付ける。# の書き換えと同じ処理の中で呼び、札の無いコマを描かせない
// #doc/<調査>/<文書> は、文書を本体の枠（iframe）に開く。ヘッダーと一覧を残したまま読める（2026-10-22 かしぇ「ヘッダーとサイドバー外して　戻るHUD入れる意味ある？」）。
// 開ける文書は、詳細の札の文書のボタン（data-doc）に在るものだけ。窓口（http）のときは ?embed=1 で戻るボタンを外してもらう
// 枠の中身を差し替えるときは location.replace で読む。src を書き換えると履歴が1つ積まれ、端末の戻るで枠の中だけが戻った
var dv=document.getElementById('docview'),fr=dv.querySelector('iframe'),cur='';
// 文書の待ちと失敗の札。枠が白いままだと、読み込み中とサーバーの停止が見分けられなかった（2026-10-25）。
// 0.8秒たっても読み終わらなければ待ちの札を出す（1秒未満の待ちに表示は要らない・design-library animations/loading-family.md）。
// 読み終わったら枠の中身を見て、HTML の文書が入っていなければ失敗とする。窓口の 403・404 は文字だけのページ、
// 手前の Tailscale は止まったサーバーの代わりに中身の無い 502、つながらなければブラウザの失敗の画面で、どれも文書ではない。
// 理由は同じ URL を問い合わせ直して状態の番号で分ける。WebKit はつながらなかった枠に load を出さず、待ちの札のまま止まったので、
// 3秒たっても読み終わらなければ窓口の manifest に黙って問い合わせ、届かなければその時点で失敗の札にする（動いていれば文は替えない）。
// 10秒たっても読み終わらなければ文を替えて、もう一度確かめる（10秒を超える待ちは様子を伝える・同じ loading-family.md の Nielsen 1993）。
// 問い合わせは窓口（--serve）で開いたときだけ行う。
// 束をほかの置き場に載せたページでは CSP が問い合わせを止めるので、理由を分けずに読み直しだけを出す
var dw=document.getElementById('docwait'),dwn=dw.querySelector('.nm'),dwh=dw.querySelector('h2'),dwl=dw.querySelector('.lead'),
dwb=dw.querySelector('.bar'),dwa=dw.querySelector('.acts'),dwr=dwa.querySelector('button'),
dwweb=location.protocol.indexOf('http')===0,dwprb=dwweb&&!!document.querySelector('link[rel=manifest]'),
dwloc=['127.0.0.1','localhost','[::1]'].indexOf(location.hostname)>=0,dwq=0,dwp=false,dwf=false,dwt1=0,dwt2=0,dwt3=0,dwlb='',
DWM=@@DOC_STATES@@;
function dwset(k){var x=DWM[k],busy=k==='wait'||k==='check'||k==='slow'||k==='alive';dwh.textContent=k==='wait'?dwlb+x[0]:x[0];dwl.textContent=x[1];
dwb.hidden=!busy;dwa.hidden=k==='wait'||k==='check';dwr.textContent=k==='missing'?'ページを読み込み直す':'もう一度読み込む';dwr.setAttribute('data-k',k);dw.hidden=false}
function dwstop(){clearTimeout(dwt1);clearTimeout(dwt2);clearTimeout(dwt3)}
function dwfail(k){dwstop();dwf=true;dv.classList.remove('pend');dv.classList.add('fail');dwset(k)}
// 問い合わせの答えを理由に直す。0 は届かなかった（つながらない・6秒で打ち切り）。
// mode は、fail＝文書が開けなかったあと、quiet・slow＝読み込み中の確かめ。読み込み中に動いていると分かったら、
// quiet は何もせず、slow は文だけ替える。確かめている間に文書が読み終わっていたら何もしない
function dwask(q,url,mode){var c=window.AbortController?new AbortController():null,tm=setTimeout(function(){if(c)c.abort()},6000);
fetch(url,{cache:'no-store',credentials:'same-origin',signal:c?c.signal:undefined}).then(function(r){return r.status},function(){return 0}).then(function(st){clearTimeout(tm);
if(q!==dwq||mode!=='fail'&&(!dwp||dwf))return;
var k=st===0?(dwloc?'local':'nonet'):st===403?'forbidden':st===404?'missing':st>=500?'down':mode==='fail'?'other':'alive';
if(k!=='alive')dwfail(k);else if(mode==='slow')dwset(k)})}
function dwgo(u,doc){var a=document.querySelector('a[data-doc="'+CSS.escape(doc)+'"]'),t=document.getElementById('t-'+doc.split('/')[0]),h=t&&t.querySelector('h2'),q=++dwq;
dwlb=a?a.textContent:'文書';dwn.textContent=h?h.textContent:'';
dwstop();dwp=true;dwf=false;dw.hidden=true;dv.classList.remove('fail');dv.classList.add('pend');
dwt1=setTimeout(function(){if(q===dwq&&dwp)dwset('wait')},800);
dwt3=setTimeout(function(){if(q===dwq&&dwp&&dwprb)dwask(q,'manifest.webmanifest','quiet')},3000);
dwt2=setTimeout(function(){if(q!==dwq||!dwp||dwf)return;dwset('slow');if(dwprb)dwask(q,'manifest.webmanifest','slow')},10000);
try{if(cur)fr.contentWindow.location.replace(u);else fr.src=u}catch(x){fr.src=u}cur=u}
// Safari は枠を置いたときの about:blank でも load を出すので、読み込みを頼んだあと（dwp）だけ見る。
// ファイルを直接開いたページは枠の中を読めないので、読み終わったら成功とする
fr.addEventListener('load',function(){if(!dwp)return;dwp=false;var d=null,q=dwq;try{d=fr.contentDocument}catch(x){}
if(!dwweb||d&&d.contentType==='text/html'&&d.body&&d.body.firstElementChild){dwstop();dwf=false;dv.classList.remove('pend','fail');dw.hidden=true;return}
if(!dwprb){dwfail('other');return}
dwstop();if(!dw.hidden)dwset('check');else dwt1=setTimeout(function(){if(q===dwq&&!dwf)dwset('check')},400);dwask(q,cur,'fail')});
// 読み直しは同じ URL でも頼み直す（show は同じ文書なら何もしないので、ここから直接呼ぶ）
dwr.addEventListener('click',function(){if(dwr.getAttribute('data-k')==='missing'){location.reload();return}
dwgo(cur,decodeURIComponent(location.hash.slice(5)))});
// ページの中を移るリンク（調査・ヘルプ・ホーム・文書）は、行き先を data-href へ移して href を外す。href があると、
// マウスを乗せたときにブラウザが左下に行き先を出し、そこに合言葉つきの URL も見えた（2026-10-22 かしぇ「offれない？」）。
// スクリプトが動かないときは href のまま普通のリンクとして動く。外したリンクはキーボードで選べるよう tabindex を付ける
document.querySelectorAll('a[href^="#"],a[data-doc]').forEach(function(a){a.setAttribute('data-href',a.getAttribute('href'));a.removeAttribute('href');
a.setAttribute('role','link');a.tabIndex=0});
document.addEventListener('keydown',function(e){var a=e.target.closest&&e.target.closest('a[data-href]');if(a&&e.key==='Enter'){e.preventDefault();a.click()}});
function show(){var h=location.hash,el=null,doc=null;
if(h.indexOf('#doc/')===0){doc=decodeURIComponent(h.slice(5));if(!document.querySelector('a[data-doc="'+CSS.escape(doc)+'"]'))doc=null}
else el=h.length>1&&document.getElementById(decodeURIComponent(h.slice(1)));
document.querySelectorAll('.topic.on').forEach(function(t){if(t!==el)t.classList.remove('on')});if(el&&el.classList.contains('topic'))el.classList.add('on');
dv.classList.toggle('on',!!doc);b.classList.toggle('doc',!!doc);
if(doc)document.querySelector('.dochud').setAttribute('data-href','#t-'+doc.split('/')[0]);
// 失敗した文書は、もう一度開いたときに頼み直す
if(doc){var u=doc+(dwweb?'?embed=1':'');if(u!==cur||dwf)dwgo(u,doc)}}
b.classList.add('js');show();
function swap(hash,after){var apply=function(){if(location.hash!==hash){ours=true;location.hash=hash}show();top0();marks();if(after)after();enter()};
if(RM||!vw.animate){apply();return}if(busy)busy.cancel();
busy=vw.animate([{opacity:1},{opacity:0}],{duration:110,easing:'ease-in',fill:'forwards'});busy.onfinish=function(){busy.cancel();busy=null;apply()}}
// スマホで開いた一覧から選んだときは、Discord と同じく中身を差し替えてから本体を戻す
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[data-href]');if(!a||e.defaultPrevented)return;
var h=a.hasAttribute('data-doc')?'#doc/'+a.getAttribute('data-doc'):a.getAttribute('data-href');if(h==='#')h='';e.preventDefault();var closing=m.matches&&b.classList.contains('open');
swap(h,closing?function(){pushed=false;setOpen(false)}:null)});
// ブラウザは hash の節へのスクロールを後から行うので、hashchange でもう一度先頭へ戻す。
// 端末の戻る・進むで変わったときも、先頭へ戻して同じ動きで出す
addEventListener('hashchange',function(){show();top0();if(ours){ours=false;return}enter()});
// 文書の戻るボタンなど、#t-… つきで開いたときも、ブラウザが節の位置まで送るので読み込み後に先頭へ戻す。
// スマホでは送る先が本体の箱になり、送るのが load の後のコマになったので、2コマ後にもう一度戻す
addEventListener('load',function(){if(!location.hash)return;top0();requestAnimationFrame(function(){requestAnimationFrame(top0)})});
var t=null,endAt=-1e9;
function wide(el){var w=el&&el.closest&&el.closest('.tablewrap,pre');return w&&w.scrollWidth>w.clientWidth}
function marks(){document.querySelectorAll('.tablewrap,pre').forEach(function(w){w.style.touchAction=w.scrollWidth>w.clientWidth?'auto':''})}
marks();addEventListener('resize',marks);addEventListener('hashchange',marks);document.addEventListener('toggle',marks,true);
function pdown(e){if(!m.matches||e.button>0)return;
// リンクの上から始めた操作も受ける（開いた一覧の項目の上から閉じられるように）。ドラッグの直後のクリックは下で止める
if(e.target.closest&&e.target.closest('header .menu,summary,input,.pager,.find,dialog,.inst-bar,.tools'))return;
// 横にスクロールできる表の上で始めた操作は、表のスクロールに譲る
if(wide(e.target))return;
var open=b.classList.contains('open');if(!open&&(e.clientX<EDGE||e.clientX>innerWidth-EDGE))return;
var f=open?W():0;t={id:e.pointerId,x:e.clientX,y:e.clientY,axis:'p',v:null,lx:e.clientX,lt:e.timeStamp,from:f,cur:f};
if(e.pointerType==='mouse')e.preventDefault()}
document.addEventListener('pointerdown',pdown);
function pmove(e){if(!t||e.pointerId!==t.id)return;var dx=e.clientX-t.x,dy=e.clientY-t.y;
if(t.axis==='p'){if(Math.hypot(dx,dy)<LOCK)return;var ax=Math.abs(dx),ay=Math.abs(dy);
t.axis=ay>=RATIO*ax?'y':(ax>ay?'x':'p');if(t.axis==='y'){t=null;return}if(t.axis!=='x')return;
// 横に決まったら指の追跡をページが握る（指が要素の外へ出ても動きを拾い続ける）
try{b.setPointerCapture(t.id)}catch(x){}b.classList.add('dragging');t.kx=e.clientX;t.kt=e.timeStamp}
var dt=e.timeStamp-t.lt;if(dt>0){var inst=(e.clientX-t.lx)/dt;t.v=t.v===null?inst:0.5*inst+0.5*t.v}t.lx=e.clientX;t.lt=e.timeStamp;
t.cur=Math.min(W(),Math.max(0,t.from+dx));b.style.setProperty('--x',t.cur+'px');b.style.setProperty('--p',(t.cur/W()).toFixed(3))}
addEventListener('pointermove',pmove);
// iOS では指のドラッグが「放した」ではなく「中断」や「握りを失った」で終わることが多い。
// 軸が横に決まった後なら、終わり方によらず最後の位置と速さで開閉を決める（中断を「元に戻す」と読むと、放した瞬間に戻る）
function end(e){if(!t||e.pointerId!==t.id)return;var g0=t;t=null;if(g0.axis!=='x')return;
b.classList.remove('dragging');b.style.removeProperty('--x');b.style.removeProperty('--p');endAt=e.timeStamp;
var moved=g0.cur-g0.from,v=g0.v,open;
if(v===null)v=(g0.lx-g0.kx)/Math.max(1,g0.lt-g0.kt);
if(Math.abs(v)>=FLICK)open=v>0;else open=g0.from>0?moved>-COMMIT:moved>=COMMIT;setOpen(open)}
addEventListener('pointerup',end);addEventListener('pointercancel',end);
// 文書の枠（iframe）の上の指の動きは枠の中の文書が受け取り、ここへは届かない。文書（skin.FRAME_JS）が送ってくる
// 指の位置を、本体の上の指の動きとして同じ処理に渡す。これで枠の上でも横に引いて一覧を開閉できる
// （2026-10-22 かしぇ「サイドバー引っ張って開けないのは結構きつい」）。送り主は今の枠の中の文書だけを受ける
addEventListener('message',function(e){var d=e.data;if(e.source!==fr.contentWindow||!d||d.imz!=='touch')return;var r=fr.getBoundingClientRect();
var ev={pointerId:'frame',pointerType:'touch',button:0,target:fr,timeStamp:performance.now(),clientX:r.left+d.x,clientY:r.top+d.y,preventDefault:function(){}};
if(d.type==='down')pdown(ev);else if(d.type==='move')pmove(ev);
// 文書の一番上から下へ引いた量（pull）は、本体の引っぱって更新と同じ札と重さで見せ、離したら同じ基準で読み込み直す
else if(d.type==='pull'){if(!m.matches||b.classList.contains('open')||b.classList.contains('refreshing'))return;
b.classList.add('pulling');fp=Math.max(0,Math.min(PULL*1.6,d.dy*.5));pset(fp)}
else if(d.type==='pullend'){if(!b.classList.contains('pulling'))return;b.classList.remove('pulling');
if(fp>=PULL){b.classList.add('refreshing');pset(PULL);setTimeout(function(){location.reload()},450)}else pclear();fp=0}
else end(ev)});var fp=0;
// 横にドラッグした直後のクリック（指を放した所のリンクや暗い面）は、押したことにしない
document.addEventListener('click',function(e){if(e.detail>0&&e.timeStamp-endAt<250){e.preventDefault();e.stopPropagation()}},true);
// 握りを失った合図は、ページが握っていたときだけ終了と読む。子の要素から出た合図で終えると、握った直後に自分で止まる
b.addEventListener('lostpointercapture',function(e){if(e.target===b)end(e)});
var d=null;
g.addEventListener('pointerdown',function(e){if(m.matches)return;d={x:e.clientX,mv:false,w:b.classList.contains('collapsed')?0:W()};e.preventDefault()});
addEventListener('pointermove',function(e){if(!d)return;var dx=e.clientX-d.x;if(Math.abs(dx)>4&&!d.mv){d.mv=true;b.classList.add('dragging')}if(!d.mv)return;
b.classList.remove('collapsed');b.style.setProperty('--side',Math.min(520,Math.max(0,d.w+dx))+'px')});
addEventListener('pointerup',function(e){if(!d)return;var g1=d,dx=e.clientX-g1.x,w=Math.min(520,g1.w+dx);d=null;b.classList.remove('dragging');
if(!g1.mv){if(b.classList.toggle('collapsed'))st('0');else{b.style.setProperty('--side',last+'px');st(String(last))}return}
var close=g1.w===0?dx<COMMIT:(w<120||(dx<=-COMMIT&&w<200));
if(close){b.classList.add('collapsed');b.style.removeProperty('--side');st('0')}
else{w=Math.max(200,w);last=w;b.style.setProperty('--side',w+'px');st(String(w))}});
// 折りたたみ（details.more）の開閉を、中身の高さと透明度の動きでつなぐ。details は既定では一瞬で開閉する。
// 札の高さは動かさず、開いたらすぐ最終の高さにして、中身を切り抜きの範囲で上から見せていく。
// 高さを動かすと、Safari は札の影をコマごとに描き直す。「ほか N 媒体」は画面の10倍ほどの高さがあり、
// 1コマに約0.36秒かかって、一瞬で切り替わって見えた（2026-10-22 かしぇ「一瞬できりかわるように見えてる」）。
// 見せていくのは画面に見えている範囲だけ。閉じるときも同じ範囲を下から消し、終わってから open を外す
// 説明の節の画面の図は、見ている端末（760px を境にスマホとパソコン）の組だけを開いたまま残し、もう一方は畳む
document.querySelectorAll('#guide details[data-dev]').forEach(function(d){if(d.getAttribute('data-dev')!==(matchMedia('(max-width:760px)').matches?'sp':'pc'))d.open=false});
document.querySelectorAll('details.more').forEach(function(dt){var sm=dt.querySelector('summary'),bd=dt.querySelector('.more-body'),an=null;
function visible(){return Math.max(1,Math.min(bd.offsetHeight,innerHeight-bd.getBoundingClientRect().top))}
function clip(px){return 'inset(0 0 '+Math.max(0,bd.offsetHeight-px)+'px 0)'}
sm.addEventListener('click',function(e){if(matchMedia('(prefers-reduced-motion:reduce)').matches||!bd.animate)return;e.preventDefault();
var opening=!dt.open||dt.classList.contains('closing');if(an)an.cancel();
if(opening){dt.classList.remove('closing');dt.open=true;var v=visible();
an=bd.animate([{clipPath:clip(0),opacity:0,transform:'translateY(-6px)'},{opacity:1,offset:.5},{clipPath:clip(v),opacity:1,transform:'none'}],
{duration:520,easing:'cubic-bezier(.33,1,.68,1)'});an.onfinish=function(){an=null}}
else{dt.classList.add('closing');var v=visible();
an=bd.animate([{clipPath:clip(v),opacity:1},{clipPath:clip(0),opacity:0}],{duration:340,easing:'cubic-bezier(.65,0,.35,1)',fill:'forwards'});
an.onfinish=function(){if(dt.classList.contains('closing')){dt.open=false;dt.classList.remove('closing')}an.cancel();an=null}}})});
// 一覧の検索とページ送り。項目は消さずに class（.off）で隠す（選んでいる調査の印は :has() で項目を名指ししている）。
// 検索語は空白で区切り、全部の語がどこかに入っている調査を残す。探す先は 題名 → 題名の側（slug・日付・媒体のホスト）→ 読み（map.md の「読み:」）→ 用語・人・媒体。
// 題名で当たった所は光らせ、読み・用語・人・媒体で当たったら、その文を項目の下に1行添える（NN/g: 途中で当たる候補は、打った文字のほうを強調する）。
// 根拠は ~/research/ja-incremental-search（2026-10-22）。1ページの件数は決めず、一覧の高さに収まるまで項目の実際の高さを積んで区切る
var as=s.querySelector('aside'),ol=as.querySelector('ol'),fi=document.getElementById('find'),fl=fi.parentNode,
none=as.querySelector('.find-none'),live=document.getElementById('find-n'),pgs=[].slice.call(document.querySelectorAll('.pager'));
// 文字の畳み方。大文字小文字・カタカナとひらがな・全角と半角の英数を同じにする。1文字を1文字に直すので、当たった位置がそのまま元の文の位置になる
function fold(v){v=String(v).toLowerCase();var o='';for(var i=0;i<v.length;i++){var c=v.charCodeAt(i);
if(c>=0x30a1&&c<=0x30f6)c-=0x60;else if(c>=0xff01&&c<=0xff5e)c-=0xfee0;o+=String.fromCharCode(c)}return o}
// ローマ字の表。ヘボン式・訓令式・IME の打ち方（Google 日本語入力・MS-IME）を同じかなへ寄せる（Migemo もヘボン式と訓令式の両方を展開する）
var RK={};("a:あ i:い u:う e:え o:お ka:か ki:き ku:く ke:け ko:こ ca:か cu:く co:こ sa:さ si:し shi:し su:す se:せ so:そ ta:た ti:ち chi:ち tu:つ tsu:つ te:て to:と "+
"na:な ni:に nu:ぬ ne:ね no:の ha:は hi:ひ hu:ふ fu:ふ he:へ ho:ほ ma:ま mi:み mu:む me:め mo:も ya:や yu:ゆ yo:よ ra:ら ri:り ru:る re:れ ro:ろ "+
"wa:わ wi:うぃ we:うぇ wo:を ga:が gi:ぎ gu:ぐ ge:げ go:ご za:ざ zi:じ ji:じ zu:ず ze:ぜ zo:ぞ da:だ di:ぢ du:づ de:で do:ど "+
"ba:ば bi:び bu:ぶ be:べ bo:ぼ pa:ぱ pi:ぴ pu:ぷ pe:ぺ po:ぽ kya:きゃ kyu:きゅ kyo:きょ sya:しゃ sha:しゃ syu:しゅ shu:しゅ syo:しょ sho:しょ she:しぇ "+
"tya:ちゃ cha:ちゃ cya:ちゃ tyu:ちゅ chu:ちゅ cyu:ちゅ tyo:ちょ cho:ちょ cyo:ちょ che:ちぇ nya:にゃ nyu:にゅ nyo:にょ hya:ひゃ hyu:ひゅ hyo:ひょ "+
"mya:みゃ myu:みゅ myo:みょ rya:りゃ ryu:りゅ ryo:りょ gya:ぎゃ gyu:ぎゅ gyo:ぎょ zya:じゃ ja:じゃ jya:じゃ zyu:じゅ ju:じゅ jyu:じゅ zyo:じょ jo:じょ jyo:じょ "+
"je:じぇ dya:ぢゃ dyu:ぢゅ dyo:ぢょ bya:びゃ byu:びゅ byo:びょ pya:ぴゃ pyu:ぴゅ pyo:ぴょ fa:ふぁ fi:ふぃ fe:ふぇ fo:ふぉ va:ゔぁ vi:ゔぃ vu:ゔ ve:ゔぇ vo:ゔぉ "+
"thi:てぃ dhi:でぃ twu:とぅ xa:ぁ la:ぁ xi:ぃ li:ぃ xu:ぅ lu:ぅ xe:ぇ le:ぇ xo:ぉ lo:ぉ xya:ゃ lya:ゃ xyu:ゅ lyu:ゅ xyo:ょ lyo:ょ "+
"xtu:っ ltu:っ xtsu:っ ltsu:っ xwa:ゎ lwa:ゎ nn:ん xn:ん").split(' ').forEach(function(p){var i=p.indexOf(':');RK[p.slice(0,i)]=p.slice(i+1)});
// 打ちかけ（「yuuy」の「y」）を、続きうるかなの候補へ広げる表と、かなの母音（長音の揺れを畳むのに使う）
var ALT={},VOW={'ゃ':'a','ゅ':'u','ょ':'o'};Object.keys(RK).forEach(function(k){for(var l=1;l<k.length;l++){var p=k.slice(0,l);(ALT[p]=ALT[p]||[]).push(RK[k])}
var v=k.charAt(k.length-1);if(RK[k].length===1&&'aiueo'.indexOf(v)>=0)VOW[RK[k]]=v});
// ローマ字をかなへ。促音（kk→っ）と「ん」（子音の前の n）も扱う。末尾が打ちかけなら p に残す。英字が無ければ null
function kana(q){var out='',i=0,lat=false;while(i<q.length){var c=q.charAt(i),c2=q.charAt(i+1);
if(c<'a'||c>'z'){out+=c==='-'?'ー':c;i++;continue}lat=true;
if(c==='n'&&c2&&((c2<'a'||c2>'z')||"aiueoyn".indexOf(c2)<0)){out+='ん';i++;continue}
// 「konnichiha」の nn の後ろが母音なら「ん」＋な行に読む（探すときは打ち方の差を広く拾う）
var c3=q.charAt(i+2);if(c==='n'&&c2==='n'&&c3&&"aiueoy".indexOf(c3)>=0){out+='ん';i++;continue}
if(c===c2&&'aiueon'.indexOf(c)<0){out+='っ';i++;continue}
var L=4,hit=false;for(;L>0;L--){var key=q.substr(i,L);if(RK[key]){out+=RK[key];i+=L;hit=true;break}}if(hit)continue;
var rest=q.slice(i);if(ALT[rest])return {k:out,p:rest};out+=c;i++}return lat?{k:out,p:''}:null}
// 長音の揺れを畳む。「ゆうやけ」と「yuyake」、「とうきょう」と「tokyo」を同じにする（ヘボン式は長音を書かないことがある）。位置は保てないので光らせない
function flat(v){var o='';for(var i=0;i<v.length;i++){var c=v.charAt(i),pv=VOW[o.charAt(o.length-1)];if(c==='ー'||(c==='う'&&(pv==='u'||pv==='o'))||(c==='お'&&pv==='o'))continue;o+=c}return o}
// 1語を1つの文の中で探す。当たれば [位置, 長さ]（位置 -1 は長音を畳んで当たった＝光らせない）。変換前の字のままで当たらなければ、かなに直して探す
function find(h,k,kv){var i=h.indexOf(k);if(i>=0)return [i,k.length];if(!kv||!kv.k)return null;
var al=kv.p?ALT[kv.p]:[''];for(var j=0;j<al.length;j++){i=h.indexOf(kv.k+al[j]);if(i>=0)return [i,kv.k.length+al[j].length]}
var fh=flat(h);for(j=0;j<al.length;j++){var fk=flat(kv.k+al[j]);if(fk.length>1&&fh.indexOf(fk)>=0)return [-1,0]}return null}
var items=[].slice.call(ol.children).map(function(li){var w=[];try{w=JSON.parse(li.getAttribute('data-w')||'[]')}catch(x){}
var q=li.querySelector('.q'),t=q.textContent,r=li.getAttribute('data-r')||'';
return {li:li,a:li.querySelector('a'),q:q,t:t,f:fold(t),s:fold(li.getAttribute('data-s')||''),r:r,rf:fold(r),
w:w.map(function(p){return [p[0],p[1],fold(p[1])]})}}),shown=items,pages=[items],pi=0,seq=0,running=[];
// 題名を、当たった範囲に印（mark）を付けて組み直す
function mark(el,txt,rs){el.textContent='';rs.sort(function(x,y){return x[0]-y[0]});var at=0;rs.forEach(function(r){if(r[0]<at)return;
if(r[0]>at)el.appendChild(document.createTextNode(txt.slice(at,r[0])));var m=document.createElement('mark');m.textContent=txt.slice(r[0],r[0]+r[1]);el.appendChild(m);at=r[0]+r[1]});
if(at<txt.length)el.appendChild(document.createTextNode(txt.slice(at)))}
// 項目の下の1行。長い文は当たった所が見えるように、手前を「…」で詰める
function setHit(it,h){var el=it.a.querySelector('.hit');if(!h){if(el)el.remove();return}
if(!el){el=document.createElement('span');el.className='hit';it.a.appendChild(el)}
var txt=h[1],at=h[2],len=h[3];if(at>16){txt='…'+txt.slice(at-8);at=9}
el.textContent='';var k=document.createElement('b');k.textContent=h[0];el.appendChild(k);var body=document.createElement('span');el.appendChild(body);
mark(body,txt,at>=0&&len?[[at,len]]:[])}
function filter(){var q=fold(fi.value.normalize('NFKC')).split(' ').filter(Boolean);shown=[];
items.forEach(function(it){var hit=null,rs=[],ok=q.every(function(k){var kv=kana(k),m=find(it.f,k,kv);if(m){if(m[0]>=0)rs.push(m);return true}
if(find(it.s,k,kv))return true;
m=find(it.rf,k,kv);if(m){if(!hit)hit=['読み',it.r,m[0],m[1]];return true}
for(var i=0;i<it.w.length;i++){m=find(it.w[i][2],k,kv);if(m){if(!hit)hit=[it.w[i][0],it.w[i][1],m[0],m[1]];return true}}return false});
// 題名は1行で切れるので、後ろのほうで当たった印は見えない。そのときは当たった前後を下の1行に出す
if(ok&&!hit&&rs.length){rs.sort(function(x,y){return x[0]-y[0]});if(rs[0][0]>16)hit=['題名',it.t,rs[0][0],rs[0][1]]}
mark(it.q,it.t,ok?rs:[]);setHit(it,ok&&hit);if(ok)shown.push(it)});
none.hidden=shown.length>0;none.querySelector('.nq').textContent=fi.value;live.textContent=q.length?shown.length+'件':'';fl.classList.toggle('has',fi.value!=='')}
function room(){var cs=getComputedStyle(as);return as.clientHeight-parseFloat(cs.paddingTop)-parseFloat(cs.paddingBottom)}
// 区切り直す。keep に渡した項目が載るページを開く。畳んだ一覧（幅がほぼ0）は測れないので、開いたときに測り直す
function paginate(keep){if(as.clientWidth<120)return;var H=room(),hide={};stop();
items.forEach(function(it){it.li.classList.add('off')});shown.forEach(function(it){it.li.classList.remove('off')});
// 高さは端数まで測る。offsetHeight は整数に丸めるので、11件で合計が 2px 足りず、一覧がはみ出した
// スマホの一覧は閉じている間、奥へ下がった形（縮小）で置いてある。測った高さを縮小の分だけ戻す（transform は offsetHeight に効かない）
var sc=as.getBoundingClientRect().height/(as.offsetHeight||1)||1;
pages=[[]];var h=0;shown.forEach(function(it){var x=it.li.getBoundingClientRect().height/sc;if(h+x>H&&pages[pages.length-1].length){pages.push([]);h=0}pages[pages.length-1].push(it);h+=x});
if(keep)pages.forEach(function(p,i){if(p.indexOf(keep)>=0)pi=i});pi=Math.min(pi,pages.length-1);place();bar()}
function place(){items.forEach(function(it){it.li.classList.add('off')});pages[pi].forEach(function(it){it.li.classList.remove('off')})}
function bar(){b.classList.toggle('pg-one',pages.length<2);pgs.forEach(function(p){var n=p.querySelector('.pg-n');
if(document.activeElement!==n)n.value=pi+1;p.querySelector('.pg-t').textContent=pages.length;
p.querySelector('[data-step="-1"]').disabled=pi<=0;p.querySelector('[data-step="1"]').disabled=pi>=pages.length-1})}
function stop(){running.forEach(function(a){a.cancel()});running=[]}
// めくる動き。次へは今の項目が上へ薄れて退き、次の項目が下から順に留まる。前へは逆向き。
// 退場は短く（0.16秒・加速）、登場は長め（0.38秒・減速）にして、新しい項目に目が行くようにする。ずらしは1件 0.014〜0.022 秒で、8件で頭打ち
// 動きの途中でまためくったら、前の動きは終わった形（行き先のページ）に置いてから始める
function go(n,dir){n=Math.max(0,Math.min(pages.length-1,n));if(running.length){seq++;stop();place()}if(n===pi){bar();return}
var my=++seq,old=pages[pi]||[];
if(RM||!ol.animate||!dir){pi=n;place();bar();return}
var out=old.map(function(it,i){return it.li.animate([{opacity:1,transform:'none'},{opacity:0,transform:'translateY('+(-dir*14)+'px)'}],
{duration:160,delay:Math.min(i,8)*14,easing:'cubic-bezier(.4,0,1,1)',fill:'forwards'})});running=out.slice();pi=n;bar();
Promise.all(out.map(function(a){return a.finished})).then(function(){if(my!==seq)return;stop();place();
running=pages[pi].map(function(it,i){return it.li.animate([{opacity:0,transform:'translateY('+(dir*18)+'px)'},{opacity:1,transform:'none'}],
{duration:380,delay:Math.min(i,8)*22,easing:'cubic-bezier(.33,1,.68,1)',fill:'backwards'})})},function(){})}
// 絞り込み直したときは向きが無いので、1ページ目を短く出すだけにする
function refilter(){filter();pi=0;paginate();if(!RM&&ol.animate)running=pages[0].map(function(it,i){return it.li.animate([{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'none'}],
{duration:220,delay:Math.min(i,8)*12,easing:'cubic-bezier(.33,1,.68,1)',fill:'backwards'})})}
// 変換中も打つたびに絞る（欄の打ちかけのローマ字は kana() が続きの候補へ広げる）。Firefox は確定の input を compositionend より先に出すので、確定でも絞り直す
fi.addEventListener('input',refilter);fi.addEventListener('compositionend',refilter);
// Enter で先頭の調査を開き、Esc で検索語を消す。ただし変換中の Enter と Esc は IME のもの（確定・取り消し）なので触らない。
// Obsidian で、変換を確定する Enter が先頭の候補を開く不具合があった（ja-incremental-search の obsidian-ime-search.md）。Safari は keyCode 229 で見分ける
fi.addEventListener('keydown',function(e){if(e.isComposing||e.keyCode===229)return;
if(e.key==='Enter'&&shown.length){e.preventDefault();fi.blur();shown[0].a.click()}
else if(e.key==='Escape'&&fi.value){fi.value='';refilter()}});
function clearFind(){fi.value='';refilter();fi.focus()}
fl.querySelector('.clear').addEventListener('click',clearFind);none.querySelector('button').addEventListener('click',clearFind);
pgs.forEach(function(p){var n=p.querySelector('.pg-n');
p.addEventListener('click',function(e){var bt=e.target.closest('[data-step]');if(bt&&!bt.disabled){var d=+bt.getAttribute('data-step');go(pi+d,d)}});
// 番号は押すと全部選んだ状態になり、そのまま打ち替えられる。範囲の外の数は端のページに丸める
n.addEventListener('focus',function(){n.select()});
n.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();n.blur()}else if(e.key==='Escape'){n.value=pi+1;n.blur()}});
n.addEventListener('change',function(){var v=parseInt(String(n.value).normalize('NFKC'),10);if(isNaN(v)){n.value=pi+1;return}
var to=Math.max(0,Math.min(pages.length-1,v-1));go(to,to>pi?1:to<pi?-1:0);n.value=to+1});
n.addEventListener('blur',function(){n.value=pi+1})});
// PC は一覧の上のホイールでめくる（一覧はもうスクロールしないので、ホイールが本文へ渡らないようにもする）
var wacc=0,wat=0;as.addEventListener('wheel',function(e){if(m.matches)return;e.preventDefault();if(e.timeStamp-wat<350)return;
wacc+=e.deltaY;if(Math.abs(wacc)<40)return;var d=wacc>0?1:-1;wacc=0;wat=e.timeStamp;go(pi+d,d)},{passive:false});
// スマホは開いた一覧を縦に払ってめくる（上へ払うと次）。横の払いは一覧の開閉のほうが受ける
var sw=null;as.addEventListener('touchstart',function(e){sw=e.touches.length===1?{x:e.touches[0].clientX,y:e.touches[0].clientY}:null},{passive:true});
as.addEventListener('touchend',function(e){if(!sw||!m.matches)return;var c=e.changedTouches[0],dx=c.clientX-sw.x,dy=c.clientY-sw.y;sw=null;
if(Math.abs(dy)>48&&Math.abs(dy)>1.5*Math.abs(dx)){var d=dy<0?1:-1;go(pi+d,d)}});
function current(){var h=location.hash;for(var i=0;i<shown.length;i++)if(shown[i].a.getAttribute('data-href')===h)return shown[i];return null}
// 選んでいる調査が今のページに無いとき（直接 #t-… で開いた・戻るで戻った）は、それが載るページへ移る
function follow(){var c=current();if(!c||pages[pi].indexOf(c)>=0)return;for(var i=0;i<pages.length;i++)if(pages[i].indexOf(c)>=0){go(i,i>pi?1:-1);return}}
addEventListener('hashchange',follow);
// 一覧の高さが変わったら（画面の回転・PC の窓の大きさ・畳んだ一覧を開いた）区切り直す。今のページの先頭の項目を保つ
filter();paginate(current());
if(window.ResizeObserver)new ResizeObserver(function(){var k=current()||(pages[pi]||[])[0];paginate(k)}).observe(as);
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(function(){paginate(current()||(pages[pi]||[])[0])});
})();""".replace("@@DOC_STATES@@", json.dumps(DOC_STATES, ensure_ascii=False))

# アプリとして入れる・感想と要望を送る・文書を PDF で保存する（2026-10-25 かしぇ）。SIDE_JS とは別に置き、同じくハッシュで許す
FEATURE_JS = r"""(function(){var b=document.body,RM=matchMedia('(prefers-reduced-motion:reduce)');
// 出る・消えるの動き（design-library animations/modal-family.md: 開くは下から 16px・0.97 倍から約 0.3 秒で減速、閉じるは 0.2 秒で加速して去る。
// 開くのと同じ長さで閉じると、操作のあとに待たされる）
function rise(el,out,done){if(RM.matches||!el.animate){if(done)done();return}
var a=el.animate(out?[{opacity:1,transform:'none'},{opacity:0,transform:'translateY(10px)'}]:[{opacity:0,transform:'translateY(16px) scale(.97)'},{opacity:1,transform:'none'}],
{duration:out?200:300,easing:out?'cubic-bezier(.55,0,1,.45)':'cubic-bezier(.2,.8,.2,1)'});if(done)a.onfinish=done}
// 小窓は標準の dialog。閉じたらフォーカスを開いたボタンへ戻す（parts/modal.md・APG）
function openD(d){d._from=document.activeElement;d.showModal();rise(d,false)}
function closeD(d){if(d.open&&!d._closing){d._closing=true;rise(d,true,function(){d._closing=false;d.close()})}}
document.querySelectorAll('dialog.dlg').forEach(function(d){
d.addEventListener('cancel',function(e){e.preventDefault();closeD(d)});
d.addEventListener('close',function(){var f=d._from;d._from=null;if(f&&f.focus)f.focus()});
// 紙の外の暗い幕を押したときも閉じる。紙の中を押したときは閉じない
d.addEventListener('click',function(e){if(e.target!==d)return;var r=d.getBoundingClientRect();
if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeD(d)});
d.querySelectorAll('[data-close]').forEach(function(x){x.addEventListener('click',function(){closeD(d)})})});
// 窓口（--serve）で開いたときだけ service worker を入れる。次からはサーバーに届かないとき、白い画面の代わりに理由の札を出す（sw_js）。
// ファイルや束のページには manifest が無いので入れない。入れられなくても本体は動くので、失敗は黙って捨てる
if(document.querySelector('link[rel=manifest]')&&navigator.serviceWorker)navigator.serviceWorker.register('sw.js').catch(function(){});
// アプリとして入れる。窓口（http・https）で開いていて、まだアプリとして開いていないときだけ出す。ファイルを直接開いたページは入れられない
var ib=document.getElementById('inst'),bar=document.getElementById('inst-bar'),idl=document.getElementById('inst-dlg'),K='imozuru-install',ev=null,
web=/^https?:$/.test(location.protocol),ua=navigator.userAgent,ios=/iPhone|iPad|iPod/.test(ua)||(/Macintosh/.test(ua)&&navigator.maxTouchPoints>1),
plat=ios?'ios':/Android/.test(ua)?'android':/Firefox\//.test(ua)?'firefox':(/Safari\//.test(ua)&&!/Chrome\/|Chromium|Edg\//.test(ua))?'safari':'chromium';
// アプリの窓は body.app（standalone）に加えて minimal-ui も見る。manifest が無いうちに Edge の「このサイトをアプリとしてインストール」で入れた窓は
// minimal-ui で開き、standalone だけを見ると窓の中に入れる案内が残った（2026-10-25・Edge の記録の effective_display_mode が 2）。
// body.app はホーム画面の見た目にも使うので広げない。fullscreen は F11 の全画面のタブにも当たりうるので入れない
var inapp=b.classList.contains('app')||matchMedia('(display-mode: minimal-ui)').matches;
function gone(){ib.hidden=true;bar.hidden=true}
if(!web||inapp)gone();
else{ib.hidden=false;idl.querySelectorAll('[data-plat]').forEach(function(p){p.hidden=p.getAttribute('data-plat')!==plat});
var seen=null;try{seen=localStorage.getItem(K)}catch(x){}
if(!seen)setTimeout(function(){bar.hidden=false;rise(bar,false)},1200)}
// Chrome と Edge は、入れられる条件がそろうと beforeinstallprompt を出す（ページを押して 30 秒ほど見たあと・web.dev の install-criteria）。
// 届いていればブラウザの入れる画面を出し、届く前に押されたら、ブラウザごとの手順の小窓を出す
addEventListener('beforeinstallprompt',function(e){e.preventDefault();ev=e});
addEventListener('appinstalled',function(){gone();try{localStorage.setItem(K,'installed')}catch(x){}});
function install(){if(!ev){openD(idl);return}var e=ev;ev=null;e.prompt();e.userChoice.then(function(c){if(c.outcome==='accepted')gone()})}
ib.addEventListener('click',install);bar.querySelector('.go').addEventListener('click',install);
bar.querySelector('.x').addEventListener('click',function(){try{localStorage.setItem(K,'closed')}catch(x){}rise(bar,true,function(){bar.hidden=true})});
// 感想・要望を送る。送り先は作者の Google フォームで、送ると受付の画面が別のタブに開く。
// 送るのは書いた内容・版・ブラウザの名乗りだけ。ページの URL（合言葉を含む）と調査の題は入れない
var fb=document.getElementById('fb'),fd=document.getElementById('fb-dlg');
if(fb&&fd){var fm=fd.querySelector('form'),envf=fm.querySelector('[data-env]');
fb.addEventListener('click',function(){fd.classList.remove('sent');openD(fd)});
fm.addEventListener('submit',function(){if(envf)envf.value=ua;
// 送る中身はこの後でブラウザが読むので、消すのは次の処理に回す
setTimeout(function(){fm.reset();fd.classList.add('sent');var c=fd.querySelector('.done .btn');if(c)c.focus()},0)})}
// 文書を PDF で保存する。枠（iframe）の文書に印刷の見た目を差し込み、文の根拠と問いの答えを開いてから印刷の画面を出し、終わったら閉じ直す。
// 前に書き出した文書は印刷の見た目を持たないので、ここで足す。ファイルを直接開いたときは枠の中に触れられないので、文書を別のタブで開く。
// iPhone と Safari は枠の文書の印刷を頼んでも画面全体を刷るので、文書だけを1枚のページとして開き、そこで印刷の画面を出す（窓口の ?print=1）
var pb=document.querySelector('.docprint'),fr=document.querySelector('#docview iframe'),PCSS=@@PRINT_CSS@@;
if(pb&&fr)pb.addEventListener('click',function(){var w=fr.contentWindow,d=null;try{d=w.document;if(!d.body)d=null}catch(x){d=null}
if(!d){window.open(fr.src,'_blank','noopener');return}
if(web&&(ios||plat==='safari')){location.href=w.location.pathname+'?print=1';return}
if(!d.getElementById('imz-print')){var s=d.createElement('style');s.id='imz-print';s.textContent=PCSS;d.head.appendChild(s)}
var op=[];d.querySelectorAll('details.s:not([open]),details.ans:not([open])').forEach(function(x){x.open=true;op.push(x)});
w.addEventListener('afterprint',function(){op.forEach(function(x){x.open=false})},{once:true});
w.focus();w.print()});
})();""".replace("@@PRINT_CSS@@", json.dumps(skin.PRINT_CSS))

# サーバーに届かないとき、service worker（sw_js）が本体の代わりに返す1枚（2026-10-25 かしぇ「止まっているときの代わりの画面を端末に置いておく仕組み　ほしいね」）。
# 起動したときにサーバーが止まっていると、手前の Tailscale が中身の無い 502 を返し、本体ごと白い画面になった。
# 見た目は文書の札と同じ象牙の紙をコルク板に1枚置く。5秒ごとに窓口の manifest へ問い合わせ、返事があれば読み直す
# （かしぇが「自動でつなぎ直す」を選んだ）。service worker は合言葉なしで配るので、調査の題・中身・合言葉は入れない
OFFLINE_JS = ("(function(){var b=document.querySelector('.acts button'),busy=false;"
              "b.addEventListener('click',function(){location.reload()});"
              # 眠っている PC は接続を拒まず黙るので、1回の問い合わせは4秒で打ち切り、重ねて出さない。
              # 問い合わせ先は service worker の置き場所（data-scope）の下。文書のページ（/調査/digest.html）で出たときも窓口の manifest を見る
              "function check(){if(busy)return;busy=true;var c=window.AbortController?new AbortController():null,"
              "t=setTimeout(function(){if(c)c.abort()},4000);"
              "fetch(document.body.getAttribute('data-scope')+'manifest.webmanifest',{cache:'no-store',credentials:'same-origin',signal:c?c.signal:undefined})"
              ".then(function(r){if(r.status<500)location.reload()},function(){}).then(function(){clearTimeout(t);busy=false})}"
              "setInterval(check,5000)})();")


def offline_html() -> str:
    """代わりの画面。見出しと説明は @@H@@・@@LEAD@@、窓口の置き場所は @@SCOPE@@ のまま返し、service worker が入れる"""
    js_hash = "'sha256-" + base64.b64encode(hashlib.sha256(OFFLINE_JS.encode()).digest()).decode() + "'"
    csp = ("default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
           f"img-src data:; connect-src 'self'; script-src {js_hash}")
    css = (f':root{{{palette.css_vars(palette.DASH)}--head:{THEME["head"]},"Hiragino Mincho ProN","Yu Mincho",serif;'
           '--serif:"Noto Serif JP","Hiragino Mincho ProN","Yu Mincho",serif;color-scheme:dark}'
           "*{box-sizing:border-box}html,body{margin:0}"
           "body{min-height:100vh;min-height:100dvh;display:grid;place-items:center;"
           "padding:max(16px,env(safe-area-inset-top,0px)) max(16px,env(safe-area-inset-right,0px)) max(16px,env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px));"
           f"background-color:var(--cork);background-image:{texture_url('cork')};background-size:240px 240px;font-family:var(--serif);color:var(--ivory-ink)}}"
           # 札は本体の .docwait .in と同じ紙・影・入りの動き
           f".in{{width:min(26rem,100%);padding:22px 22px 18px;border-radius:3px;background-color:var(--ivory);background-image:{texture_url('paper')};"
           "box-shadow:0 0 0 1px var(--ivory-line),0 16px 32px -14px color-mix(in oklch,var(--umbra) 85%,transparent);"
           # 文節で折る指定（auto-phrase）は Safari に無いので、長音や小書きのかなを行頭に置かない指定（strict）も付ける
           "animation:in .3s cubic-bezier(.2,.8,.2,1);word-break:auto-phrase;line-break:strict}"
           "@keyframes in{from{opacity:0;transform:translateY(6px)}}"
           ".nm{margin:0 0 2px;font-size:.8rem;line-height:1.6;color:var(--ivory-sub)}"
           "h1{margin:0;font:600 1.15rem/1.5 var(--head);letter-spacing:.04em}"
           # 最後の行に「い。」だけが残る折り返しを避ける（WebKit の幅 390 で出た）
           ".lead{margin:6px 0 0;font-size:.88rem;line-height:1.7;color:var(--ivory-sub);text-wrap:pretty}"
           ".bar{position:relative;display:block;height:2px;margin-top:14px;overflow:hidden;background:var(--ivory-line)}"
           ".bar::before{content:\"\";position:absolute;top:0;bottom:0;left:0;width:32%;background:var(--ivory-ink);animation:bar 1.6s cubic-bezier(.45,0,.55,1) infinite}"
           "@keyframes bar{from{transform:translateX(-100%)}to{transform:translateX(312.5%)}}"
           ".poll{margin:10px 0 0;font-size:.8rem;line-height:1.6;color:var(--ivory-sub)}"
           ".acts{margin-top:16px}"
           ".btn{min-height:40px;padding:0 18px;border-radius:99px;border:1px solid var(--side-bg);background:var(--side-bg);color:var(--ivory);"
           "font:600 .92rem/1 var(--head);letter-spacing:.06em;cursor:pointer;transition:transform .15s}"
           ".btn:active{transform:scale(.96)}.btn:focus-visible{outline:2px solid var(--beni);outline-offset:2px}"
           "@media (prefers-reduced-motion:reduce){.in{animation:none}.bar::before{animation:none;left:34%}.btn{transition:none}}")
    return (f'<!doctype html>\n<html lang="ja"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            f'<meta http-equiv="Content-Security-Policy" content="{csp}">\n'
            f'<title>imozuru 調査記録</title>{skin.HEAD_META}'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;600&family={THEME["font"]}&display=swap">'
            f'<style>{css}</style></head>\n<body data-scope="@@SCOPE@@">'
            '<div class="in" role="status"><p class="nm">imozuru 調査記録</p><h1>@@H@@</h1><p class="lead">@@LEAD@@</p>'
            '<span class="bar" aria-hidden="true"></span><p class="poll">5秒ごとに確かめています。戻ったら自動で開きます。</p>'
            '<div class="acts"><button class="btn" type="button">もう一度読み込む</button></div></div>'
            f"<script>{OFFLINE_JS}</script></body></html>\n")


# 窓口が /sw.js で配る service worker。サーバーに届かないときだけ、最上位の画面に代わりの画面（offline_html）を返す
SW_JS = r"""// imozuru の調査記録の service worker。サーバーに届かないときだけ、本体の代わりの画面を返す。
// 調査のページは端末に置かない（窓口は no-store で返し、ここでも保存しない）。代わりの画面はこのファイルの中に持つので、
// 入れるときに取りに行くものは無い（ホーム画面のアプリは cookie を分けて持ち、合言葉の要る取得が通らないことがある）
var PAGE=@@PAGE@@,STATES=@@STATES@@,LOCAL=['127.0.0.1','localhost','[::1]'];
self.addEventListener('install',function(){self.skipWaiting()});
self.addEventListener('activate',function(e){e.waitUntil(self.clients.claim())});
// 横取りするのは最上位の画面の読み込みだけ。枠（iframe）の文書は本体の札が見分けるので、ここで代わりの画面を返すと
// 札が「文書が読めた」と取り違える。問い合わせ（manifest）・書体・アイコンは素通りさせる
self.addEventListener('fetch',function(e){var r=e.request;if(r.mode!=='navigate'||r.destination!=='document')return;e.respondWith(load(r))});
// 10秒たっても応答の頭が来なければ届かないとみなす（眠っている PC は接続を拒まず黙る）。応答の頭は中身より先に来るので、
// 窓口が動いていれば大きいページでも10秒はかからない。502・503・504 は手前の中継（Tailscale）がサーバーに届かなかった答え
function load(r){var t,late=new Promise(function(res){t=setTimeout(function(){res(null)},10000)});
return Promise.race([fetch(r).catch(function(){return null}),late]).then(function(x){clearTimeout(t);
if(x&&[502,503,504].indexOf(x.status)<0)return x;
var k=x?'down':LOCAL.indexOf(self.location.hostname)>=0?'local':'nonet',s=STATES[k];
return new Response(PAGE.replace('@@H@@',s[0]).replace('@@LEAD@@',s[1]).replace('@@SCOPE@@',self.registration.scope),
{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})})}
"""


def sw_js() -> str:
    """service worker の本文。代わりの画面の文は文書の札と同じ表（DOC_STATES）から取る。
    代わりの画面が変われば本文のバイトも変わり、ブラウザが新しい版に入れ替える"""
    states = {k: DOC_STATES[k] for k in ("down", "local", "nonet")}
    return (SW_JS.replace("@@PAGE@@", json.dumps(offline_html(), ensure_ascii=False))
            .replace("@@STATES@@", json.dumps(states, ensure_ascii=False)))


def bars(rows: list[tuple[str, int]], cls: str = "", head: str = "", unit: str = "", colors: dict | None = None) -> str:
    """横棒。共通の目盛り（最大値を全幅）で、値は棒の横に数字でも出す。
    colors を渡すと行ごとに標本の色（.rc1〜.rc4）で塗る＝一覧のチップと同じ色で対応させる。ラベルは必ず文字で出す"""
    if not rows:
        return '<p class="note">記録なし</p>'
    peak = max(v for _, v in rows) or 1
    body = "".join(
        f'<tr><td class="lbl">{esc(k)}</td><td class="bar {cls} {("rc%d" % colors[k]) if colors and k in colors else ""}"><span style="width:{v / peak * 100:.1f}%" '
        f'title="{esc(k)}: {v}{unit}"></span></td><td class="n">{v}</td></tr>' for k, v in rows)
    return (f'<div class="tablewrap"><table><thead><tr><th>{esc(head)}</th><th></th><th class="n">{esc(unit)}</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def reason_cls(t: dict) -> str:
    n = REASON_COLOR.get(t["reason_class"])
    return f"rc{n}" if n else "none"


def status_chip(status: str) -> str:
    cls = {"根拠あり": "", "一部のみ": " part", "根拠なし": " no"}.get(status, " no")
    return f'<span class="st{cls}">{esc(status)}</span>'


def title_of(t: dict) -> str:
    """一覧と詳細の見出しに出す名前。map.md の「題:」、無ければ問い、それも無ければ slug"""
    return t.get("title") or t["question"] or t["slug"]


def topic_html(t: dict) -> str:
    run = t["run"] or {}
    rounds = "記録なし" if t["rounds"] is None else f"{t['rounds']} 周"
    # 台帳の値は、数えた値と食い違うときだけ短く添える（説明は #guide の節に置く）。
    # 台帳は「2周」「原文32本」のように単位つきで書かれることがあるので、最初の数どうしで比べる
    def differs(ledger: str, counted) -> bool:
        m = re.search(r"\d+", ledger)
        return not m or int(m.group()) != counted
    if run.get("周") and differs(run["周"], t["rounds"]):
        rounds += f'<span class="note">（台帳 {esc(run["周"])}）</span>'
    srcs = f"{t['sources']} 本"
    if run.get("原文") and differs(run["原文"], t["sources"]):
        srcs += f'<span class="note">（台帳 {esc(run["原文"])}）</span>'
    facts = [("日付", esc(t["date"] or "記録なし")), ("周回数", rounds), ("原文", srcs),
             ("終了理由", (f'<span class="chip {reason_cls(t)}">{esc(t["reason_class"])}</span> '
                                    + esc(t["reason"])) if t["reason"] else "記録なし")]
    # 台帳の列名は「感覚と合った？」のまま。画面では誰の答えかが分かる名前で出す（2026-10-22 かしぇ）
    if run.get("感覚と合った？"):
        facts.append(("ユーザーの反応", esc(run["感覚と合った？"])))
    if t["searches"] is not None:
        line = f"検索 {t['searches']} 本・ヒット {t['hits']} 件"
        if t["fetch_ok"] is not None:
            line += f"・保存 {t['fetch_ok']}・取得失敗 {t['fetch_ng']}"
        facts.append(("検索と取得", line))
    else:
        facts.append(("検索と取得", "記録なし"))
    # 紙面の「← ホームへ」は置かない。ホームへはロゴで戻る（2026-10-22 かしぇ「ホームへ　のリンク廃止」）
    out = [f'<section class="topic {reason_cls(t)}" id="t-{esc(t["slug"])}">',
           f"<h2>{esc(title_of(t))}</h2>",
           # 題を見出しにしたときは、問いの全文を見出しのすぐ下に出す（問いは調べる範囲を決める文なので削らない）
           *([f'<p class="question">{esc(t["question"])}</p>'] if t.get("title") and t["question"] and t["question"] != t["title"] else []),
           f'<p class="note">{esc(t["slug"])}</p>',
           '<div class="card"><dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl></div>"]
    if t["docs"]:
        out.append('<div class="card"><h3>文書</h3><div class="docs">'
                   # data-doc があれば、スクリプトがダッシュボードの本体の枠に開く。動かないときは href の別ページで開く
                   + "".join(f'<a href="{esc(t["slug"])}/{esc(name)}" data-doc="{esc(t["slug"])}/{esc(name)}">{esc(label)}</a>'
                             for name, label in t["docs"]) + "</div></div>")
    if t["claims"]:
        out.append('<div class="card"><h3>調査の論点</h3><ul class="claims">'
                   + "".join(f"<li>{status_chip(s)}<span>{esc(c)}</span></li>" for c, s in t["claims"]) + "</ul></div>")
    if t["hosts"]:
        out.append('<div class="card"><h3>取得元</h3><div class="hosts">'
                   + "".join(f"<span>{esc(h)}<b>{n}</b></span>" for h, n in Counter(t["hosts"]).most_common()) + "</div></div>")
    out.append("</section>")
    return "\n".join(out)


# 説明の節に載せる画面の図（make_guide_shots.py が架空の調査を撮って作る）。
# 番号は絵の中の印と同じ。意味は絵のすぐ下に文字で書く（絵と説明を離すと、見比べる手間が増える）
# 説明の節に載せる画面の図の、画面ごとの部品・番号・説明。スマホとパソコンの図はどちらもこの表から作る
# （make_guide_shots.py が架空の調査を撮り、ここの部品に印を重ねる）。端末ごとに書き分けると、
# 指す部品と番号がずれた（2026-10-22 かしぇ「スマホとＰＣで解説している内容がバラついてるのがやばい」）。
# 両方の端末にある部品は数字（4つ目の欄が空）で、どちらの組にも同じ番号と説明で載る。
# 片方の端末にしか無い部品（スマホの ☰ と ×、パソコンのつまみ）は、その端末の組にだけ A・B の文字で載せる
# （同「スマホの＝と×の説明はあるべき　そこは臨機応変でしょ」）。
# 画面名は、名前だけで何の画面かが分かる語にする（同「画面名は　自己紹介でなくてはならない」で紙面→トピック詳細）。
# 部品は CSS のセレクタで、{dev} は端末（sp・pc）、{t} は撮るトピック詳細に置き換える
GUIDE_SCREENS = [
    ("home", "ホーム", [(".inst", "1", "アプリとして入れる。配信した画面（--serve）で開いたときに表示します", ""),
                       (".fb", "2", "作者へ感想・要望を送る。送り先のフォームがあるときに表示します", ""), (".help", "3", "ヘルプを表示", ""),
                       (".card.tally", "4", "全トピックの集計。下方に終了理由・原文の取得元・周回数の内訳が続きます", ""),
                       (".menu", "A", "サイドバーを表示", "sp")]),
    ("side", "サイドバー", [(".home-link", "5", "ロゴ。押すとホームへ移動します", ""), (".find", "6", "検索欄", ""),
                           (".pager.{dev}", "7", "ページ送り", ""),
                           ("aside li:first-child a", "8", "トピック1件。題名と日付。左端の色は終了理由の分類", ""),
                           (".menu", "B", "サイドバーを閉じる", "sp"),
                           (".grip", "A", "サイドバーの幅を調整するつまみ。押すと折り畳みます", "pc")]),
    ("topic", "トピック詳細", [("{t} dl.facts", "9", "トピックの記録", ""), ("{t} .docs", "10", "文書。選択すると、この枠内に表示します", ""),
                      ("{t} ul.claims", "11", "調査の論点と、原文の有無を示す印", "")]),
    ("doc", "文書閲覧", [(".docview iframe", "12", "表示中の文書", ""), (".dochud", "13", "トピック詳細へ戻る", ""),
                     (".docprint", "14", "この文書を PDF で保存（印刷）", "")]),
]


def screen_parts(legend: list[tuple[str, str, str, str]], dev: str) -> list[tuple[str, str, str, str]]:
    """画面の部品のうち、その端末の図に載るもの（両方にある部品と、その端末にだけある部品）"""
    return [x for x in legend if x[3] in ("", dev)]


def shot_html(name: str, caption: str, legend: list[tuple[str, str, str, str]]) -> str:
    """図を1枚、番号の説明と一緒に出す。絵が無ければ（make_guide_shots.py を回す前など）何も出さない"""
    png = LOGO.with_name(name)
    if not png.is_file():
        return ""
    src = "data:image/webp;base64," + base64.b64encode(png.read_bytes()).decode()
    items = "".join(f'<li><span class="n{"" if n.isdigit() else " only"}">{esc(n)}</span>{esc(t)}</li>' for _, n, t, _ in legend)
    # 題 → 図 → 番号の説明の順。何の画面かを先に読んでから図を見る（2026-10-22 かしぇ「ガメンタイトル→スクショ→解説がいいな」）
    return (f'<figure class="shot"><figcaption>{esc(caption)}</figcaption>'
            f'<img src="{src}" alt="{esc(caption)}。番号の印は下の説明と対応しています" loading="lazy"><ol class="legend">{items}</ol></figure>')


# 分類の意味。画面には名前だけを出し、意味は説明のページに置く
REASON_MEANING = {
    "論点充足": "全論点に原文が付いて終了",
    "一部充足": "一部の論点を残して終了",
    "期限到達": "依頼の時間・回数の上限に到達して終了",
    "取得不可": "残りの原文がログイン・有料・ボット対策の先にあり、取得できずに終了",
    "情報飽和": "新規に挙がる人物・資料の大半が、既に地図に存在",
    "周回上限": "4周追跡して終了",
}


def sentence_lines(markup: str) -> str:
    """説明の文の形をそろえる。項目の最後の文に句点が無ければ付け（同「。をさいごにつけてない部分はつける」）、
    文の終わり（。）ごとに改行を入れて1文ずつ行に分ける（同「ヘルプ画面の改行が　もっとしていいとおもう」・ja-writing の改行の段）。
    タグの中（画像の alt など）と、図の番号の説明（ol.legend）には改行を入れない。番号1つの説明は短く、
    途中で折ると番号との対応が崩れて見えた（同「同じ数字の中なら改行しない」）"""
    markup = re.sub(r"([^。>\s])</li>", r"\1。</li>", markup)
    out, skip = [], False
    for part in re.split(r"(<[^>]+>)", markup):
        if part.startswith("<"):
            skip = True if part.startswith('<ol class="legend"') else False if part == "</ol>" and skip else skip
            out.append(part)
        else:
            out.append(part if skip else re.sub(r"。(?=\S)", "。<br>", part))
    return "".join(out)


def guide_html(topics: list[dict]) -> str:
    """画面の説明（同じページの #guide の節）。数え方・分類の規則・操作をここに集め、ほかの画面には書かない。
    別のファイルにするとページの読み込みで画面が一瞬白くなったので、同じページの中に置く（2026-10-21 かしぇ）。

    上から読めば、この画面が何のためにあるかから分かるように、全体から詳細へ並べる
    （2026-10-22 かしぇ「そもそもこのアプリはなんなのか　というところから」「ただし認知負荷は削減」）。
    開いたまま読むのは、何の画面か・スキルのフロー・画面構成まで。操作・分類の表・集計方法は畳み、
    要る人だけが開く（慣れた人には要らない説明を押しつけない・~/research/cognitive-load-dataviz）。
    用語はスキルのフローの各段に「画面のどの項目に出るか」として添え、別の用語集は作らない（同じ説明を2か所に置かない）。
    imozuru そのものの説明は置かない。この画面を開く人は imozuru を使っている（同日かしぇ「要らない」）。
    文は「です・ます」で、和語に開いた言い方は熟語にする（同日かしぇ「日本語的に開かれた表現は積極的に熟語にする」）"""
    n = len(topics)
    with_reason = sum(1 for t in topics if t["reason_class"] != "記録欠落")
    with_hosts = sum(1 for t in topics if t["hosts"])
    with_rounds = sum(1 for t in topics if t["rounds"] is not None)
    fetch_topics = [t for t in topics if t["fetch_ok"] is not None]
    # 分類と状態は、画面に出ているのと同じ札（.chip・status_chip）で見せる。名前の文字だけだと、画面のどれのことか照らし合わせにくい
    # （2026-10-22 かしぇ「表示してるコンポーネントつかったほうがわかりやすくていい」）
    def reason_chip(label: str) -> str:
        return f'<span class="chip {reason_cls({"reason_class": label})}">{esc(label)}</span>'
    rules = "".join(f"<tr><td>{reason_chip(label)}</td><td>{esc(REASON_MEANING.get(label, ''))}</td><td>{esc('・'.join(words))}</td></tr>"
                    for label, words in REASON_RULES)
    rules += f"<tr><td>{reason_chip('記録欠落')}</td><td>台帳に記録が無い</td><td>—</td></tr>"
    fetch = (f"取得の成否の記録は {len(fetch_topics)}件にあります。" if fetch_topics else "取得の成否の記録があるトピックはまだありません。")

    # 画面構成は、図があれば図で見せる。図が無いときだけ文字の3行で書く。
    # スマホとパソコンの図を1組ずつ畳みに入れる。両方とも開いた状態で書き、スクリプトが見ている端末の組だけを開いたまま残す
    # （スクリプトが動かないときは両方開いたまま）。見ていない端末の図まで読ませない
    shots_sp, shots_pc = ("".join(shot_html(f"guide-{dev}-{key}.webp", title, screen_parts(legend, dev)) for key, title, legend in GUIDE_SCREENS)
                          for dev in ("sp", "pc"))
    shots = "".join(f'<details class="more" data-dev="{dev}" open><summary>{label}</summary><div class="more-body">{html_}</div></details>'
                    for dev, label, html_ in (("sp", "スマホの画面", shots_sp), ("pc", "パソコンの画面", shots_pc)) if html_)
    parts = ('<ul class="parts"><li><b>ホーム</b>最初に表示される画面です。全トピックの集計として、終了理由・原文の取得元・周回数の内訳を並べます</li>'
             '<li><b>サイドバー</b>トピックを新しい順に並べます。パソコンでは常に表示し、スマホでは左上のボタンで表示します。左端の色の帯は終了理由の分類です</li>'
             '<li><b>トピック詳細</b>サイドバーで選択したトピックの記録と文書です</li></ul>')

    def more(summary: str, body: str) -> str:
        return f'<details class="more"><summary>{summary}</summary><div class="more-body">{body}</div></details>'

    # 段は SKILL.md の「流れ」の 0〜4 と同じ番号と順にする。あとで SKILL.md を読む人が対応を取れるように
    # （2026-10-22 かしぇ「調べものの流れ　←スキルのフロー　とか　がいいかも」）
    flow = "".join(f"<li><div class=\"flow-step\">{esc(step)}。<span class=\"to\">{esc(item)}</span></div></li>" for step, item in (
        ("調査する疑問と、回答に必要な論点を3〜6個決定します。論点は「定番の手法は何か」「どこで失敗するか」のように、疑問を分割した小さな設問です", "調査の論点"),
        ("その分野の用語・人物・媒体を探索し、地図（map.md）に記録します。ここまでを0周目と呼びます", "文書の map.md"),
        ("引用・リンク・著者を追跡して原文を保存し、地図に追記します。一巡を1周と数えます", "周回数・原文・取得元"),
        ("各周の終了時に、継続か終了かを判断します。全論点に原文が付く、新規の資料が出現しなくなる、などの条件で終了します", "終了理由"),
        ("原文の抜き書きと、解説付きの詳細レポートを作成して提出し、結果が感覚と合致したかを依頼者に確認します", "文書・ユーザーの反応")))
    ops_sp = ("<li>サイドバーは、左上のボタンを押すか、本文を右へスワイプすると表示されます。左へスワイプするか、暗転した本文を押すと閉じます</li>"
              "<li>サイドバー上部の検索欄は、題名・疑問・用語・人物・媒体を対象に検索します。ひらがなやローマ字でも一致します</li>"
              "<li>サイドバーのページは、サイドバー表示中の右端の帯にある、× の下のボタンで送ります。サイドバーを上下にスワイプしても送れます（上へスワイプで次のページ）。番号を押すと直接入力できます</li>"
              "<li>画面の最上部で下へ引くと、記録を再読み込みします</li>"
              "<li>文書はトピック詳細の枠内に表示されます。左下のボタンでトピック詳細へ戻ります</li>")
    ops_pc = ("<li>サイドバー右端のつまみをドラッグすると幅を調整でき、押すと折り畳みます</li>"
              "<li>サイドバーのページは、サイドバー下端のボタンか、サイドバーの上でのホイール操作で送ります。番号を押すと直接入力できます</li>"
              "<li>サイドバー上部のロゴを押すと、ホームへ移動します</li>"
              "<li>配信した画面（<code>--serve</code>）を Chrome か Edge で開くと、右上の入れるボタンでアプリとして入れられます。タスクバーやスタートメニューから、ブラウザを開かずに起動できます</li>")
    # 両方の端末に共通の操作（2026-10-25 かしぇ「pdf出力」「フィードバック、レビュー送るモーダル」）
    ops_both = ("<li>文書の表示中は、左下の2つ目のボタンで、その文書を PDF で保存（印刷）できます。根拠の引用は開いた状態で印刷されます</li>"
                + ("<li>右上の吹き出しのボタンから、作者へ感想・要望を送れます。送るのは書いた内容とバージョン・ブラウザの種類だけです</li>" if feedback_form() else ""))
    ops_sp += ops_both
    ops_pc += ops_both
    phone = ("<ol><li>PC で <code>dashboard.py --serve</code> を実行します。合言葉付きの URL が表示されます</li>"
             "<li>PC とスマホに Tailscale（自分の機器同士だけを接続する VPN）を導入して同じアカウントで接続し、PC で <code>tailscale serve --bg 8765</code> を実行します</li>"
             "<li>スマホで <code>https://&lt;PC の名前&gt;.&lt;tailnet&gt;.ts.net/?k=&lt;合言葉&gt;</code> を開きます</li>"
             "<li>右上の入れるボタン（下向きの矢印）を押し、表示された手順でホーム画面に追加すると、ロゴのアイコンから起動できます</li></ol>"
             "<p>配信用の窓口は PC 内部（127.0.0.1）でのみ待ち受け、Tailscale が自分の機器にだけ中継します。"
             "合言葉は <code>IMOZURU_SERVE_TOKEN</code> で固定できます。固定しないと起動ごとに変化し、ホーム画面のアイコンから開けなくなります。</p>")
    claims = '<ul class="claims">' + "".join(f"<li>{status_chip(st)}<span>{esc(text)}</span></li>" for st, text in (
        ("根拠あり", "論点に原文の場所が付いています。"), ("一部のみ", "論点の一部にのみ原文が付いています。"),
        ("根拠なし", "探索したものの、原文が付いていません。"), ("未確認", "抜き書きが未作成のトピックで、地図の論点にまだ印がありません。"))) + "</ul>"
    counts = (f"<ul><li>トピック: 調査の保存先（既定 <code>~/research</code>）直下のフォルダ1つを1件と数えます</li>"
              f"<li>原文: <code>sources/</code> のファイルを、拡張子を除いた名前で集計します（PDF とその文字起こしは1本）</li>"
              f"<li>周回数: <code>log.md</code> の「N周目」の見出しと検索の記録から集計します。0周目（地図作成）は含みません。{n}件中 {with_rounds}件に記録があります</li>"
              f"<li>取得元: <code>map.md</code> の原文の表の URL を、媒体ごとに集計します。ホームには上位{SHOWN_HOSTS}件を表示します。{n}件中 {with_hosts}件に記録があります</li>"
              f"<li>検索と取得: <code>queries.jsonl</code> と <code>fetch-log.jsonl</code> から集計します。{fetch}</li>"
              f"<li>終了理由・ユーザーの反応: 台帳（<code>--runs</code> で指定する <code>evals/runs.md</code>）から読み取ります。台帳に無いトピックは「記録欠落」「記録なし」となります。{n}件中 {with_reason}件に記録があります</li>"
              "<li>台帳記載の周回数・原文数が集計値と異なる場合のみ、括弧で台帳の値を併記します</li>"
              "<li>「記録なし」は、0 と区別するための表示です</li></ul>")
    return sentence_lines(f"""<h2><span lang="en">imozuru</span> 調査記録とは</h2>
<p class="lead">imozuru で行った調査を、トピックごとに並べたダッシュボードです。トピックは1つの疑問について調べたひとまとまりのことを指します。過去のトピックとその文書を探し出し、それぞれがどこまで進んでどう終わったかを見比べられます。</p>
<div class="card"><h3>スキルのフロー</h3>
<p>imozuru は1つのトピックを、次の段の順に進めます。各段の下の名前は、その結果が出る画面の項目です。</p>
<ol class="flow" start="0">{flow}</ol></div>
<div class="card"><h3>画面構成</h3>
{shots or parts}
{more("スマホでの操作", f"<ul>{ops_sp}</ul>")}
{more("パソコンでの操作", f"<ul>{ops_pc}</ul>")}</div>
<div class="card"><h3>スマホでの閲覧</h3>
<p>PC で配信した画面を、スマホのブラウザで閲覧できます。</p>
{more("手順", phone)}</div>
<div class="card"><h3>分類と状態</h3>
{more("終了理由の分類", f'<p>imozuru はトピックごとに、終了理由などを台帳（<code>evals/runs.md</code>）へ1行記録します。その「調査を区切った理由」の文に「判定語」のいずれかが含まれれば、その分類とします。上の行ほど優先して判定します。元の文は各トピック詳細に掲載しています。</p><div class="tablewrap"><table><thead><tr><th>分類</th><th>意味</th><th>判定語</th></tr></thead><tbody>{rules}</tbody></table></div>')}
{more("調査の論点の状態", "<p>トピック詳細の「調査の論点」で、各論点の先頭に付く印です。</p>" + claims)}</div>
<div class="card"><h3>集計方法</h3>
<p>数値はすべて、各トピックのフォルダの記録から機械的に集計しています。</p>
{more("項目別の集計方法", counts)}</div>""")


def home_html(topics: list[dict]) -> str:
    reasons = Counter(t["reason_class"] for t in topics if t["reason_class"] != "記録欠落").most_common()
    hosts = Counter(h for t in topics for h in t["hosts"])
    by_date = [t for t in topics if t["rounds"] is not None]
    # 見出しは短い熟語にする（2026-10-21 かしぇ「画面に出すタイトルとしては冗長」）。
    # 画面には数字と見出しだけを置き、数え方や分類の規則は #guide の節に書く（2026-10-21 かしぇ「長々と注釈や操作案内を書きたくない」）
    # 調査と原文の総数は、ホームの最初の札に大きく置く（2026-10-22 かしぇ「ダッシュボード上の最初の大きな要素にする」）。
    # 前は頭の帯の小さな文字だった
    total_sources = sum(t["sources"] for t in topics)
    out = ['<section class="home">',
           # 札の頭に画面の名前を置く。ロゴは一覧の上にしかなく、スマホでは一覧を開くまで何の画面か分からない
           # （2026-10-22 かしぇ「この画面が何であるかを知らせるため」）
           '<div class="card tally"><h1 class="plate-name"><span lang="en">imozuru</span> 調査記録</h1>'
           f'<dl><div><dt>トピック</dt><dd><b>{len(topics)}</b>件</dd></div>'
           f'<div><dt>原文</dt><dd><b>{total_sources}</b>本</dd></div></dl></div>',
           '<div class="card"><h3>終了理由</h3>',
           bars(reasons, head="分類", unit="件", colors=REASON_COLOR), "</div>",
           '<div class="card"><h3>取得元</h3>',
           bars(hosts.most_common(SHOWN_HOSTS), cls="src", head="媒体", unit="本")]
    if len(hosts) > SHOWN_HOSTS:
        out.append(f'<details class="more"><summary>ほか {len(hosts) - SHOWN_HOSTS} 媒体</summary><div class="more-body">'
                   + bars(hosts.most_common()[SHOWN_HOSTS:], cls="src", head="媒体", unit="本") + "</div></details>")
    out.append("</div>")
    out += ['<div class="card"><h3>周回数</h3>',
            bars(sorted(Counter(f"{t['rounds']} 周" for t in by_date).items(), key=lambda kv: int(kv[0].split()[0])),
                 head="周", unit="件"),
            "</div></section>"]
    return "\n".join(out)


def chevron(d: str) -> str:
    """ページ送りの矢印。d は SVG の線の形"""
    return (f'<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{d}"/></svg>')


FIND_HTML = ('<label class="find"><svg class="lens" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>'
             '<input type="search" id="find" placeholder="トピック・用語・人・媒体" aria-label="サイドバーを検索" autocomplete="off" '
             'enterkeyhint="search" spellcheck="false">'
             f'<button type="button" class="clear" aria-label="検索語を消す">{chevron("M7 7l10 10M17 7L7 17")}</button></label>')


# 0件のとき。無かったことと打った語をはっきり出し、次の一手（語を消す）を添える。どこを探したかも書く
# （NN/g 2014「Clearly explain that there are no matching results」・ビービット 2007「次にどういうアクションを取ればよいか」）
FIND_NONE = ('<div class="find-none" hidden><p>「<b class="nq"></b>」に当てはまるトピックはない</p>'
             '<p class="where">題名・疑問・読み・用語・人・媒体から探した</p><button type="button">検索語を消す</button></div>')


def pager_html(kind: str) -> str:
    """一覧のページ送り。PC は一覧の底に横並び（‹ 2 / 4 ›）、スマホは開いた一覧の右の細い帯に、
    × の下へ縦に並べる（2026-10-22 かしぇ）。番号は押すと打ち込める。中身はスクリプトが入れる"""
    prev, nxt = ("M15 6l-6 6 6 6", "M9 6l6 6-6 6") if kind == "pc" else ("M6 15l6-6 6 6", "M6 9l6 6 6-6")
    sep = '<span class="t">/ <span class="pg-t">1</span></span>' if kind == "pc" else '<span class="rule"></span><span class="t pg-t">1</span>'
    return (f'<nav class="pager {kind}" aria-label="サイドバーのページ"><button type="button" data-step="-1" aria-label="前のページ">{chevron(prev)}</button>'
            '<input class="pg-n" type="text" inputmode="numeric" aria-label="ページ番号" value="1" autocomplete="off">'
            f'{sep}<button type="button" data-step="1" aria-label="次のページ">{chevron(nxt)}</button></nav>')


def install_html() -> str:
    """アプリとして入れる帯と、入れ方の手順の小窓。どちらもスクリプトが窓口で開いたときだけ出す（hidden で書いておく）。
    手順はブラウザごとに書き、スクリプトが見ている端末の組だけを残す。Chrome と Edge の項目の名前は版で変わるので、名前は書きすぎない"""
    steps = {
        "ios": "<ol class=\"how\"><li>Safari の共有ボタン（四角から上向きの矢印）を押します</li><li>「ホーム画面に追加」を選び、「追加」を押します</li></ol>",
        "android": "<ol class=\"how\"><li>Chrome の右上のメニュー（︙）を押します</li><li>「アプリをインストール」か「ホーム画面に追加」を選びます</li></ol>",
        "chromium": ("<ol class=\"how\"><li>アドレスバーの右端にあるインストールのアイコンを押すか、ブラウザのメニューからアプリのインストールの項目を選びます</li>"
                     "<li>見当たらない場合は、30秒ほどこの画面を操作してから、もう一度右上の入れるボタンを押します</li></ol>"),
        "safari": "<ol class=\"how\"><li>メニューバーの「ファイル」を開きます</li><li>「Dock に追加」を選びます</li></ol>",
        "firefox": "<p>Firefox はアプリとしての追加に対応していません。Chrome か Edge でこの画面を開くと入れられます。</p>",
    }
    plats = "".join(f'<div data-plat="{k}">{v}</div>' for k, v in steps.items())
    return (f'<section class="inst-bar" id="inst-bar" aria-labelledby="inst-h" hidden><span class="ic">{INSTALL_ICON}</span>'
            '<div class="tx"><h2 id="inst-h">アプリとして入れる</h2><p>アイコンから、ブラウザを開かずに起動できます</p></div>'
            f'<button class="btn pri go" type="button">入れる</button><button class="x" type="button" aria-label="この案内を閉じる">{CLOSE_ICON}</button></section>'
            '<dialog class="dlg" id="inst-dlg" aria-labelledby="inst-dh"><div class="in"><h2 id="inst-dh">アプリとして入れる</h2>'
            '<p class="lead">入れると、ホーム画面やタスクバーのアイコンから、この調査記録をすぐに開けます。合言葉の入力は要りません。</p>'
            f'{plats}<div class="acts"><button class="btn" type="button" data-close>閉じる</button></div>'
            f'<button class="x" type="button" aria-label="閉じる" data-close>{CLOSE_ICON}</button></div></dialog>')


def feedback_html(form: dict) -> str:
    """感想・要望を送る小窓。フォームの送り先へ別のタブで直接送る（このページの CSP の form-action で、送り先をそのフォームだけに絞る）。
    送るものを小窓の中に書いておく。調査の題や中身、ページの URL は送らない"""
    kinds = "".join(f'<label><input type="radio" name="{form["kind"]}" value="{k}" required><span>{k}</span></label>' for k in FEEDBACK_KINDS)
    rating = ("<fieldset><legend>評価<small>任意・5 が最高</small></legend><div class=\"chips\">"
              + "".join(f'<label><input type="radio" name="{form["rating"]}" value="{n}"><span>{n}</span></label>' for n in range(1, 6))
              + "</div></fieldset>") if "rating" in form else ""
    version = imozuru_version()
    hidden = (f'<input type="hidden" name="{form["version"]}" value="{esc(version)}">' if "version" in form else "") + \
             (f'<input type="hidden" name="{form["env"]}" value="" data-env>' if "env" in form else "")
    return ('<dialog class="dlg" id="fb-dlg" aria-labelledby="fb-h"><div class="in"><h2 id="fb-h">感想・要望を送る</h2>'
            '<p class="lead">imozuru の作者に届きます。不具合の報告、ほしい機能、使ってみた感想をお寄せください。</p>'
            f'<form method="post" action="{esc(form["action"])}" target="_blank" rel="noopener noreferrer">'
            f'<fieldset><legend>種類</legend><div class="chips">{kinds}</div></fieldset>{rating}'
            '<label class="lbl" for="fb-body">内容</label><textarea id="fb-body" name="' + form["body"] + '" required maxlength="4000"></textarea>'
            f'{hidden}<p class="what">送るのは、ここに書いた内容と、imozuru のバージョン（{esc(version)}）・ブラウザの種類だけです。調査の題や中身は送りません。'
            '送ると、Google フォームの受付画面が別のタブで開きます。</p>'
            '<div class="acts"><button class="btn" type="button" data-close>取消</button><button class="btn pri" type="submit">送る</button></div></form>'
            '<div class="done" role="status"><p>受付の画面を別のタブで開きました。そこに「回答を記録しました」と出ていれば届いています。ありがとうございます。</p>'
            '<div class="acts"><button class="btn pri" type="button" data-close>閉じる</button></div></div>'
            f'<button class="x" type="button" aria-label="閉じる" data-close>{CLOSE_ICON}</button></div></dialog>')


def render(topics: list[dict], root: Path, served: bool = False) -> str:
    """served は窓口（--serve）から返すとき。アプリとして入れる指定（manifest）を付ける。ファイルに書き出すページは入れられないので付けない"""
    form = feedback_form()
    try:
        logo = (LOGO_LIGHT if LOGO_LIGHT.is_file() else LOGO).read_text(encoding="utf-8")
        logo = logo.replace("<svg ", '<svg role="img" aria-label="imozuru" ', 1)
    except OSError:
        logo = '<span class="ttl">imozuru</span>'  # 公開版の外で動かしたときなど、ロゴが無ければ文字で出す
    # 検索の索引は項目ごとの属性に持たせる。data-s は題名の側（問い・slug・日付・理由・媒体のホスト）、
    # data-w は map.md の用語・人・媒体の箇条（当たったときに項目の下へ何で当たったかを出す）。map.md の文は他人が書いたものなので必ず esc を通す
    items = "".join(
        f'<li data-s="{esc(" ".join([t["slug"], title_of(t), t["question"], t["date"], t["reason_class"], *sorted(set(t["hosts"]))]))}" '
        f'data-w="{esc(json.dumps(t.get("words", []), ensure_ascii=False))}" data-r="{esc(t.get("reading", ""))}">'
        f'<a class="{reason_cls(t)}" href="#t-{esc(t["slug"])}"><span class="q">{esc(title_of(t))}</span>'
        f'<span class="m">{esc(t["date"] or "日付なし")}<span class="chip {reason_cls(t)}">'
        f'{esc(t["reason_class"])}</span></span></a></li>' for t in topics)
    # 選んでいる調査を一覧で示す。開いている札（スクリプトが動くときは印 .on、動かないときは :target）を :has() で一覧へ伝える
    current = "".join(f'body:not(.js) .layout:has(#t-{t["slug"]}:target) aside a[href="#t-{t["slug"]}"],'
                      f'body.js .layout:has(#t-{t["slug"]}.on) aside a[data-href="#t-{t["slug"]}"]'
                      "{background:color-mix(in oklch,var(--glass) 9%,transparent)}" for t in topics if SLUG.fullmatch(t["slug"]))
    body = [f'<header><button class="menu" type="button" aria-controls="side" aria-expanded="false" aria-label="サイドバー"><span></span></button>'
            f'{pager_html("sp")}</header>',
            # 右上のボタンの列。入れるボタンはスクリプトが窓口で開いたときだけ出す。送るボタンは送り先のフォームがあるときだけ置く
            '<div class="tools">'
            f'<button class="tbtn inst" id="inst" type="button" hidden aria-haspopup="dialog" aria-label="アプリとして入れる" data-tip="アプリとして入れる">{INSTALL_ICON}</button>'
            + (f'<button class="tbtn fb" id="fb" type="button" aria-haspopup="dialog" aria-label="感想・要望を送る" data-tip="感想・要望を送る">{FEEDBACK_ICON}</button>' if form else "")
            + f'<a class="tbtn help" href="#guide" aria-label="ヘルプ" data-tip="ヘルプ">{HELP_ICON}</a></div>',
            # 文書を本体の枠に開いているときだけ出す戻るボタン。行き先（その文書の調査の札）はスクリプトが入れる
            # （2026-10-22 かしぇ「戻るHUDは要るね　そのレポートの所属する項目に戻りたい時が絶対ある」）
            f'<a class="imz-hud dochud" href="#" aria-label="このトピックの記録へ戻る">{HUD_ICON}</a>',
            f'<button class="imz-hud docprint" type="button" aria-label="この文書を PDF で保存（印刷）">{PRINT_ICON}</button>', PTR_ICON,
            '<div class="layout">',
            # ロゴの帯と一覧は .side-in で包む。スマホで開閉するとき、中身を1つの塊として奥へ下げ・手前へ出す
            f'<div class="side" id="side"><div class="side-in"><div class="brand"><a class="home-link" href="#" aria-label="ホームへ">{logo}</a>{FIND_HTML}</div>'
            f'<aside><ol>{items}</ol>{FIND_NONE}<p class="sr" id="find-n" aria-live="polite"></p></aside></div>'
            f'{pager_html("pc")}<button class="grip" type="button" aria-label="サイドバーを開く・閉じる（ドラッグでも動く）"></button></div>',
            '<button class="shade" type="button" aria-label="サイドバーを閉じる" tabindex="-1"></button><div class="frame" aria-hidden="true"></div>',
            '<main><div class="view">', home_html(topics), *[topic_html(t) for t in topics],
            f'<section class="topic guide" id="guide">{guide_html(topics)}</section>',
            '<section class="docview" id="docview" aria-label="文書"><iframe title="文書"></iframe>'
            # 文書の待ちと失敗の札。文と押せるものはスクリプトが入れ替える
            '<div class="docwait" id="docwait" hidden><div class="in" role="status"><p class="nm"></p><h2></h2><p class="lead"></p>'
            '<span class="bar" aria-hidden="true"></span><div class="acts" hidden><button class="btn pri" type="button"></button></div></div></div></section>',
            "</div></main></div>", install_html(), feedback_html(form) if form else ""]
    # スクリプトは中身のハッシュで許可する。'unsafe-inline' にすると、調査の記録から紛れ込んだ文字列も動きうる
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(js.encode()).digest()).decode() + "'" for js in (SIDE_JS, FEATURE_JS))
    # フォームの送り先は感想のフォームだけに絞る（form-action は default-src を引き継がないので、書かないと全部の宛先へ送れる）。
    # アプリとして入れる指定と、文書が開けなかったときに窓口へ様子を問い合わせる fetch と、サーバーに届かないときの
    # 代わりの画面を出す service worker は、窓口のときだけ許す
    csp = (f"default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src data:; "
           f"frame-src 'self' file:; script-src {hashes}; form-action {'https://docs.google.com' if form else chr(39) + 'none' + chr(39)}"
           + ("; manifest-src 'self'; connect-src 'self'; worker-src 'self'" if served else ""))
    # ホーム画面のアイコン。画面の高さの数え方を変える apple-mobile-web-app-* の指定とは別物で、見た目の大きさには触れない
    # （apple-mobile-web-app-capable などを足したら、ホーム画面から開いたとき下に帯が出た・2026-10-22）
    icon_link = '<link rel="apple-touch-icon" href="apple-touch-icon.png">' if ICON.is_file() else ""
    # アプリの指定は合言葉を持つ相手にだけ返すので、cookie を付けて取りに行かせる（use-credentials）
    if served:
        icon_link += '<link rel="manifest" href="manifest.webmanifest" crossorigin="use-credentials">'
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>imozuru 調査記録</title>{skin.HEAD_META}{icon_link}
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;500&family=Noto+Serif+JP:wght@400;600&family={THEME["font"]}&display=swap">
<style>{CSS}{hud_css("dark")}:root{{--bar:{THEME["bar"]};--src:{THEME["src"]};--r1:{THEME["r1"]};--r2:{THEME["r2"]};--r3:{THEME["r3"]};--r4:{THEME["r4"]};--p-r1:{THEME["p-r1"]};--p-r2:{THEME["p-r2"]};--p-r3:{THEME["p-r3"]};--p-r4:{THEME["p-r4"]};--p-bar:{THEME["p-bar"]};--p-src:{THEME["p-src"]};--head:{THEME["head"]},"Hiragino Mincho ProN","Yu Mincho",serif}}{current}</style></head>
<body>
{chr(10).join(body)}
<script>{SIDE_JS}</script>
<script>{FEATURE_JS}</script>
</body></html>
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
