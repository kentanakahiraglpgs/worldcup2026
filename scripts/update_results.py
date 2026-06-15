#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
W杯2026 スコア自動取得スクリプト
TheSportsDB(無料・キー不要)から2026 FIFA World Cupの結果を取得し、
index.html の対戦カードに突合して results.json を更新する。

- 対戦カードは index.html の Mg(...) 行から自動抽出（単一ソース）
- 英→日チーム名はエイリアス＋正規化(小文字/記号/アクセント除去)で堅牢に突合
- グループ戦は「同一ペアは1回だけ」を利用し日付ズレ(JST差)を無視してペアで突合
- 既存 results.json の ko(決勝T手入力分) は保持

使い方:
  python3 scripts/update_results.py          # results.json を更新
  python3 scripts/update_results.py --dry     # 書き込まず内容を表示
"""
import json, re, sys, os, urllib.request, unicodedata
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "results.json")
JST = timezone(timedelta(hours=9))

LEAGUE_ID = "4429"   # FIFA World Cup (TheSportsDB)
SEASON = "2026"
KEY = "3"            # TheSportsDB 無料公開キー
ENDPOINTS = [
    f"https://www.thesportsdb.com/api/v1/json/{KEY}/eventsseason.php?id={LEAGUE_ID}&s={SEASON}",
    f"https://www.thesportsdb.com/api/v1/json/{KEY}/eventspastleague.php?id={LEAGUE_ID}",
]

# JA → 想定される英語表記(TheSportsDB)エイリアス
JA_EN = {
    "メキシコ": ["Mexico"], "南アフリカ": ["South Africa"], "韓国": ["South Korea", "Korea Republic", "Korea"],
    "チェコ": ["Czech Republic", "Czechia"], "カナダ": ["Canada"],
    "ボスニア・ヘルツェゴビナ": ["Bosnia-Herzegovina", "Bosnia and Herzegovina", "Bosnia"],
    "ハイチ": ["Haiti"], "スコットランド": ["Scotland"], "アメリカ": ["USA", "United States"],
    "パラグアイ": ["Paraguay"], "カタール": ["Qatar"], "スイス": ["Switzerland"], "ブラジル": ["Brazil"],
    "モロッコ": ["Morocco"], "オーストラリア": ["Australia"], "トルコ": ["Turkey", "Turkiye", "Türkiye"],
    "ドイツ": ["Germany"], "キュラソー": ["Curacao", "Curaçao"], "オランダ": ["Netherlands", "Holland"],
    "日本": ["Japan"], "コートジボワール": ["Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"],
    "エクアドル": ["Ecuador"], "スウェーデン": ["Sweden"], "チュニジア": ["Tunisia"], "スペイン": ["Spain"],
    "カーボベルデ": ["Cape Verde", "Cabo Verde"], "ベルギー": ["Belgium"], "エジプト": ["Egypt"],
    "サウジアラビア": ["Saudi Arabia"], "ウルグアイ": ["Uruguay"], "イラン": ["Iran", "IR Iran"],
    "ニュージーランド": ["New Zealand"], "フランス": ["France"], "セネガル": ["Senegal"], "イラク": ["Iraq"],
    "ノルウェー": ["Norway"], "アルゼンチン": ["Argentina"], "アルジェリア": ["Algeria"],
    "オーストリア": ["Austria"], "ヨルダン": ["Jordan"], "ポルトガル": ["Portugal"],
    "コンゴ民主共和国": ["DR Congo", "Congo DR", "Democratic Republic of the Congo", "Congo Democratic Republic"],
    "イングランド": ["England"], "クロアチア": ["Croatia"], "ガーナ": ["Ghana"], "パナマ": ["Panama"],
    "ウズベキスタン": ["Uzbekistan"], "コロンビア": ["Colombia"],
}

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())

# 正規化EN → JA の逆引き
EN_TO_JA = {}
for ja, ens in JA_EN.items():
    for en in ens:
        EN_TO_JA[norm(en)] = ja

def extract_group_fixtures():
    """index.html の Mg(...) からグループ戦カードを抽出: [(date, home, away), ...]"""
    html = open(INDEX, encoding="utf-8").read()
    pat = re.compile(r'Mg\("([^"]*)","([^"]*)","([^"]*)","([^"]*)","([^"]*)"')
    out = []
    for m in pat.finditer(html):
        d, dow, time, a, b = m.groups()
        out.append((d, a, b))
    return out

def fetch_events():
    evs = {}
    for url in ENDPOINTS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wc2026-bot"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            for e in (data.get("events") or []):
                evs[e.get("idEvent")] = e
        except Exception as ex:
            print(f"[warn] fetch失敗 {url}: {ex}", file=sys.stderr)
    return list(evs.values())

def main():
    dry = "--dry" in sys.argv
    fixtures = extract_group_fixtures()
    # 無向ペア(JA) → (home, away, date)
    pair_index = {}
    for d, a, b in fixtures:
        pair_index[frozenset((a, b))] = (a, b, d)

    events = fetch_events()
    scores = {}
    unresolved = []
    for e in events:
        hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
        if hs in (None, "") or as_ in (None, ""):
            continue
        try:
            hs, as_ = int(hs), int(as_)
        except (TypeError, ValueError):
            continue
        en_h, en_a = e.get("strHomeTeam"), e.get("strAwayTeam")
        ja_h, ja_a = EN_TO_JA.get(norm(en_h)), EN_TO_JA.get(norm(en_a))
        if not ja_h or not ja_a:
            unresolved.append(f"{en_h} vs {en_a}")
            continue
        key_pair = frozenset((ja_h, ja_a))
        fx = pair_index.get(key_pair)
        if not fx:
            continue  # グループ戦に無い(=決勝T等)はスキップ
        home, away, date = fx
        # app側のhome/away順に合わせてスコアを並べる
        if ja_h == home:
            sa, sb = hs, as_
        else:
            sa, sb = as_, hs
        scores["%s|%s|%s" % (home, away, date)] = [sa, sb]

    # 既存 ko(手入力分) を保持
    ko = {}
    if os.path.exists(OUT):
        try:
            ko = json.load(open(OUT, encoding="utf-8")).get("ko", {}) or {}
        except Exception:
            ko = {}

    result = {
        "updated": datetime.now(JST).isoformat(timespec="minutes"),
        "_format": "scores: { 'ホーム|アウェイ|M/D': [得点H, 得点A] }  /  ko: { '試合番号': [得点A, 得点B] }  ※自動更新 by scripts/update_results.py (TheSportsDB)",
        "scores": scores,
        "ko": ko,
    }

    print(f"fixtures={len(fixtures)} events={len(events)} matched_scores={len(scores)}")
    if unresolved:
        print("[未対応のチーム名] " + ", ".join(sorted(set(unresolved))), file=sys.stderr)

    if dry:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"wrote {OUT}")

if __name__ == "__main__":
    main()
