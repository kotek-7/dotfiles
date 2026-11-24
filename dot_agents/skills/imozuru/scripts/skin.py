"""imozuru が書き出す文書（抜き書き・詳細レポート・map.md と log.md の表示）の共通の見た目。

履歴ダッシュボードに合わせて、コルク板の地に象牙の紙をピンで留め、その上に中身を載せる
（2026-10-22 かしぇ「抜き書きと詳細レポートのフォーマットも　ダッシュボード側のデザインに合わせたい」）。
紙は1つの話題ごとに1枚（.sheet）。色は palette.py の値だけを使い、質感は assets/ の PNG を埋め込む。
md の表示（md_html）は、map.md・log.md を文字のまま見せていたのを、見出し・箇条書き・表などに組む
（同日かしぇ「mdはちゃんとプレビューするようにしたい」）。
"""

import base64
import html
import re
from pathlib import Path
from urllib.parse import urlsplit

import palette

ASSETS = Path(__file__).resolve().parent.parent / "assets"
HEAD_FONT = '"Shippori Mincho"'

# Google Fonts を読むので、文書の CSP はこの2つの宛先と、質感の data: 画像を許す
FONT_LINK = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;500'
             '&family=Noto+Serif+JP:wght@400;600&family=Shippori+Mincho:wght@500;700&display=swap">')
CSP_FONTS = "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src data:"


def texture(name: str) -> str:
    """質感の PNG（make_textures.py が作る）を CSS の url() にする。無ければ平らな色のまま（none）"""
    png = ASSETS / f"{name}.png"
    if not png.is_file():
        return "none"
    return 'url("data:image/png;base64,' + base64.b64encode(png.read_bytes()).decode() + '")'


def _head_meta() -> str:
    """どのページの head にも置く指定。ダッシュボードと文書の両方が使う。
    タブの印（favicon.png・make_textures.py が作る）は data: で埋め込む。束を file:// で開いても、
    窓口の合言葉が要るページでも、別のファイルを取りに行かずに出る。
    format-detection は、iPhone の Safari が日付や件数の数字の並びを電話番号のリンクに変えるのを止める"""
    meta = '<meta name="format-detection" content="telephone=no">'
    png = ASSETS / "favicon.png"
    if png.is_file():
        meta += '<link rel="icon" type="image/png" href="data:image/png;base64,' + base64.b64encode(png.read_bytes()).decode() + '">'
    return meta


HEAD_META = _head_meta()


def lang_attr(text: str) -> str:
    """原文の引用に付ける言語の名乗り。ページは lang="ja" なので、名乗らない英文は日本語の書体の選び方と
    日本語の読み上げで扱われる。仮名も漢字も無くラテン文字のある文だけを en と名乗る。原文はほぼ英語か日本語で、
    ほかの言語を見分ける判定は持たない（フランス語の原文も en と名乗る）"""
    if re.search(r"[぀-ヿ㐀-鿿]", text) or not re.search(r"[A-Za-z]", text):
        return ""
    return ' lang="en"'


# 紙の上の役割は文書の明るい組（DOC_LIGHT）。コルクの上に直接置く字（ページの末尾）は on-cork
SKIN_VARS = (palette.css_vars(palette.DOC_LIGHT)
             + palette.css_vars({"cork": "cork", "umbra": "umbra", "glass": "glass", "brass": "brass",
                                 "pin-dark": "walnut-2", "on-cork": "ivory-5"}))

