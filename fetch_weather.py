# -*- coding: utf-8 -*-
r"""
fetch_weather.py
ねこのひげ - Open-Meteo から指定期間の hourly 天気データを取得し
WeatherRecord に upsert する。緯度経度は DB の UserLocation を使用。

配置パス:
  C:/Users/t-nsugimoto/source/repos/neko_no_hige/fetch_weather.py

実行例 (PowerShell):
  (.venv) PS C:/Users/t-nsugimoto/source/repos/neko_no_hige>
      python ./fetch_weather.py

依存:
  requests  (未インストールなら: pip install requests)
"""
# Python3.13でも型ヒントを文字列扱いにして前方参照を楽にする（おまじない）
from __future__ import annotations

# os=環境変数操作 / sys=終了コード返却 に使う
import os
import sys
# 日時計算用。timezone は dt_tz という別名で読み込む（後述のJST生成に使用）
from datetime import datetime, timedelta, timezone as dt_tz

# --- Django セットアップ ------------------------------------------------
# このスクリプトは manage.py を経由せず単体実行するため、
# 「どの settings を使うか」を自分で Django に教える必要がある。
DJANGO_SETTINGS_MODULE_NAME = "config.settings"
# 環境変数 DJANGO_SETTINGS_MODULE を設定（既に在ればそれを尊重）
os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE_NAME)

import django  # noqa: E402
# Djangoを初期化。これを呼ぶ前に models を import するとエラーになる
django.setup()

# 初期化後だからモデルを安全に読み込める（noqa=import位置の警告抑制）
from tracker.models import WeatherRecord, UserLocation  # noqa: E402

# --- 取得対象 -----------------------------------------------------------
START_DATE = "2026-05-30"   # 取得開始日 JST 00:00（この日を含む）
END_DATE   = "2026-06-03"   # 取得終了日 JST 23:00（この日を含む）
TZ_NAME = "Asia/Tokyo"      # Open-Meteoへ渡すタイムゾーン名

# Open-Meteo の予報API（過去日も past_days で取得可能）
API_URL = "https://api.open-meteo.com/v1/forecast"


def reduce_weather_code(code: int) -> int:
    """Open-Meteo WMO weather code を 4分類に縮約。
    0=快晴 -> 0(晴)
    1,2=主に晴/一部曇 -> 1(晴のち曇)
    3=曇 -> 2(曇)
    上記以外(霧/雨/雪/雷雨等) -> 3(雨扱い)
    """
    if code == 0:
        return 0
    if code in (1, 2):
        return 1
    if code == 3:
        return 2
    # それ以外（霧・雨・雪・雷雨など）はすべて「雨扱い」にまとめる
    return 3


def parse_jst(s: str) -> datetime:
    """Open-Meteo は timezone=Asia/Tokyo 指定時、'YYYY-MM-DDTHH:MM' の
    naive JST 文字列を返す。aware な JST datetime に変換する。
    （naive=タイムゾーン情報なし / aware=あり。DB保存にはawareが安全）
    """
    # +9時間 のタイムゾーン（=日本時間JST）を作る
    jst = dt_tz(timedelta(hours=9))
    # 文字列を日時に変換し、JST情報を付与して返す
    return datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=jst)


