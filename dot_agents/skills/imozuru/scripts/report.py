#!/usr/bin/env python3
"""抜き書き（extracts.json）を、原文どおりか確かめてから読むためのページ（report.html）にする。

原文を40本落としても、英語の PDF や1時間の字幕のままでは読まれずに終わる。
かといってエージェントが要約すると「早すぎる閉じ」に戻る。間を取るのが Ellis の
extracting＝抜き書き。論点ごとに原文をそのまま切り出して並べ、エージェントが書くのは
見出し・「見つからなかった」・英語の訳だけにする。

言い換えが紛れ込まないよう、抜き書きの文が原文の指定の行にそのまま在るかを機械で確かめる。
1つでも見つからなければ HTML は作らず、どれが合わないかを出して止まる。

使い方:
    report.py <topic_dir>         … <topic_dir>/extracts.json → <topic_dir>/report.html
    report.py <topic_dir> --check … 照合だけして HTML は作らない

extracts.json の形（例はリポジトリの examples/demo/extracts.json）:
    {"title", "question", "stopped",
     "claims": [{"claim", "status": "根拠あり|一部のみ|根拠なし", "note"?,
                 "quotes": [{"file", "line", "end"?, "text", "ja"?, "mark"?, "context_note"?, "url"?}]}],
     "disagreements"?: [{"topic", "quotes": [{..., "who"}]}],
     "unreached"?: ["..."]}
引用の元のページへのリンクは "url" か、無ければ map.md の「原文（sources/）」の表の「元の URL」か取得の記録（fetch-log.jsonl）から付ける。
"""

import fnmatch
import html
import json
import os
import re
import sys
import tempfile
from functools import lru_cache
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skin  # noqa: E402  見た目（コルク板と象牙の紙）と色は skin.py・palette.py の1か所に置く

# 2026-10-21 まで使っていた状態の言葉。前に書いた extracts.json も読めるよう、新しい言葉に読み替える
OLD_STATUS = {"付いた": "根拠あり", "一部だけ": "一部のみ", "付かなかった": "根拠なし"}

# 前後に見せる行数。抜き書きがどんな流れの中にあったかを、ページの中で開いて確かめられるように。
CONTEXT_LINES = 6

# 負号として扱う字。PDF は U+2212 を、和文は全角の U+FF0D を、組版された英文は en dash（U+2013）を使うことがある
MINUS = ("-", "\u2212", "\uff0d", "\u2013")
# 符号つきの数の始まり。「.」だけでは数にしない（「- .NET 8」の「.NET」を負号の後ろと見なさない）
SIGNED_NUMBER = re.compile(r"[.．]?\d")
# 負号の直前にこの字があれば、語の中のハイフンか範囲（COVID-19・18-65・50%–60%・行末で切った「period-」）として扱う。
# 和文の「気温は－5度」を通さないよう、仮名や漢字は含めない
WORD_CHAR = re.compile(r"[A-Za-z0-9０-９Ａ-Ｚａ-ｚ%％°]")
# 照合に落ちたときの案内。行番号のずれと思って行を直しても通らないので、負号の決まりをここで知らせる
MINUS_HINT = ("数で始まる抜き書きは、原文でその直前に負号やダッシュ（-・−・－・–）があれば、その記号ごと写す。"
              "数で始まる箇条書きの項目も「- 」ごと写す（負号と見分けられないため）")