CSS = """
:root{@@VARS@@--head:@@HEAD@@,"Hiragino Mincho ProN","Yu Mincho",serif;--serif:"Noto Serif JP","Hiragino Mincho ProN","Yu Mincho",serif;color-scheme:light}
*{box-sizing:border-box}
html{background:var(--cork)}
body{margin:0;background-color:var(--cork);background-image:@@CORK@@;background-size:240px 240px;color:var(--ink);
font-family:var(--serif);line-height:1.85;font-size:16px}
main{max-width:48rem;margin:0 auto;padding:2.4rem max(14px,env(safe-area-inset-right,0px)) 6rem max(14px,env(safe-area-inset-left,0px))}
h1,h2,h3,h4{font-family:var(--head);font-weight:700;letter-spacing:.03em}
/* 1枚の紙。ダッシュボードの札と同じく、板に貼り付いた紙として縁の細い影だけを落とし、上の真ん中を真鍮のピンで留める。
   下の両角だけ少し反った影を付ける */
.sheet{position:relative;background-color:var(--bg);background-image:@@PAPER@@;color:var(--ink);border-radius:3px;
padding:2.4rem 2rem 1.6rem;margin:0 0 2.2rem;
box-shadow:0 1px 0 color-mix(in oklch,var(--glass) 50%,transparent) inset,0 0 0 1px color-mix(in oklch,var(--umbra) 16%,transparent),0 1px 2px color-mix(in oklch,var(--umbra) 45%,transparent)}
.sheet::before{content:"";position:absolute;top:8px;left:50%;width:16px;height:16px;margin-left:-8px;border-radius:50%;z-index:1;
background:radial-gradient(circle at 35% 30%,color-mix(in oklch,var(--glass) 80%,transparent),var(--brass) 45%,var(--pin-dark) 100%);
box-shadow:1px 2px 2px color-mix(in oklch,var(--umbra) 55%,transparent)}
.sheet::after{content:"";position:absolute;left:3px;right:3px;top:100%;height:9px;pointer-events:none;
background:radial-gradient(farthest-side at 0 0,color-mix(in oklch,var(--umbra) 50%,transparent),transparent) left top/44px 9px no-repeat,
radial-gradient(farthest-side at 100% 0,color-mix(in oklch,var(--umbra) 50%,transparent),transparent) right top/44px 9px no-repeat}
.sheet>:first-child{margin-top:0}
footer{color:var(--on-cork)}
@media (max-width:600px){.sheet{padding:2.1rem 1.1rem 1.2rem}main{padding-top:1.6rem}}
/* 折りたたみの三角は自前で描き、開閉に合わせて回す（ダッシュボードと同じ）。閉じる動きの間（.closing）は閉じた向きへ戻す。
   解説の1文（details.s）は文そのものを押す行なので三角を付けない */
details:not(.s)>summary{list-style:none;cursor:pointer}
details:not(.s)>summary::-webkit-details-marker{display:none}
details:not(.s)>summary::before{content:"";display:inline-block;width:0;height:0;margin-right:.5em;vertical-align:.08em;border-style:solid;
border-width:.32em 0 .32em .5em;border-color:transparent transparent transparent currentColor;transition:transform .25s cubic-bezier(.2,.8,.2,1)}
details[open]:not(.closing)>summary::before{transform:rotate(90deg)}
@media (prefers-reduced-motion:reduce){details>summary::before{transition:none}}
/* md の表示 */
.md h1{font-size:1.45rem;margin:0 0 .6rem}
.md h2{font-size:1.15rem;margin:2rem 0 .4rem;padding-bottom:.25rem;border-bottom:1px solid var(--line)}
.md h3{font-size:1.02rem;margin:1.6rem 0 .3rem}.md h4{font-size:.95rem;margin:1.2rem 0 .2rem}
.md p{margin:.5rem 0}.md ul,.md ol{padding-left:1.3rem;margin:.4rem 0}.md li{margin:.15rem 0;overflow-wrap:anywhere}
.md li.task{list-style:none;margin-left:-1.3rem}
.md .box{display:inline-block;width:1.05em;height:1.05em;margin-right:.45em;vertical-align:-.15em;border:1px solid var(--sub);border-radius:3px;text-align:center;line-height:1;font-size:.85em}
.md .box.on{background:var(--accent);border-color:var(--accent);color:var(--card)}
.md a{color:var(--accent);overflow-wrap:anywhere}
.md code{font-family:ui-monospace,"Cascadia Code",monospace;font-size:.82em;background:color-mix(in oklch,var(--line) 45%,transparent);padding:0 .25em;border-radius:3px}
.md pre{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:.7rem .9rem;overflow:auto;font-size:.8rem;line-height:1.6;max-height:none}
.md pre code{background:none;padding:0}
.md blockquote{margin:.6rem 0;padding-left:.9rem;border-left:3px solid var(--accent);color:var(--sub)}
.md hr{border:0;border-top:1px solid var(--line);margin:1.5rem 0}
.md .tablewrap{overflow-x:auto;margin:.6rem 0}
.md table{border-collapse:collapse;font-size:.85rem;min-width:100%}
.md th,.md td{border-bottom:1px solid var(--line);padding:.3rem .5rem;text-align:left;vertical-align:top;overflow-wrap:anywhere}
.md th{font-weight:600;color:var(--sub);white-space:nowrap}
"""
CSS = (CSS.replace("@@VARS@@", SKIN_VARS).replace("@@HEAD@@", HEAD_FONT)
       .replace("@@CORK@@", texture("cork")).replace("@@PAPER@@", texture("paper")))

