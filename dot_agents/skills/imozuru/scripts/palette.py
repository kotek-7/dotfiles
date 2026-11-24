"""imozuru が書き出すページ（履歴ダッシュボード・抜き書き・詳細レポート・戻るボタン）の色の唯一の置き場。

色はすべて OKLCH で、ここの色見本（SWATCH）から役割の名前へ割り当てる。ページの側は役割の名前
（CSS の変数）だけを使い、色の値を直接書かない。透かしは color-mix で役割の色から作る。
tests/test_palette.py が、書き出したページの中の oklch() がすべてここの値かを確認する。

外観は「昆虫の標本箱」（2026-10-21 かしぇが3つの棚の見本から A を選んだ）。胡桃材の濃い地に象牙の面、
標本の色を点で入れる。文書（抜き書き・詳細レポート）は象牙の紙を地にし、暗い設定では胡桃材の地にする。
"""

SWATCH = {
    # 胡桃材。暗い地の段。数字が小さいほど暗い
    "walnut-1": "oklch(0.15 0.022 50)",
    "walnut-2": "oklch(0.21 0.03 50)",
    "walnut-3": "oklch(0.25 0.032 53)",
    "walnut-4": "oklch(0.27 0.035 55)",
    "walnut-5": "oklch(0.32 0.035 58)",
    "walnut-6": "oklch(0.34 0.045 62)",
    "walnut-7": "oklch(0.36 0.035 60)",
    "walnut-8": "oklch(0.42 0.04 60)",
    # 象牙。明るい地と、暗い地の上の文字
    "ivory-1": "oklch(0.98 0.015 88)",
    "ivory-2": "oklch(0.94 0.025 85)",
    "ivory-3": "oklch(0.93 0.02 85)",
    "ivory-4": "oklch(0.89 0.06 85)",
    "ivory-5": "oklch(0.82 0.03 80)",
    "ivory-6": "oklch(0.76 0.03 80)",
    # 墨。象牙の地の上の文字
    "sumi-1": "oklch(0.25 0.04 58)",
    "sumi-2": "oklch(0.3 0.03 55)",
    "sumi-3": "oklch(0.44 0.03 60)",
    # 琥珀。文書の差し色
    "amber-dark": "oklch(0.47 0.1 65)",
    "amber-light": "oklch(0.77 0.11 74)",
    "amber-hit": "oklch(0.35 0.045 70)",
    # コルク。本体の地（2026-10-22 かしぇが「コルク板＋象牙の台紙」を選んだ）。象牙の文字 6.98・台紙との差 7.2
    "cork": "oklch(0.42 0.055 62)",
    # 真鍮。標本箱の金具（一覧の幅を変えるつまみ）
    "brass": "oklch(0.7 0.09 82)",
    "brass-dark": "oklch(0.42 0.06 70)",
    # 影と光沢。透かして使う
    "umbra": "oklch(0.08 0.02 50)",
    "glass": "oklch(1 0 0)",
    # 紅芋の紅紫（ブランドの色）。説明の図で画面の部品を指す番号の印だけに使う。胡桃材の暗い地にも象牙の紙にも埋もれない明るさ
    "beni": "oklch(0.56 0.19 350)",
}

# 履歴ダッシュボード（胡桃材の地・詳細は象牙の札）
DASH = {
    "paper": "walnut-4", "paper2": "walnut-2", "card": "walnut-5", "card2": "walnut-7", "line": "walnut-8",
    "lamp": "walnut-6", "side-bg": "walnut-1", "ink": "ivory-3", "sub": "ivory-6",
    "ivory": "ivory-2", "ivory-ink": "sumi-2", "ivory-sub": "sumi-3", "ivory-line": "ivory-5",
    "umbra": "umbra", "glass": "glass", "cork": "cork", "brass": "brass", "brass-dark": "brass-dark", "beni": "beni",
}

# 抜き書きと詳細レポート。明るい設定は象牙の紙、暗い設定は胡桃材
DOC_LIGHT = {"bg": "ivory-2", "ink": "sumi-1", "sub": "sumi-3", "accent": "amber-dark",
             "card": "ivory-1", "line": "ivory-5", "hit": "ivory-4"}