def main() -> int:
    # requests は外部ライブラリなので、未導入なら親切に案内して終了
    try:
        import requests  # noqa: WPS433
    except ImportError:
        print("[err] requests が未インストールです: pip install requests を実行してください")
        return 1  # 異常終了（0以外）

    # --- 現在地を DB から取得 ----------------------------------------
    # UserLocation.current() は pk=1 の1行を返す（無ければデフォルトで作成）
    loc = UserLocation.current()
    print(f"[info] location: lat={loc.latitude}, lon={loc.longitude}, "
          f"accuracy={loc.accuracy_m}, updated_at={loc.updated_at}")

    # 期間境界 (JST aware) を作る
    jst = dt_tz(timedelta(hours=9))
    # 開始＝その日の00:00
    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").replace(tzinfo=jst)
    # 終了＝その日の23:00（+23時間して当日最後の正時に合わせる）
    end_dt   = datetime.strptime(END_DATE,   "%Y-%m-%d").replace(tzinfo=jst) + timedelta(hours=23)
    print(f"[info] target: {start_dt.isoformat()} - {end_dt.isoformat()} (JST)")

    # API 呼び出しのパラメータ
    params = {
        "latitude": loc.latitude,                                   # 緯度（DB値）
        "longitude": loc.longitude,                                 # 経度（DB値）
        "hourly": "temperature_2m,surface_pressure,weather_code",   # 欲しい時間別項目
        "timezone": TZ_NAME,                                        # JSTで返してもらう
        "past_days": 7,                                             # 過去7日分も取得
        "forecast_days": 1,                                         # 予報は1日分
    }
    print(f"[info] GET {API_URL}")
    try:
        # タイムアウト30秒でGET。raise_for_status()でHTTPエラーを例外化
        r = requests.get(API_URL, params=params, timeout=30)
        r.raise_for_status()
    except Exception as e:
        # 通信失敗・HTTPエラーはここでまとめて捕捉
        print(f"[err] API error: {e}")
        return 1

    # レスポンスJSONから hourly ブロックを取り出す（無ければ空辞書）
    data = r.json().get("hourly", {})
    times = data.get("time", [])              # 時刻の配列
    temps = data.get("temperature_2m", [])    # 気温の配列
    press = data.get("surface_pressure", [])  # 気圧の配列
    codes = data.get("weather_code", [])      # 天気コードの配列

    print(f"[info] api returned {len(times)} hourly points")

    # 集計用カウンタ
    fetched = 0          # 保存(upsert)した件数
    skipped = 0          # 範囲外・欠損でスキップした件数
    upserts_created = 0  # 新規作成された件数
    upserts_updated = 0  # 更新された件数
    samples_head: list[str] = []  # 先頭サンプル表示用
    samples_tail: list[str] = []  # 末尾サンプル表示用

    # 4つの配列を行ごとにまとめる（時刻・気温・気圧・コードを1組に）
    rows = list(zip(times, temps, press, codes))
    for ts, t, p, c in rows:
        # どれか1つでも欠損(None)ならスキップ
        if t is None or p is None or c is None:
            skipped += 1
            continue
        obs = parse_jst(ts)  # 時刻文字列をJST datetimeへ
        # 取得対象期間の外ならスキップ
        if not (start_dt <= obs <= end_dt):
            skipped += 1
            continue

        # 天気コードを4分類へ縮約
        wc = reduce_weather_code(int(c))
        # observed_at をキーに upsert（あれば更新・なければ作成）
        # update_or_create の戻り値は (オブジェクト, 作成したか)
        _, created = WeatherRecord.objects.update_or_create(
            observed_at=obs,                       # 一意キー
            defaults={                             # 上書き/新規時にセットする値
                "weather_code": wc,
                "temperature_c": round(float(t), 1),  # 小数1桁に丸め
                "pressure_hpa":  round(float(p), 1),
            },
        )
        fetched += 1
        # 新規かどうかでカウンタを振り分け
        if created:
            upserts_created += 1
        else:
            upserts_updated += 1

        # 確認用の1行サンプル文字列
        line = f"{obs.strftime('%m/%d %H:%M')}  code={wc}  t={t}C  p={p}hPa"
        # 先頭3件だけ head に保存
        if len(samples_head) < 3:
            samples_head.append(line)
        # tail は全件入れて、あとで末尾3件に切る
        samples_tail.append(line)

    # 末尾3件だけ残す
    samples_tail = samples_tail[-3:]

    # 結果サマリーを表示
    print(f"[ok]   upsert: {fetched}  (created={upserts_created} / updated={upserts_updated})")
    print(f"[info] skipped(out of range or null): {skipped}")
    print("[info] head samples:")
    for s in samples_head:
        print("       " + s)
    print("[info] tail samples:")
    for s in samples_tail:
        print("       " + s)

    return 0  # 正常終了


# このファイルを直接実行したときだけ main() を動かす
# （他からimportされたときは動かさない、の定番ガード）
if __name__ == "__main__":
    sys.exit(main())  # main()の戻り値をOSの終了コードにする