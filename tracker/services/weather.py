# -*- coding: utf-8 -*-
"""
tracker/services/weather_client.py
ねこのひげ - Open-Meteo APIクライアント（現在の地表気圧取得）

【目的】
気象API「Open-Meteo」から、指定地点の **現在の地表気圧（hPa）** を取得する。
痛み記録と気圧変化の相関を分析するための「気圧センサー代わり」として利用。

【Open-Meteo を採用した理由】
- 無料・APIキー不要（個人開発・MVPに最適）
- HTTPS / JSON / 軽量レスポンス
- 緯度経度を渡すだけで日本国内も問題なくカバー

【設計方針】
- 引数 lat/lon を省略可能にし、未指定時は settings の TOKYO_LAT/TOKYO_LON を採用
  → どこからでも「とりあえず東京の気圧」を取れる安全側のデフォルト
- ネットワーク障害・API側障害・JSON構造変化のいずれが起きても None を返す
  → 呼び出し側で「データなし」として扱えるよう、例外を呑む設計
  （痛み記録の保存自体は気圧が取れなくても続行させたいため）

【注意】
- リクエストはブロッキング（timeout=10秒）。
  Djangoのリクエストスレッド内で直接呼ぶと、API遅延がそのまま画面遅延になる。
  そのため呼び出し側は sync_weather_async() のように非同期化して使う前提。
"""
import requests
from django.conf import settings


# ============================================================
# 定数
# ============================================================
# Open-Meteo の予報API エンドポイント。
# "current" パラメータで「いま」の値だけを取得できる。
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


# ============================================================
# 公開関数
# ============================================================
def get_current_pressure(lat: float | None = None,
                         lon: float | None = None) -> float | None:
    """
    指定地点の現在の地表気圧（hPa）を返す。

    Args:
        lat: 緯度。None の場合は settings.TOKYO_LAT（デフォルト 35.6812）を使用
        lon: 経度。None の場合は settings.TOKYO_LON（デフォルト 139.7671）を使用

    Returns:
        float : 取得成功時の地表気圧（hPa）
        None  : 通信失敗・API異常・JSON構造変化など、何らかの原因で取得できなかった場合

    補足：
        - 戻り値が None のときは「気圧データなし」として扱う想定
          （呼び出し側で記録をスキップする / 既定値で埋める など）
        - 例外は全て握りつぶす（後述の except Exception）。
          痛み記録の入力フローを気象API障害で止めないための割り切り。
    """

    # --------------------------------------------------------
    # 1. 緯度経度のフォールバック
    # --------------------------------------------------------
    # 呼び出し側が lat/lon を指定していなければ settings の値を使う。
    # settings に該当変数が無い場合は東京駅近辺の座標を最終デフォルトに。
    # getattr の第3引数で「settingsにも無い時の保険」を二重に用意している。
    lat = lat if lat is not None else getattr(settings, "TOKYO_LAT", 35.6812)
    lon = lon if lon is not None else getattr(settings, "TOKYO_LON", 139.7671)

    # --------------------------------------------------------
    # 2. APIリクエストパラメータ
    # --------------------------------------------------------
    # - current=surface_pressure : 現時点の地表気圧のみ要求（レスポンス軽量化）
    # - timezone=Asia/Tokyo      : 返却される時刻を日本時間で揃える
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "surface_pressure",
        "timezone": "Asia/Tokyo",
    }

    # --------------------------------------------------------
    # 3. HTTP GET → JSON 解析 → 気圧値の抽出
    # --------------------------------------------------------
    # timeout=10秒：API側の遅延でWebリクエストが詰まるのを防ぐ上限。
    # raise_for_status()：4xx/5xx を例外化（下の except でまとめて捕捉）。
    try:
        r = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        # レスポンス構造の前提：
        #   {"current": {"surface_pressure": 1013.2, ...}, ...}
        # 構造が変わったら KeyError → except 経由で None に倒れる。
        return float(data["current"]["surface_pressure"])

    except Exception:
        # 想定する失敗：
        #   - requests.ConnectionError / Timeout : ネットワーク不調
        #   - requests.HTTPError                : APIが5xx を返した
        #   - KeyError / TypeError              : JSON構造の変化
        #   - ValueError                        : float() 変換失敗
        # いずれも「気圧データなし」と同義として扱う設計。
        # → 呼び出し側のUI/保存処理を止めないことを優先。
        return None