def norm(s: str) -> str:
    """照合用に空白・改行・箇条書きの印をそろえる。文字そのものは変えない。
    数が続く行頭の「- 」は負号かもしれないので残す（#19）"""
    s = re.sub(r"(?m)^\s*(?:\*|-(?!\s*[.．]?\d))\s+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def verify(src_dir: Path, q: dict) -> tuple[bool, list[str], int, int]:
    """抜き書きが原文の指定の行（前後2行の余裕つき）にそのまま在るか。前後の文脈も返す。"""
    relative = Path(q["file"])
    if relative.is_absolute() or PureWindowsPath(q["file"]).is_absolute() or ".." in relative.parts:
        return False, [], 0, 0
    try:
        root = src_dir.resolve()
        topic = src_dir.parent.resolve()
        path = (src_dir / relative).resolve()
    except (OSError, RuntimeError, ValueError):
        return False, [], 0, 0
    if root == topic or not root.is_relative_to(topic):
        return False, [], 0, 0
    if not path.is_relative_to(root) or not path.is_file():
        return False, [], 0, 0
    # splitlines() はページ区切り（\f）も改行に数え、grep・sed と行番号がずれる。改行だけで数える
    lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
    # 0 や負の行・end が line より前の指定は、前後2行の余裕で原文の頭に寄せると通ってしまい、
    # 指していない行を「照合済み」と見せる（2026-10-20 のレビュー）。原文の中の行だけを受け付ける
    # end が無いか null なら1行だけ（null は前から通っていたので受け付け続ける）
    first = q["line"]
    last = first if q.get("end") is None else q["end"]
    if not all(type(n) is int for n in (first, last)) or not 1 <= first <= last <= len(lines):
        return False, [], 0, 0
    start = max(1, first - 2)
    end = min(len(lines), last + 2)
    # ここから先は、検査を通った first・last だけを使う
    # スペースでつないでから整えると、行頭の印は1行目のものしか消えない。2行目より後の「- 」が残り、
    # 箇条書きにまたがる抜き書きが落ちた（penpenguin の記事・2026-10-17）。
    # Markdown の原文に限り、行ごとに印を消した形でも照らす。Markdown の行頭の「- 」はリストの印で、
    # HTML から起こした .md は段落が1行にまとまる。従来の形を残すのは、印ごと写した前からの抜き書きを落とさないため。
    # 行頭の「- 」は負号のことがあり、消すと「- 5 mg」を「5 mg」と写した抜き書きまで通る（2026-10-26 のレビュー）。
    # 拡張子では見分けられない。fetch.py は text/plain も .md で保存し、「- 5 mg」は Markdown としても
    # 負号か印か決まらない（#19）。そこで norm() は数字の前の「- 」を消さず、_in_order() は負号の直後から
    # 始まる抜き書きを通さない。数字で始まる項目は「- 」ごと写さないと照合できないが、符号を落とすよりよい
    window = lines[start - 1:end]
    regions = [norm(" ".join(window))]
    if path.suffix.lower() == ".md":
        regions.append(norm("\n".join(window)))
    # 2段組の PDF は左右の段が1行に混ざり、何行かにまたがる文はそのままでは照合できない
    # （Yoshida 2008 で起きた）。抜き書きを「…」で区切れば、区切りごとに順に照らす。
    # 区切りはページにも「…」として残るので、省いたことが読む人に見える。
    pieces = [norm(p) for p in q["text"].split("…") if norm(p)]
    ok = bool(pieces) and any(_in_order(pieces, region) for region in regions)
    c0 = max(1, q["line"] - CONTEXT_LINES)
    c1 = min(len(lines), last + CONTEXT_LINES)
    return ok, lines[c0 - 1:c1], c0, c1


def _in_order(pieces: list[str], region: str) -> bool:
    """区切りがどれも、前の区切りより後ろに region の中で現れるか。
    数で始まる区切りは、負号の直後の位置では数えない（「- 5 mg」の中の「5 mg」を通さない・#19）"""
    signed = [bool(SIGNED_NUMBER.match(p)) for p in pieces]
    pos = 0
    for piece, number in zip(pieces, signed):
        at = region.find(piece, pos)
        while at >= 0 and number and _after_minus(region, at):
            at = region.find(piece, at + 1)
        if at < 0:
            return False
        pos = at + len(piece)
    return True


def _after_minus(region: str, at: int) -> bool:
    """region の at の直前（空白を除く）が負号か。英数字の直後のハイフンは語の一部なので負号にしない"""
    head = region[:at].rstrip()
    if not head.endswith(MINUS):
        return False
    # 空白をはさむ en dash は範囲（2019 – 2020）か挿入のダッシュ。負号の en dash は数に接する（–0.5）。
    # ハイフンは空白があっても負号とする（Markdown の「- 5 mg」・#19）
    if head.endswith("\u2013") and len(head) != at:
        return False
    return not WORD_CHAR.fullmatch(head[-2:-1] or " ")


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# 引用に、元のページへのリンクを付ける（#16・2026-10-25）。元の URL は map.md の「原文（sources/）」の表の「元の URL」の列にある。
# 「ファイル」の列は1つの名前とは限らない。手元の 46 件の調査の map.md には、読点・カンマ・中黒・全角の「／」で並べた行、
# PDF とその文字起こしを a.pdf/.txt や a.pdf / .txt（a.pdf と a.txt の2本）と1つの表記で書いた行、（未読）のような注記、
# sources/ 付き、ワイルドカード（ms-learn-*.md）、ファイル名そのものに入った半角の丸括弧（-r）があった
SOURCE_URL = re.compile(r"https?://[^\s\"'<>|`（）「」、。]+")
NAME_SEP = re.compile(r"[、,，・／]+|\s+")
EXT_ALT = re.compile(r"^(.+?)\.(\w+)((?:/\.\w+)+)$")


def link_url(url) -> str:
    """リンクにしてよい URL だけを返す。http(s) で、ホストがあり、空白・引用符・<> を含まないもの。javascript: などは捨てる"""
    if not isinstance(url, str) or not re.fullmatch(r"https?://[^\s\"'<>]+", url):
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    return url if parts.scheme in ("http", "https") and parts.netloc else ""


def file_groups(cell: str) -> list[list[str]]:
    """「ファイル」の列の1行を、元の URL と組にする単位（並べた1つ1つ）ごとのファイル名の並びにする。
    a.pdf/.txt は1つの単位で a.pdf と a.txt の2本。/ を含む名前は、下のフォルダの名前かもしれないので全体も残す"""
    s = cell.replace("`", "")
    # 全角の括弧は注記（未読 など）。半角の丸括弧はファイル名に入ることがあるので外さない
    s = re.sub(r"（[^）]*）", " ", s)
    s = re.sub(r"(?<![\w.-])sources/", "", s)
    # 拡張子だけが続く書き方（a.pdf/.txt・a.pdf / .txt・a.pdf・.txt）は、どれも同じ名前の別の拡張子
    s = re.sub(r"\s*[/・、,，]\s*(?=\.\w+(?![\w.]))", "/", s)
    groups = []
    for token in NAME_SEP.split(s):
        m = EXT_ALT.match(token)
        if m:
            names = [f"{m.group(1)}.{m.group(2)}"] + [m.group(1) + e for e in re.findall(r"/(\.\w+)", m.group(3))]
        else:
            names = [token] + (token.split("/") if "/" in token else [])
        names = [n for n in names if re.search(r"\.\w+$", n)]
        if names:
            groups.append(names)
    return groups


def cell_urls(cell: str) -> list[str]:
    urls = []
    for u in SOURCE_URL.findall(cell):
        u = u.rstrip(".,;:")
        while u.endswith(")") and u.count(")") > u.count("("):
            u = u[:-1]
        if link_url(u):
            urls.append(u)
    return urls


@lru_cache(maxsize=64)
def _source_rows(map_path: str, _mtime: int) -> tuple:
    try:
        text = Path(map_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    rows = []
    for head in re.finditer(r"^\|[^\n]*\|[ \t]*$", text, re.M):
        cols = [c.strip() for c in head.group(0).strip().strip("|").split("|")]
        if "ファイル" not in cols or "元の URL" not in cols:
            continue
        fi, ui = cols.index("ファイル"), cols.index("元の URL")
        # 見出しの次の行は区切り（|---|）。表が終わる（| で始まらない行）まで読む。
        # 区切りの行と最初の行のあいだに空行を挟んだ map.md があったので、空行は飛ばす
        for line in text[head.end():].lstrip("\n").split("\n")[1:]:
            if not line.strip():
                continue
            if not line.startswith("|"):
                break
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) <= max(fi, ui):
                continue
            groups = file_groups(cells[fi])
            # 「同上」は前の行の URL を引き継がない。手元では、別々の論文が並ぶ行で「URL は log 参照」の注記を繰り返す意味だった
            urls = cell_urls(cells[ui])
            # URL が1つなら、その行のファイル全部の元。ファイルの単位と同じ数なら順に組にする。
            # 数が合わないときは付けない（違うページへのリンクは、リンクが無いより悪い）
            if len(urls) == 1:
                rows += [(tuple(g), urls[0]) for g in groups]
            elif urls and len(urls) == len(groups):
                rows += [(tuple(g), u) for g, u in zip(groups, urls)]
    return tuple(rows)


@lru_cache(maxsize=64)
def _fetched(log_path: str, _mtime: int) -> tuple[dict, dict]:
    """取得の記録（fetch-log.jsonl）から、取得に成功した原文の URL を引く表を作る。（ファイル名→URL, 保存名→URL）。
    fetch.py は status と sources/ の中の名前を、ほかの取得の道具は result と sources/ 付きの名前を書いていた。
    同じ原文を取り直した行は、あとの行（いちばん新しい取得）を使う"""
    by_file, by_stem = {}, {}
    try:
        lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return by_file, by_stem
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or "OK" not in (r.get("status"), r.get("result")):
            continue
        url = link_url(r.get("url"))
        if not url:
            continue
        file = r.get("file")
        if isinstance(file, str) and file:
            file = re.sub(r"^sources/", "", file)
            by_file[file] = by_file[Path(file).name] = url
            by_stem[Path(file).stem] = url
        if isinstance(r.get("name"), str) and r["name"]:
            by_stem[r["name"]] = url
    return by_file, by_stem


def source_url(src_dir: Path, file: str) -> str:
    """引用の原文（sources/ からの相対）の元の URL を引く。見つからなければ空。
    map.md の「原文（sources/）」の表を先に見て、無ければ取得の記録（fetch-log.jsonl）を見る。
    手元では、引用された原文 765 本のうち表から引けるのは 418 本で、取得の記録も見ると 509 本になった。
    表は書き手が整えたものなので、名前がそのまま合う行を表・記録の順に探し、拡張子だけが違う行は最後に表・記録の順に探す"""
    topic = Path(src_dir).parent
    rows, (log_file, log_stem) = (), ({}, {})
    try:
        rows = _source_rows(str(topic / "map.md"), (topic / "map.md").stat().st_mtime_ns)
    except OSError:
        pass
    try:
        log_file, log_stem = _fetched(str(topic / "fetch-log.jsonl"), (topic / "fetch-log.jsonl").stat().st_mtime_ns)
    except OSError:
        pass
    wanted = {file, Path(file).name}
    for names, url in rows:
        if any(n in wanted or ("*" in n and fnmatch.fnmatchcase(Path(file).name, n)) for n in names):
            return url
    for n in (file, Path(file).name):
        if n in log_file:
            return log_file[n]
    # 名前が合う行が無いときだけ、拡張子を除いた名前で照合する。表に a.md と書いて実物は文字起こしの a.txt という行や、
    # 記録には取った a.pdf だけがあって引用は文字起こしの a.txt という行があった
    stem = Path(file).stem
    for names, url in rows:
        if any("*" not in n and Path(n).stem == stem for n in names):
            return url
    return log_stem.get(stem, "")


# 外へ出るリンクの印。ほかの印と同じく文字ではなく線の絵にする
OUT_ICON = ('<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>')


def quote_html(src_dir: Path, q: dict, ctx: list[str], c0: int) -> str:
    loc = f"{q['file']}:{q['line']}" + (f"-{q['end']}" if q.get("end") else "")
    hit = range(q["line"], (q.get("end") or q["line"]) + 1)
    # markdown の空行で間延びするので、空の行は飛ばす（行番号はそのまま残るので位置は追える）
    # span は display:block なので区切りの改行は入れない（入れると行間が二重になった）
    ctx_html = "".join(
        f'<span class="{"hit" if c0 + i in hit else ""}"><b>{c0 + i}</b> {esc(t)}</span>'
        for i, t in enumerate(ctx) if t.strip())
    parts = ['<figure class="quote">']
    if q.get("who"):
        parts.append(f'<div class="who">{esc(q["who"])}</div>')
    parts.append(f'<blockquote{skin.lang_attr(q["text"])}>{esc(q["text"])}</blockquote>')
    if q.get("ja"):
        parts.append(f'<p class="ja"><span class="tag">訳</span>{esc(q["ja"])}</p>')
    meta = [f'<code>{esc(loc)}</code>']
    url = link_url(q.get("url")) or source_url(src_dir, q["file"])
    if url:
        meta.append(f'<a class="src" href="{esc(url)}" target="_blank" rel="noopener noreferrer">元のページを開く{OUT_ICON}</a>')
    if q.get("mark"):
        meta.append(f'<span class="mark">{esc(q["mark"])}</span>')
    if q.get("context_note"):
        meta.append(f'<span class="cn">{esc(q["context_note"])}</span>')
    parts.append(f'<figcaption>{" ".join(meta)}</figcaption>')
    parts.append(f'<details><summary>前後を読む（{c0}〜{c0 + len(ctx) - 1}行）</summary><pre{skin.lang_attr(" ".join(ctx))}>{ctx_html}</pre></details>')
    parts.append("</figure>")
    return "\n".join(parts)


# 地と紙と書体は skin.CSS。ここは抜き書きに固有の部品だけ。論点ごとに1枚の紙（.sheet）に載せる
CSS = skin.CSS + """
h1{font-size:1.6rem;margin:0 0 .5rem}
h2{font-size:1.2rem;margin:0 0 .4rem}
.lead{color:var(--sub);margin:.2rem 0}
.status{display:inline-block;font-size:.8rem;padding:.05rem .55rem;border-radius:99px;border:1px solid var(--accent);color:var(--accent);margin-left:.5rem;vertical-align:middle}
.status.none{border-style:dashed;color:var(--sub);border-color:var(--sub)}
.note{color:var(--sub);font-size:.95rem}
.quote{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1rem 1.1rem;margin:1rem 0}
blockquote{margin:0;padding-left:.9rem;border-left:3px solid var(--accent);white-space:pre-wrap}
.who{font-weight:600;margin-bottom:.4rem}
.ja{margin:.6rem 0 0;color:var(--sub)}
.tag{font-size:.75rem;border:1px solid var(--sub);border-radius:4px;padding:0 .3rem;margin-right:.4rem}
figcaption{margin-top:.6rem;font-size:.8rem;color:var(--sub);display:flex;flex-wrap:wrap;gap:.5rem}
figcaption a.src{display:inline-flex;align-items:center;gap:.25rem;color:inherit;white-space:nowrap}
figcaption a.src svg{flex:none}
code{font-family:ui-monospace,"Cascadia Code",monospace;font-size:.78rem}
.mark{color:var(--accent)}
details{margin-top:.5rem;font-size:.8rem}
summary{cursor:pointer;color:var(--sub)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.78rem;line-height:1.6;max-height:22rem;overflow:auto;margin:.4rem 0 0}
pre span{display:block}
pre span.hit{background:var(--hit)}
pre b{display:inline-block;min-width:3em;color:var(--sub);font-weight:400}
ul.unreached li{margin:.2rem 0}
footer{margin-top:2rem;font-size:.8rem}
"""


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    topic = Path(sys.argv[1]).expanduser()
    check_only = "--check" in sys.argv
    data = json.loads((topic / "extracts.json").read_text(encoding="utf-8"))
    src = topic / "sources"

    bad, rendered, signed_bad = [], {}, False
    groups = [("claims", c) for c in data["claims"]] + [("dis", d) for d in data.get("disagreements", [])]
    for _, g in groups:
        for q in g.get("quotes", []):
            ok, ctx, c0, _ = verify(src, q)
            if not ok:
                bad.append(f"{q['file']}:{q['line']}  「{q['text'][:40]}…」")
                signed_bad = signed_bad or any(SIGNED_NUMBER.match(norm(p)) for p in q["text"].split("…"))
            rendered[id(q)] = (ctx, c0)
    if bad:
        print("原文に見つからない抜き書きがある（言い換えか、行番号のずれ）:")
        print("\n".join("  " + b for b in bad))
        if signed_bad:  # 行番号のずれや言い換えで落ちたときにまで出すと、原因を取り違える
            print(MINUS_HINT)
        return 1
    total = sum(len(g.get("quotes", [])) for _, g in groups)
    print(f"照合 OK: 抜き書き {total} 件がすべて原文のとおり")
    if check_only:
        return 0

    # 冒頭と、論点ごとに1枚ずつの紙にする
    body = ['<section class="sheet">', f"<h1>{esc(data['title'])}</h1>",
            f'<p class="lead">調べたこと: {esc(data["question"])}</p>',
            f'<p class="lead">調査を区切った理由: {esc(data["stopped"])}</p>',
            "</section>"]
    for c in data["claims"]:
        status = OLD_STATUS.get(c["status"], c["status"])
        cls = "status none" if status == "根拠なし" else "status"
        body.append(f'<section class="sheet"><h2>{esc(c["claim"])}<span class="{cls}">{esc(status)}</span></h2>')
        if c.get("note"):
            body.append(f'<p class="note">{esc(c["note"])}</p>')
        for q in c.get("quotes", []):
            ctx, c0 = rendered[id(q)]
            body.append(quote_html(src, q, ctx, c0))
        body.append("</section>")
    for d in data.get("disagreements", []):
        body.append(f'<section class="sheet"><h2>食い違い: {esc(d["topic"])}</h2>')
        for q in d.get("quotes", []):
            ctx, c0 = rendered[id(q)]
            body.append(quote_html(src, q, ctx, c0))
        body.append("</section>")
    if data.get("unreached"):
        body.append('<section class="sheet"><h2>届かなかったもの</h2><ul class="unreached">'
                    + "".join(f"<li>{esc(u)}</li>" for u in data["unreached"]) + "</ul></section>")
    # 絶対パスはページを人に渡すと手元のユーザー名を漏らすので、ページからの相対で書く
    body.append(f'<footer>imozuru の抜き書き・原文はこのページと同じ場所の {esc(src.name)}/</footer>')

    page = skin.page(f"{data['title']} 抜き書き", "\n".join(body), extra_head=f"<style>{CSS}</style>")
    out = topic / "report.html"
    # 同じ場所に排他的に作り、仕込まれたリンクを踏まず、途中で止まっても前のページを残す
    fd, tmp = tempfile.mkstemp(prefix=".report.html.", suffix=".tmp", dir=out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(page)
        os.replace(tmp, out)
    finally:
        Path(tmp).unlink(missing_ok=True)
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    # 抜き書きの頭を出すので、端末の文字コードに無い字（cp932 の à など）で落ちないようにする
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
