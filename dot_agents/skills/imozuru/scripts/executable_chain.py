#!/usr/bin/env python3
"""論文の引用を前へ・後ろへたどる（OpenAlex）。

Bates 1989 の footnote chasing（後ろへ）と citation searching（前へ）を道具でやる。
引用をたどると、その分野の言葉を知らなくても次の論文に行ける（Bates 1989 L301-302）。

OpenAlex は1日 1,000 回まで無料の枠（x-ratelimit-limit-usd 0.1）。プリペイドの残高が
0 なら枠を超えても止まるだけで課金されない。API キーや支払いの登録はしない。

使い方:
    chain.py find  <DOI か題名>          … 論文を特定して ID を出す（題名なら候補5件）
    chain.py refs  <ID か DOI> [-n 20]    … 後ろへ: その論文が引いている文献
    chain.py cites <ID か DOI> [-n 20]    … 前へ: その論文を引いている文献（被引用の多い順）
    chain.py author <著者名か著者ID> [-n 20] … 著者で追う: その人の論文（被引用の多い順）
                                            名前なら「# 別の候補」の行に同名の別人の ID も出す
    --log <topic_dir> --round N を付けると、出した一覧を詳細レポートの記録（queries.jsonl）にも足す
出力: 1行1本、タブ区切り（年 被引用数 ID 題名 DOI 無料PDF）
"""

import json
import re
import sys
import urllib.parse
import urllib.request

API = "https://api.openalex.org"
# OpenAlex の work ID（W と数字だけ）。「Weak …」のような題名と取り違えないよう、形で見分ける
WORK_ID = re.compile(r"W\d+")
AUTHOR_ID = re.compile(r"A\d+")
FIELDS = "id,display_name,publication_year,cited_by_count,doi,best_oa_location"
# API の応答の大きさの上限。200本の一覧でも数百 KB に収まる。
MAX_BYTES = 20_000_000
# 1回に出す本数の上限。OpenAlex の per-page の上限と同じ。
MAX_N = 200


