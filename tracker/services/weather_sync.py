# -*- coding: utf-8 -*-
"""
tracker/services/weather_sync.py
ねこのひげ - Webアクセス時に裏で天気データを更新するための共通モジュール。

特徴:
  - バックグラウンドスレッドでAPIを叩くのでページ描画をブロックしない
  - 10分以内に既に実行していたらスキップ(API叩き過ぎ防止)
  - 実測(過去〜現在) と 予報(未来) を is_forecast で区別して保存する ★案B
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone as dt_tz

from django.utils import timezone

from tracker.models import WeatherRecord, UserLocation


# --- 定数 ---------------------------------------------------------------
JST = dt_tz(timedelta(hours=9))                              # 日本時間
API_URL = "https://api.open-meteo.com/v1/forecast"           # Open-Meteo
MIN_INTERVAL = timedelta(minutes=10)                         # 最短同期間隔

# 予報をどこまで先まで保存するか（weather_risk の表示10日=240hに合わせる）
FORECAST_BUFFER_H = 240

# --- 同時実行制御用 -----------------------------------------------------
_LOCK = threading.Lock()         # スロット判定の排他
_LAST_RUN = {"ts": None}         # 直近実行時刻(プロセス内メモリ)
_RUNNING = {"flag": False}       # 走行中フラグ(二重起動防止)


# --- 共通ユーティリティ -------------------------------------------------
def _reduce_weather_code(code: int) -> int:
    """WMOコード→アプリ用4分類(0晴/1晴のち曇/2曇/3雨)"""
    if code == 0:
        return 0
    if code in (1, 2):
        return 1
    if code == 3:
        return 2
    return 3


def _parse_jst(s: str) -> datetime:
    """'YYYY-MM-DDTHH:MM' (naive JST) → aware JST datetime"""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=JST)


# --- 本体処理 -----------------------------------------------------------
def _do_sync() -> None:
    """実際の取得・upsert処理。スレッド内で呼ばれる。例外はログ出力のみ。"""
    try:
        import requests  # ここでimport(未インストールでもアプリ自体は動かす)
    except ImportError:
        print("[weather_sync] requests 未インストールのためスキップ")
        _RUNNING["flag"] = False
        return

    try:
        now = datetime.now(JST)
        today = now.date()

        # 実測の下限：今日を含む直近7日間の先頭(6日前の00:00)
        past_start = datetime.combine(today - timedelta(days=6),
                                      datetime.min.time()).replace(tzinfo=JST)
        # 予報の上限：今から FORECAST_BUFFER_H 時間先
        future_end = now + timedelta(hours=FORECAST_BUFFER_H)

        loc = UserLocation.current()
        params = {
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "hourly": "temperature_2m,surface_pressure,weather_code",
            "timezone": "Asia/Tokyo",
            "past_days": 7,
            # ★forecast_days は「今日0時から数えた日数」。今日の大半は既に過ぎているため、
            #   now+240h(丸10日先)まで埋めるには 10 ではなく 11（今日＋10日）が必要。
            "forecast_days": 11,   # ★10日予報：now+240h(丸10日先)を確実にカバー
        }

        r = requests.get(API_URL, params=params, timeout=20)
        r.raise_for_status()
        data = r.json().get("hourly", {})

        times = data.get("time", [])
        temps = data.get("temperature_2m", [])
        press = data.get("surface_pressure", [])
        codes = data.get("weather_code", [])

        created = updated = skipped = 0
        for ts, t, p, c in zip(times, temps, press, codes):
            if t is None or p is None or c is None:
                skipped += 1
                continue
            obs = _parse_jst(ts)

            # ★案B：時刻で実測/予報を振り分ける
            if past_start <= obs <= now:
                is_forecast = False                 # 過去〜現在 = 実測
            elif now < obs <= future_end:
                is_forecast = True                  # 未来 = 予報
            else:
                skipped += 1                        # 範囲外は捨てる
                continue

            _, was_created = WeatherRecord.objects.update_or_create(
                observed_at=obs,
                defaults={
                    "weather_code": _reduce_weather_code(int(c)),
                    "temperature_c": round(float(t), 1),
                    "pressure_hpa":  round(float(p), 1),
                    "is_forecast":   is_forecast,   # ★案B
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        print(f"[weather_sync] ok: created={created} updated={updated} skipped={skipped}")

    except Exception as e:
        # ページ描画は別スレッドで完了済み。ここでの失敗は致命的ではない。
        print(f"[weather_sync] error: {e}")
    finally:
        _RUNNING["flag"] = False


# --- 公開API ------------------------------------------------------------
def sync_weather_async(force: bool = False) -> bool:
    """バックグラウンドで天気同期を起動する。

    Returns:
        True  : スレッドを起動した
        False : スロットリングまたは走行中でスキップした
    """
    now = timezone.now()
    with _LOCK:
        # 既に別スレッドで走行中なら何もしない
        if _RUNNING["flag"]:
            return False
        # 直近MIN_INTERVAL内に実行済みならスキップ(force=Trueで無視)
        last = _LAST_RUN["ts"]
        if (not force) and last and (now - last) < MIN_INTERVAL:
            return False
        _LAST_RUN["ts"] = now
        _RUNNING["flag"] = True

    t = threading.Thread(target=_do_sync, daemon=True)
    t.start()
    return True


# ============================================================
# 【追記ブロック 1/4】 天気痛リスクの判定ロジック（変更なし）
# ------------------------------------------------------------
# 目的：天気痛リスクの「判定ロジック」を1か所に集約する。
#       views.py はこれを呼ぶだけにして薄く保つ。
# ============================================================

# --- リスク判定のしきい値（医学的知見に基づく。チューニングはここ1か所で） ---
DROP_HIGH_HPA = -4.0   # 6時間で -4hPa 以下の低下 → 高リスク（高感度化: 旧 -8.0）
DROP_MID_HPA  = -2.0   # 6時間で -2〜-4hPa の低下 → 中リスク（高感度化: 旧 -5.0）
RISK_WINDOW_H = 6      # 比較する先読み時間（時間）


def classify_pain_risk(delta_hpa):
    """6時間先との気圧差(hPa)からリスク区分を返す。

    Returns: "high" / "mid" / "low"
    """
    if delta_hpa is None:
        return "low"
    if delta_hpa <= DROP_HIGH_HPA:
        return "high"
    if delta_hpa <= DROP_MID_HPA:
        return "mid"
    return "low"


RISK_LABEL_JP = {"high": "高", "mid": "中", "low": "低"}
RISK_DESC_JP  = {"high": "注意", "mid": "やや高め", "low": "安定"}


def build_risk_timeline(series, step_h=6, horizon_h=48):
    """時系列の気圧から、step_h ごとの未来リスク配列を作る。"""
    if not series:
        return []

    # time -> pressure の簡易ルックアップ（最近傍）
    def pressure_at(target):
        best = min(series, key=lambda r: abs((r["time"] - target).total_seconds()))
        return best["pressure"]

    from datetime import timedelta
    start = series[0]["time"]
    out = []
    h = 0
    while h <= horizon_h:
        t0 = start + timedelta(hours=h)
        # このスロット(step_h時間)内で最も急な6時間降下を代表値にする。
        # step_h=6 は従来どおり t0 の1点のみ（後方互換）。step_h が大きい(日次24h等)
        # ときは6時間刻みで走査して最悪値を採用し、スロット内の急降下を取りこぼさない。
        worst = None
        probe = 0
        stride = RISK_WINDOW_H if step_h > RISK_WINDOW_H else step_h
        while probe < step_h and (h + probe) <= horizon_h:
            _a = t0 + timedelta(hours=probe)
            _b = _a + timedelta(hours=RISK_WINDOW_H)
            _d = round(pressure_at(_b) - pressure_at(_a), 1)
            if worst is None or _d < worst:
                worst = _d
            probe += stride
        delta = worst if worst is not None else 0.0
        risk = classify_pain_risk(delta)
        out.append({
            "time": t0,
            "risk": risk,
            "label": RISK_LABEL_JP[risk],
            "desc": RISK_DESC_JP[risk],
            "delta": delta,
        })
        h += step_h
    return out


def current_pain_risk(series):
    """「今」のリスク（先頭時刻 vs 6時間後）を返す。"""
    tl = build_risk_timeline(series, step_h=RISK_WINDOW_H, horizon_h=RISK_WINDOW_H)
    return tl[0] if tl else {"risk": "low", "label": "低", "desc": "安定", "delta": 0.0}


def build_advice(timeline):
    """タイムラインからLv1ルールベースの猫アドバイス文を組み立てる（LLM不要）。"""
    if not timeline:
        return "今のところ気圧は安定しているにゃ。ゆっくり過ごすにゃ🐾"
    highs = [x for x in timeline if x["risk"] == "high"]
    if highs:
        when = highs[0]["time"].strftime("%m/%d %H時ごろ")
        return (f"{when}に急激な気圧低下が予想されるにゃ。"
                "早めの休息・水分補給や、必要に応じたお薬の準備をしておくと安心にゃ🐾")
    mids = [x for x in timeline if x["risk"] == "mid"]
    if mids:
        return "この先やや気圧が下がる時間帯があるにゃ。無理せず過ごすといいにゃ🐾"
    return "しばらく気圧は安定傾向にゃ。穏やかに過ごせそうにゃ🐾"