DOC_DARK = {"bg": "walnut-2", "ink": "ivory-3", "sub": "ivory-6", "accent": "amber-light",
            "card": "walnut-3", "line": "walnut-7", "hit": "amber-hit"}

# 文書に重ねる戻るボタン。地の明暗の反対側を当てる
HUD_LIGHT = {"hud-bg": "walnut-4", "hud-fg": "ivory-2", "hud-umbra": "umbra"}
HUD_DARK = {"hud-bg": "ivory-2", "hud-fg": "walnut-4", "hud-umbra": "umbra"}

# 標本の4色（終了理由の分類）と棒・原文の色。dataviz の validate_palette.js を暗い面 walnut-5 の上で
# 全組み合わせ通した（色覚の差は注意の範囲＝文字ラベルを必ず添える）。
# p- の付く色は象牙の台紙（ivory-2）の上に置く棒と点。暗い面の色のままだと緑の対比が 2.45 で、3 に届かなかった。
# 台紙の上で validate_palette.js --pairs all を全部通した組（2026-10-22）
# 案1・案2 はキーカラーとキーフォントだけを変えた見比べ用。決まったら1つにする
THEMES = {
    "1": {"bar": "oklch(0.62 0.13 75)", "src": "oklch(0.66 0.15 150)",
          "r1": "oklch(0.62 0.14 245)", "r2": "oklch(0.66 0.15 150)", "r3": "oklch(0.62 0.13 75)", "r4": "oklch(0.56 0.17 345)",
          "p-r1": "oklch(0.52 0.14 245)", "p-r2": "oklch(0.47 0.13 150)", "p-r3": "oklch(0.61 0.13 75)", "p-r4": "oklch(0.52 0.17 345)",
          "p-bar": "oklch(0.61 0.13 75)", "p-src": "oklch(0.47 0.13 150)",
          "head": '"Shippori Mincho"', "font": "Shippori+Mincho:wght@500;700"},
    "2": {"bar": "oklch(0.66 0.13 85)", "src": "oklch(0.6 0.15 350)",
          "r1": "oklch(0.6 0.13 250)", "r2": "oklch(0.64 0.13 160)", "r3": "oklch(0.66 0.13 85)", "r4": "oklch(0.6 0.15 350)",
          "p-r1": "oklch(0.48 0.13 250)", "p-r2": "oklch(0.5 0.13 160)", "p-r3": "oklch(0.62 0.13 85)", "p-r4": "oklch(0.56 0.15 350)",
          "p-bar": "oklch(0.62 0.13 85)", "p-src": "oklch(0.56 0.15 350)",
          "head": '"Zen Old Mincho"', "font": "Zen+Old+Mincho:wght@500;700"},
}


def css_vars(roles: dict) -> str:
    """役割の表を CSS の変数の並び（--名前:値;…）にする"""
    return "".join(f"--{k}:{SWATCH[v]};" for k, v in roles.items())


def mix(role: str, percent: int) -> str:
    """役割の色を透かす。値を直接書かずに、変数から作る"""
    return f"color-mix(in oklch,var(--{role}) {percent}%,transparent)"


def all_values() -> set[str]:
    """ページに出てよい oklch() の値の全部"""
    return set(SWATCH.values()) | {v for t in THEMES.values() for k, v in t.items() if v.startswith("oklch(")}


def hex_of(value: str) -> str:
    """oklch() の値を #rrggbb にする。CSS の外（アプリの指定の manifest）は oklch を読めないことがあるので、そこだけに使う。
    変換は OKLab の定義どおり（Ottosson 2020）。sRGB の外の色は端に寄せる"""
    import math
    L, C, h = (float(x) for x in value[value.index("(") + 1:value.index(")")].split()[:3])
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_, m_, s_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, \
        (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)

    def gamma(x):
        x = min(1.0, max(0.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return "#" + "".join(f"{round(gamma(c) * 255):02x}" for c in lin)
