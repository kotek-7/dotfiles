#!/usr/bin/env python3
"""ダッシュボードの質感の絵（assets/cork.png・assets/paper.png）と、ホーム画面のアイコン（assets/apple-touch-icon.png）と
タブの印（assets/favicon.png）を描き出す。開発用の道具。

質感やロゴを変えたときだけ回す。ページを作るたびには要らない（dashboard.py は出来上がった PNG を使うだけ）。
描くのにブラウザ（playwright の chromium）を使う。SVG のフィルタの描き方はブラウザに依存するので、毎回同じものでそろえる。

使い方:
    make_textures.py        … 質感の絵（2倍の解像度・透過）とアイコンを全部描き直す
    make_textures.py icons  … アイコン（ホーム画面・タブ・アプリの 192px と 512px）だけを描き直す
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard  # noqa: E402
import palette  # noqa: E402

ICON_SIZE = 180  # iPhone のホーム画面のアイコンの大きさ（px）。角の丸めは iPhone がかける
# 紋の周りの余白。紋は丸いので、iPhone が角を丸めても欠けない。ロゴの SVG の中にも紋の外に約6%の余白がある
# （0.14 では小さく見えた・2026-10-22 かしぇ「もうちょっとアイコンロゴ大きくていいかも」）
ICON_PAD = 0.05
# タブの印は 16px（高精細の画面で 32px）で出るので、その倍の 64px で描いて縮めてもらう。
# 紋だけを透過の地に置くと明るいタブで字が消えた（象牙の線が白地に溶ける）ので、アイコンと同じ胡桃材の地に置く。
# タブの印は角を丸めてもらえないので、自分で角を丸める（四角のままだと周りの印より重く見える）
FAVICON = dashboard.LOGO.with_name("favicon.png")
FAVICON_SIZE = 64
FAVICON_PAD = 0.03
FAVICON_RADIUS = 12


def icon_html(size: int = ICON_SIZE, pad_ratio: float = ICON_PAD, radius: int = 0) -> str:
    """ロゴの紋（左の丸い印）だけを、一覧と同じ胡桃材の地の正方形に置く。
    ロゴの SVG は紋が左端の 1254 角に収まり、字はその右にあるので、viewBox を正方形に絞れば紋だけが残る。
    ホーム画面のアイコンは地を透過にしない（iPhone は透過の所を黒で埋める）ので radius=0。角は iPhone が丸める"""
    svg = dashboard.LOGO_LIGHT.read_text(encoding="utf-8")
    side = re.search(r'viewBox="0 0 \d+(?:\.\d+)? (\d+(?:\.\d+)?)"', svg).group(1)
    svg = re.sub(r'viewBox="[^"]*"', f'viewBox="0 0 {side} {side}"', svg, count=1)
    pad = round(size * pad_ratio)
    return (f'<style>html,body{{margin:0;background:transparent}}'
            f'div{{width:{size}px;height:{size}px;border-radius:{radius}px;background:{palette.SWATCH[palette.DASH["side-bg"]]}}}'
            f'svg{{display:block;width:{size - 2 * pad}px;height:{size - 2 * pad}px;padding:{pad}px}}</style><div>{svg}</div>')


def main() -> int:
    from playwright.sync_api import sync_playwright
    icons_only = sys.argv[1:] == ["icons"]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (png, svg, size) in ({} if icons_only else dashboard.TEXTURES).items():
            page = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=2)
            page.set_content(f"<style>html,body{{margin:0;background:transparent}}</style>{svg()}")
            page.screenshot(path=str(png), omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})
            print(f"→ {png}（{png.stat().st_size / 1024:.0f} KB）")
        # アプリとして入れたときのアイコン（192px・512px）は、ホーム画面のアイコンと同じ絵を大きく描く
        apps = [(png, int(re.search(r"\d+", path).group())) for path, png in dashboard.APP_ICONS.items()]
        for png, size, html_ in ((dashboard.ICON, ICON_SIZE, icon_html()),
                                 (FAVICON, FAVICON_SIZE, icon_html(FAVICON_SIZE, FAVICON_PAD, FAVICON_RADIUS)),
                                 *[(png, size, icon_html(size)) for png, size in apps]):
            page = browser.new_page(viewport={"width": size, "height": size})
            page.set_content(html_)
            page.screenshot(path=str(png), omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})
            print(f"→ {png}（{png.stat().st_size / 1024:.1f} KB）")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