# 印刷と PDF の見た目（2026-10-25 かしぇ「pdf出力できるといいかも？」）。コルク板と紙の質感・ピン・影は外して白い紙に刷り、
# 戻るボタンと編の切り替えの札は消す。選んでいる編だけを刷り、その編の名前は読み上げ用の見出しを見せて示す。
# 引用と問いはページの境目で割らない。ダッシュボードは、前に書き出した文書にも同じものを差し込んでから印刷する
PRINT_CSS = """
@media print{
@page{margin:14mm 12mm}
html,body{background:none!important}
main{max-width:none;padding:0}
.sheet{background:none!important;box-shadow:none!important;border-radius:0;padding:0!important;margin:0 0 9mm}
.sheet::before,.sheet::after{display:none!important}
.imz-hud,.tabs,nav,figure.quote>details{display:none!important}
.lv>h2.sr{position:static;width:auto;height:auto;overflow:visible;clip:auto;white-space:normal;font-size:1.1rem;margin:0 0 .4rem}
figure.quote,.quiz,dt,ul.claims li,tr{break-inside:avoid}
/* 引用は枠と左の線と「原文 N」の札を外し、字下げだけで示す（2026-10-25 かしぇが「引用は字下げだけにする」を選んだ）。
   抜き書き・詳細レポートの見た目の指定はこの後ろに来るので、!important で上書きする */
figure.quote{background:none!important;border:0!important;border-radius:0!important;padding:0 0 0 1.6em!important;margin:.3rem 0 .9rem!important}
figure.quote blockquote{border-left:0!important;padding-left:0!important}
figure.quote .tag{border:0!important;padding:0!important}
.mk{display:none!important}
h1,h2,h3,h4,dt{break-after:avoid}
a{color:inherit;text-decoration:none}
.hit,mark{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""
CSS += PRINT_CSS

# 印刷の直前に、選んでいる編の文の根拠（details.s）と問いの答え（details.ans）を開き、刷り終えたら元に戻す。
# 紙では押して開けないので、根拠の引用は文のすぐ下に出しておく。原文の前後や検索の全件は閉じたまま（長すぎる）
PRINT_JS = ("(function(){var opened=[];addEventListener('beforeprint',function(){"
            "document.querySelectorAll('details.s:not([open]),details.ans:not([open])').forEach(function(d){d.open=true;opened.push(d)})});"
            "addEventListener('afterprint',function(){opened.forEach(function(d){d.open=false});opened=[]})})();")


# --- md を HTML に組む -------------------------------------------------------
# 中身は他人が書いた文（調べた先の題名・URL を含む）として扱う。先に全部エスケープしてから印を付け、
# リンクは http(s) だけにする。対応するのは imozuru の map.md・log.md が使う形だけ
# （見出し・段落・箇条書き・番号つき・チェックボックス・表・コードの囲み・引用・区切り線・太字・コード・リンク）

URL_RE = re.compile(r"https?://[^\s<>\"'）」]+")


def _safe_url(u: str) -> str | None:
    try:
        return u if urlsplit(html.unescape(u)).scheme in ("http", "https") else None
    except ValueError:
        return None


def inline(text: str) -> str:
    """1行の中の印。text はまだエスケープしていない文"""
    out, codes = html.escape(text, quote=True), []

    def keep(m):
        codes.append(f"<code>{m.group(1)}</code>")
        return f"\x00{len(codes) - 1}\x00"
    out = re.sub(r"`([^`]+)`", keep, out)

    def mdlink(m):
        url = _safe_url(m.group(2))
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>' if url else m.group(0)
    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", mdlink, out)
    # 囲みの無い URL もリンクにする。すでに <a> の中にあるものは触らない
    parts = re.split(r"(<a [^>]*>.*?</a>)", out)
    out = "".join(p if p.startswith("<a ") else URL_RE.sub(
        lambda m: (f'<a href="{m.group(0)}" target="_blank" rel="noopener noreferrer">{m.group(0)}</a>'
                   if _safe_url(m.group(0)) else m.group(0)), p) for p in parts)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], out)


def _table(rows: list[str]) -> str:
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], [c for c in cells[1:] if not all(set(x) <= set("-: ") for x in c)]
    return ('<div class="tablewrap"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head)
            + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            + "</tbody></table></div>")


def _item(text: str) -> str:
    """箇条書きの1項目。「[x]」「[ ]」「[~]」で始まる項目はチェックの印を付ける"""
    t = re.match(r"\[([ xX~])\]\s*(.*)", text)
    if not t:
        return f"<li>{inline(text)}"
    on = t.group(1) in "xX"
    mark = "✓" if on else ("〜" if t.group(1) == "~" else "")
    return f'<li class="task"><span class="box{" on" if on else ""}">{mark}</span>{inline(t.group(2))}'


def _list(items: list, k: int, base: int) -> tuple[str, int]:
    """items[k] から、字下げが base 以上の項目を1つの箇条書きに組む。より深い項目は直前の項目の中へ入れる"""
    tag, parts = items[k][1], []
    while k < len(items) and items[k][0] >= base:
        li = _item(items[k][2])
        k += 1
        if k < len(items) and items[k][0] > base:
            sub, k = _list(items, k, items[k][0])
            li += sub
        parts.append(li + "</li>")
    return f"<{tag}>" + "".join(parts) + f"</{tag}>", k


def md_html(text: str) -> str:
    text = text.replace("\x00", "")  # コードを戻す内部の目印を、入力から偽装させない
    lines, out, i = text.splitlines(), [], 0
    para: list[str] = []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(inline(p) for p in para) + "</p>")
            para.clear()
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            flush()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
            continue
        if not s:
            flush()
            i += 1
            continue
        m = re.match(r"(#{1,6})\s+(.*)", s)
        if m:
            flush()
            n = min(len(m.group(1)), 4)
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if s.startswith("|"):
            flush()
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            out.append(_table(lines[i:j]))
            i = j
            continue
        if s.startswith(">"):
            flush()
            j, quote = i, []
            while j < len(lines) and lines[j].strip().startswith(">"):
                quote.append(lines[j].strip()[1:].strip())
                j += 1
            out.append("<blockquote>" + "<br>".join(inline(q) for q in quote) + "</blockquote>")
            i = j
            continue
        m = re.match(r"\s*([-*+]|\d+[.)])\s+(.*)", line)
        if m:
            flush()
            # 項目は（字下げの幅・ol か ul・本文）で集め、字下げが深い項目は直前の項目の中の入れ子の箇条書きにする
            # （CHANGELOG の「追加」の下の細目が、平らに並んで親子が見えなかった・2026-10-22）
            items, j = [], i
            while j < len(lines):
                mm = re.match(r"(\s*)([-*+]|\d+[.)])\s+(.*)", lines[j])
                if mm:
                    items.append([len(mm.group(1).expandtabs(4)), "ol" if mm.group(2)[0].isdigit() else "ul", mm.group(3)])
                elif lines[j].strip() and lines[j].startswith((" ", "\t")) and items:
                    items[-1][2] += " " + lines[j].strip()  # 続きの行は同じ項目に足す
                else:
                    break
                j += 1
            out.append(_list(items, 0, items[0][0])[0])
            i = j
            continue
        para.append(s)
        i += 1
    flush()
    return "\n".join(out)


# 折りたたみ（details）の開閉を、高さの動きでつなぐ。details は既定では一瞬で開閉する（2026-10-22 かしぇ「▼要素のアニメーションがそっち側にない」）。
# 開くときは開いた高さまで伸ばし（長いほど少し長く・上限 0.42 秒・減速）、閉じるときは見出しの高さまで縮めてから open を外す（0.24 秒）
DETAILS_JS = ("(function(){var RM=matchMedia('(prefers-reduced-motion:reduce)');"
              "document.querySelectorAll('details').forEach(function(d){var s=d.querySelector('summary'),an=null;if(!s||!d.animate)return;"
              "s.addEventListener('click',function(e){if(RM.matches)return;e.preventDefault();var h0=d.offsetHeight;if(an)an.cancel();"
              "var cs=getComputedStyle(d),pad=parseFloat(cs.paddingTop)+parseFloat(cs.paddingBottom)+parseFloat(cs.borderTopWidth)+parseFloat(cs.borderBottomWidth);"
              "d.style.overflow='hidden';"
              "if(!d.open||d.classList.contains('closing')){d.classList.remove('closing');d.open=true;var h1=d.offsetHeight;"
              "an=d.animate([{height:h0+'px'},{height:h1+'px'}],{duration:Math.min(420,200+Math.abs(h1-h0)*.3),easing:'cubic-bezier(.33,1,.68,1)'});"
              "an.onfinish=function(){an=null;d.style.overflow=''}}"
              "else{d.classList.add('closing');an=d.animate([{height:h0+'px'},{height:(s.offsetHeight+pad)+'px'}],{duration:240,easing:'cubic-bezier(.65,0,.35,1)'});"
              "an.onfinish=function(){an=null;d.open=false;d.classList.remove('closing');d.style.overflow=''}}})})})();")


# ダッシュボードの本体の枠（iframe）に開かれたときだけ、指の位置を親へ送る。枠の上の指の動きは親に届かず、
# 横に引いて一覧を開く操作が効かなかった（2026-10-22 かしぇ「サイドバー引っ張って開けないのは結構きつい」）。
# 送るのは位置だけで、縦のスクロールはこの文書がそのまま受ける。横にスクロールできる表の上で始めた操作は送らない（表に譲る）。
# ファイルを直接開いた束でも届くよう postMessage で送る。
# 文書の一番上から下へ引いたときは「引っぱって更新」として引いた量（pull）を送り、この文書のスクロールと弾みは止める
# （同日かしぇ「引っぱって更新も足して」）。向きは 10px 動くまで決めない（親の本体と同じ）
FRAME_JS = ("(function(){if(window.parent===window)return;var on=false,mode='',x0=0,y0=0,top=false;"
            "function post(o){o.imz='touch';parent.postMessage(o,'*')}"
            "function send(k,e){var p=e.changedTouches[0];post({type:k,x:p.clientX,y:p.clientY})}"
            "addEventListener('touchstart',function(e){var w=e.target.closest&&e.target.closest('.tablewrap,pre');"
            "on=e.touches.length===1&&!(w&&w.scrollWidth>w.clientWidth);mode='';top=scrollY<=0;"
            "if(on){x0=e.touches[0].clientX;y0=e.touches[0].clientY;send('down',e)}},{passive:true});"
            "addEventListener('touchmove',function(e){if(!on)return;var p=e.touches[0],dx=p.clientX-x0,dy=p.clientY-y0;"
            "if(!mode&&Math.hypot(dx,dy)>=10){mode=top&&dy>0&&Math.abs(dy)>Math.abs(dx)?'pull':'free';if(mode==='pull')y0=p.clientY}"
            "if(mode==='pull'){if(e.cancelable)e.preventDefault();post({type:'pull',dy:p.clientY-y0})}else send('move',e)},{passive:false});"
            "function up(e){if(!on)return;on=false;if(mode==='pull')post({type:'pullend'});else send('up',e)}"
            "addEventListener('touchend',up,{passive:true});addEventListener('touchcancel',up,{passive:true})})();")


def page(title: str, body: str, extra_head: str = "", scripts: tuple[str, ...] = ()) -> str:
    """文書のページの外枠。body は組み終わった HTML（.sheet を並べたもの）。
    スクリプトは折りたたみの動き（DETAILS_JS）・印刷の前に根拠を開く（PRINT_JS）と、渡されたものだけを、中身のハッシュで許して置く"""
    import hashlib
    js = [*scripts, DETAILS_JS, PRINT_JS, FRAME_JS]
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'" for s in js)
    csp = f"default-src 'none'; {CSP_FONTS}; script-src {hashes}"
    tags = "".join(f"<script>{s}</script>" for s in js)
    return (f'<!doctype html>\n<html lang="ja"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta http-equiv="Content-Security-Policy" content="{csp}">{HEAD_META}'
            f"<title>{html.escape(title)}</title>{FONT_LINK}{extra_head}</head>\n<body><main>\n{body}\n</main>{tags}</body></html>\n")