class _SameOrigin(urllib.request.HTTPRedirectHandler):
    """転送は API と同じ場所（https://api.openalex.org）の中だけたどる。

    素の urlopen は転送の先をどこへでもたどるので、応答が 127.0.0.1 へ転送すると、
    手元のサービスの中身を読んでしまう（2026-10-20 の2回目のレビュー）。転送の本体は読まずに閉じる。
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        if not newurl.startswith(API + "/"):
            raise ValueError(f"API の外への転送はたどらない: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameOrigin)


def get(path: str, **params) -> dict:
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "imozuru (mailto omitted)"})
    with _OPENER.open(req, timeout=60) as res:
        body = res.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError(f"応答が {MAX_BYTES:,} バイトを超える")
    return json.loads(body)


def clean(s: object) -> str:
    """API の値を1行の出力に入れる形にする。タブ・改行の仲間・制御文字は空白にする。

    題名や著者名は論文の著者や登録者が書く。タブや改行が残ると列や行が増え、エージェントが表を読み違える。
    端末を操る ESC の並びも、ここで消す。
    文字の向きを変える制御文字（U+202E など）と幅の無い空白も消す。題名の一部を逆向きに見せたり、
    見た目が同じで中身の違う文字列を作ったりできる。ZWJ・ZWNJ は絵文字や一部の文字で要るので残す。
    """
    return re.sub(r"[\s\x00-\x1f\x7f-\x9f  \u200b\u200e\u200f\u202a-\u202e\u2060-\u2069\ufeff]+", " ", str(s)).strip()


def author_line(a: dict, aid: str) -> str:
    """著者1人を「名前 ID 所属 論文数」の1行にする。"""
    inst = ", ".join(clean(i.get("display_name") or "") for i in a.get("last_known_institutions") or [])
    return f"{clean(a.get('display_name') or '')} {aid} {inst} 論文{clean(a.get('works_count'))}本"


def search_title(key: str) -> list[dict]:
    """題名だけを対象に探し、被引用の多い順に5件返す。

    全文検索（search=）は解説記事や重複の記録が上に来て、Kuhlthau 1991 の本体が
    5位以内に出なかった。題名に絞って被引用順に並べると本体が1位に来た。
    題名に著者名を混ぜると外れるので、題名の語だけを渡す。

    登録された題名が副題抜きのことがある（Marchionini 2006 は "Exploratory search"
    だけ）。全部の語では0件になるので、0件なら前半の3語で引き直す。
    """
    words = key.replace(",", " ").replace(":", " ").split()
    if not words:  # 空の条件で問い合わせると、題名を絞らない検索になる
        return []
    # 3語以下なら前半の3語は全部と同じ。同じ問い合わせを2回送って枠を使わない
    for terms in (words, words[:3]) if len(words) > 3 else (words,):
        hits = get("/works", filter="title.search:" + " ".join(terms),
                   sort="cited_by_count:desc", **{"per-page": 5}, select=FIELDS)["results"]
        if hits:
            return hits
    return []


def resolve(key: str) -> dict:
    """DOI・OpenAlex ID・題名のどれからでも論文を1本引く。題名なら被引用の最も多い1本。

    ID と DOI は API の道筋に入る。「?」や「../」を含む値で問い合わせの形を変えられないよう、
    ID は形を確かめ、DOI は「.」「..」の区切りを断ってから符号化して入れる。
    doi.org の URL は % で符号化済みなので、一度戻してから符号化する（二重にすると %28 が %2528 になる）。
    """
    if WORK_ID.fullmatch(key) or "openalex.org/" in key:
        wid = key.rstrip("/").rsplit("/", 1)[-1]
        if not WORK_ID.fullmatch(wid):
            raise SystemExit(f"OpenAlex の ID の形ではない: {clean(key)}")
        return get(f"/works/{wid}", select=FIELDS)
    if key.startswith("10.") or "doi.org/" in key:
        doi = urllib.parse.unquote(key.split("doi.org/")[-1]) if "doi.org/" in key else key
        if any(part in {".", ".."} for part in doi.split("/")):
            raise SystemExit(f"DOI に「.」か「..」の区切りがある: {clean(key)}")
        return get(f"/works/doi:{urllib.parse.quote(doi, safe='/')}", select=FIELDS)
    hits = search_title(key)
    if not hits:
        raise SystemExit(f"見つからない: {clean(key)}")
    return hits[0]


def row(w: dict) -> str:
    """1本を1行に。どの値も clean() を通す。"""
    oa = (w.get("best_oa_location") or {}).get("pdf_url") or ""
    wid = (w.get("id") or "").rsplit("/", 1)[-1]
    return "\t".join(clean(x) for x in (
        w.get("publication_year"), w.get("cited_by_count"), wid,
        (w.get("display_name") or "")[:120], w.get("doi") or "", oa))


def main() -> int:
    args = sys.argv[1:]
    n = 20
    if "-n" in args:
        i = args.index("-n")
        value = args[i + 1] if i + 1 < len(args) else ""
        # isdigit() は「²」も数字と見なすので、ASCII の数字だけを通す
        if not re.fullmatch(r"[0-9]+", value) or not 1 <= int(value) <= MAX_N:
            print(f"-n には 1〜{MAX_N} の数を書く", file=sys.stderr)
            return 2
        n = int(value)
        del args[i:i + 2]
    log_topic, log_round = None, None
    if "--log" in args:
        i = args.index("--log")
        if i + 1 >= len(args):
            print("--log には調べものの置き場を書く", file=sys.stderr)
            return 2
        log_topic = args[i + 1]
        del args[i:i + 2]
        if "--round" not in args:
            print("--log には --round N も付ける", file=sys.stderr)
            return 2
    if "--round" in args:
        i = args.index("--round")
        value = args[i + 1] if i + 1 < len(args) else ""
        if not re.fullmatch(r"[0-9]+", value):
            print("--round には周の数を書く", file=sys.stderr)
            return 2
        log_round = int(value)
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, key = args[0], " ".join(args[1:])
    shown: list[dict] = []

    if cmd == "find":
        # 題名のときは候補を全部見せる。どれが本体かを読み手が確かめられるように。
        hits = [resolve(key)] if WORK_ID.fullmatch(key) or key.startswith("10.") or "/" in key else search_title(key)
        if not hits:
            print(f"候補なし: {clean(key)}（DOI で引き直すか、題名の語を減らす）")
        for w in hits:
            print(row(w))
        shown += hits
    elif cmd in ("refs", "cites"):
        # 応答の ID も次の問い合わせに入るので、形を確かめてから使う
        wid = (resolve(key).get("id") or "").rsplit("/", 1)[-1]
        if not WORK_ID.fullmatch(wid):
            raise SystemExit(f"応答の ID の形がおかしい: {clean(wid)}")
        flt = f"cited_by:{wid}" if cmd == "refs" else f"cites:{wid}"
        res = get("/works", filter=flt, sort="cited_by_count:desc",
                  **{"per-page": n}, select=FIELDS)
        print(f"# {cmd} {wid} 全{clean(res['meta']['count'])}本中 上位{len(res['results'])}本")
        for w in res["results"]:
            print(row(w))
        shown += res["results"]
    elif cmd == "author":
        # 著者 ID（A と数字）ならその人を直接引く。名前なら検索の1位を使い、ほかの候補も並べる。
        # 名前だけでは同姓同名を見分けられないので、別人だったら候補の ID で引き直せるようにする
        if AUTHOR_ID.fullmatch(key):
            hits = [get(f"/authors/{key}")]
        else:
            hits = get("/authors", search=key, **{"per-page": 5})["results"]
        if not hits:
            raise SystemExit(f"著者が見つからない: {clean(key)}")
        ids = [(a.get("id") or "").rsplit("/", 1)[-1] for a in hits]
        if not all(AUTHOR_ID.fullmatch(i) for i in ids):
            raise SystemExit(f"応答の著者 ID の形がおかしい: {clean(' '.join(ids))}")
        a, aid = hits[0], ids[0]
        print(f"# author {author_line(a, aid)}")
        for other, oid in zip(hits[1:], ids[1:]):
            print(f"# 別の候補 {author_line(other, oid)}（この人なら chain.py author {oid}）")
        res = get("/works", filter=f"author.id:{aid}", sort="cited_by_count:desc",
                  **{"per-page": n}, select=FIELDS)
        for w in res["results"]:
            print(row(w))
        shown += res["results"]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    if log_topic:
        log(log_topic, log_round, cmd, key, shown)
    return 0


def log(topic: str, round_: int, cmd: str, key: str, works: list[dict]) -> None:
    """出した一覧を queries.jsonl に足す。URL は DOI を先に、無ければ OpenAlex の頁。無料 PDF も照合に使う。"""
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import digest  # 同じフォルダ。--log を使うときだけ読む

    def http_url(u):
        if not isinstance(u, str):
            return False
        try:
            return urllib.parse.urlsplit(u).scheme in ("http", "https")
        except ValueError:
            return False

    hits = []
    for w in works:
        location = w.get("best_oa_location")
        oa = location.get("pdf_url") if isinstance(location, dict) else None
        url = next((u for u in (w.get("doi"), w.get("id")) if http_url(u)), None)
        if not url:
            continue
        hit = {"title": clean(w.get("display_name") or ""), "url": url}
        if http_url(oa):
            hit["also"] = [oa]
        hits.append(hit)
    record = digest.normalize_record({
        "round": round_, "by": "chain.py", "method": cmd, "query": key, "hits": hits}, None, None)
    digest.append_records(Path(topic).expanduser(), [record])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as e:  # 接続の失敗・HTTP のエラー・壊れた JSON を1行で返す
        print(f"取れなかった: {type(e).__name__}: {clean(e)}", file=sys.stderr)
        sys.exit(1)
