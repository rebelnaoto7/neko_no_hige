# -*- coding: utf-8 -*-
"""
tracker/views.py
ねこのひげ - ビュー定義

このモジュールはアプリの全画面のリクエスト処理をまとめたもの。
  - ホーム（猫の吹き出し: 服薬リマインド＋天気アドバイス）
  - 痛み記録の登録・編集・履歴
  - グラフ（データの見える化）
  - リマインド設定
  - 現在地保存API
  - 天気アドバイス専用ページ
"""

# ------------------------------------------------------------
# 標準ライブラリ
# ------------------------------------------------------------
import json                       # 現在地APIのJSONボディをパースするため
import datetime                   # 天気アドバイスの「今日の日付」生成に使用
from datetime import timedelta    # 日時の加減算（前後1時間・7日間など）に使用


# ------------------------------------------------------------
# サードパーティ
# ------------------------------------------------------------
import requests                   # Open-Meteo（気象API）へのHTTPリクエスト用

# ------------------------------------------------------------
# Django 関連
# ------------------------------------------------------------
from django.http import JsonResponse, HttpResponseBadRequest          # APIレスポンス用
from django.shortcuts import render, redirect, get_object_or_404      # 画面描画 / リダイレクト / 取得失敗時404
from django.utils import timezone                                     # タイムゾーン対応の現在時刻取得
from django.views.decorators.http import require_http_methods, require_POST  # HTTPメソッド制限デコレータ

# ------------------------------------------------------------
# 自アプリのモデル / サービス
# ------------------------------------------------------------
from .models import PainRecord, WeatherRecord, ReminderSetting, UserLocation
from .services.weather_sync import sync_weather_async    # 天気データを非同期で取得・更新するサービス
from .services.advice import build_temperature_advice    # 気温→猫アドバイス文を作るルールベース関数

# ★追加：次のリマインダーを計算する専用ロジック
#   - is_active=True のみ対象
#   - 今日の残りが無ければ「明日の最初」へ自動繰越
#   - Asia/Tokyo で時刻比較するためタイムゾーンずれが起きない
from .services.reminder import get_next_reminder

from django.contrib.auth import login as auth_login          # 登録直後に自動ログインさせる
from django.contrib.auth.decorators import login_required   # ★Lv3：ログイン必須化
from django.contrib.auth.forms import UserCreationForm        # Django標準のユーザー作成フォーム
from django.shortcuts import redirect                          # 既に import 済みなら不要

# tracker/views.py
from django.contrib.auth.decorators import login_not_required

from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render

from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render

from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

@login_not_required
def landing(request):
    if request.user.is_authenticated:
        return redirect("tracker:home")
    return render(request, "tracker/landing.html")

@login_not_required
def welcome(request):
    # 既にログイン済みならホームへ素通り
    if request.user.is_authenticated:
        return redirect("tracker:home")
    return render(request, "tracker/welcome.html")

# ============================================================
# サインアップ（自己登録）ビュー
# ・GET : 空の登録フォームを表示
# ・POST: 入力を検証し、OKならユーザー作成＋自動ログイン→ホームへ
# ・Django標準の UserCreationForm を利用（username + password1/2）
# ============================================================
# サインアップは未ログインでアクセスできる必要がある
@login_not_required
def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()              # 新規ユーザーをDBに作成
            auth_login(request, user)       # 作成直後にそのままログイン状態にする
            return redirect("tracker:home") # ホームへ遷移（猫吹き出しが見える）
    else:
        form = UserCreationForm()           # GET時は空フォーム

    return render(request, "registration/signup.html", {"form": form})


# ============================================================
# 定数定義
# ============================================================

# グラフの曜日ラベル（月曜=0 ～ 日曜=6 の順）
WD = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

# 痛みの種類セレクトボックス用の選択肢（value, label）
PAIN_TYPE_CHOICES = [
    ('頭痛', '頭痛'),
    ('腰痛', '腰痛'),
    ('肩こり', '肩こり'),
    ('関節痛', '関節痛'),
    ('だるい', 'だるい'),
    ('めまい', 'めまい'),
    ('吐き気', '吐き気'),
    ('その他', 'その他'),
]

# Open-Meteo の weather_code を簡易ラベルに変換するマップ
# （履歴一覧で天気を文字表示するために使用）
WEATHER_LABEL = {0: '晴', 1: '晴のち曇', 2: '曇', 3: '雨'}

# 現在地が未保存のときに使うデフォルト座標（東京・品川付近）
DEFAULT_LAT = 35.6090
DEFAULT_LON = 139.7300


# ============================================================
# ユーティリティ関数
# ============================================================

def _round_to_hour(dt):
    """
    任意の日時を「正時」に丸める。
    - 30分以上 → 次の時間に切り上げ
    - 30分未満 → 現在の時間に切り下げ
    気圧・気温は1時間単位で取得しているため、痛み記録の時刻に最も近い
    気象データを引くためのキーを作る目的で使う。
    """
    if dt.minute >= 30:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=0, second=0, microsecond=0)


def _nearest_weather(local_dt):
    """
    指定時刻に最も近い WeatherRecord を返す。
    1. まず正時に丸めて完全一致を狙う（高速・正確）
    2. 無ければ ±1時間の範囲で時系列順に最も近いものを返す
    どちらも無ければ None。
    """
    rounded = _round_to_hour(local_dt)

    # ① 正時完全一致を最優先（実測のみ。予報は痛み突き合わせに使わない）
    wr = WeatherRecord.objects.filter(observed_at=rounded, is_forecast=False).first()
    if wr:
        return wr

    # ② フォールバック：前後1時間以内で最初に見つかった実測レコード
    return (WeatherRecord.objects
            .filter(is_forecast=False,
                    observed_at__gte=rounded - timedelta(hours=1),
                    observed_at__lte=rounded + timedelta(hours=1))
            .order_by('observed_at').first())

def _parse_recorded_at(date_str, time_str):
    """
    フォームから送られてくる日付・時刻文字列を、
    タイムゾーン付き(aware)の datetime に変換する。
    - date_str: "YYYY-MM-DD"
    - time_str: "HH:MM" （空文字なら現在時刻を採用）
    パースに失敗した場合は安全側に倒して now() を返す。
    """
    now_local = timezone.localtime()
    try:
        d = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
        if time_str:
            t = timezone.datetime.strptime(time_str, "%H:%M").time()
        else:
            # 時刻未指定 → 現在時刻（マイクロ秒は不要なので削る）
            t = now_local.time().replace(microsecond=0)
        naive = timezone.datetime.combine(d, t)
        # ローカルTZを付与して aware 化（DB保存のため必須）
        return timezone.make_aware(naive, now_local.tzinfo)
    except (ValueError, TypeError):
        # 不正入力時は現在時刻にフォールバック
        return timezone.now()


def _fetch_today_advice(loc):
    """
    今日の最高/最低気温を Open-Meteo から取得し、
    猫アドバイス辞書（build_temperature_advice の戻り値）を返す共通関数。

    home と weather_advice の両方から呼ばれる（処理の重複を避けるため切り出し）。
    - loc: UserLocation インスタンス（None可）
    - 取得失敗・データ無しのときは temp が None のまま渡るので、
      advice 側で「データなし」表示になる（例外で画面を壊さない設計）。
    """
    # 現在地が無ければ東京・品川付近をデフォルト使用
    lat = getattr(loc, "latitude", None) or DEFAULT_LAT
    lon = getattr(loc, "longitude", None) or DEFAULT_LON

    temp_max = temp_min = None
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "Asia/Tokyo",
                "forecast_days": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        daily = resp.json().get("daily", {})
        if daily.get("temperature_2m_max"):
            temp_max = daily["temperature_2m_max"][0]
        if daily.get("temperature_2m_min"):
            temp_min = daily["temperature_2m_min"][0]
    except Exception:
        # 通信失敗・APIエラー時は None のまま（テンプレートで「データなし」表示）
        pass

    return build_temperature_advice(temp_max, temp_min)


# ============================================================
# ホーム画面
# ============================================================
@login_required          # ★Lv3：ホームもログイン必須化
def home(request):
    """
    トップページ。
    - 開くたびに天気データの同期をバックグラウンドでキック
    - 次に来るアクティブなリマインドを1件取得（猫の吹き出し1段目）
    - 今日の天気アドバイスを生成（猫の吹き出し2段目）
    - 保存済みの現在地（緯度経度）をテンプレに渡す
    """
    sync_weather_async()  # 非同期で気象データを更新（描画はブロックしない）

    now = timezone.localtime()

    # ▼ 変更：次のリマインドの計算を services/reminder.py に切り出した
    #   旧ロジックは「is_active=True で reminder_time 最小」を返すだけで、
    #   現在時刻より過去のものでも先頭に出てしまうバグがあった。
    #   新ロジックは下記を保証する：
    #     - 現在時刻(Asia/Tokyo)より後で最も近い時刻を返す
    #     - 今日の残りが無ければ「明日の最初」を返す
    #     - 1件も無ければ None
    #   戻り値は dict（time / medicine_name / is_tomorrow / label / minutes_until）
    
    # ログイン時のみ吹き出し用データを計算（未ログインは None → テンプレ側で section ごと非表示）
    if request.user.is_authenticated:
        # ★Lv3：本人の設定だけで次リマインダーを計算（user を渡す）
        next_reminder = get_next_reminder(now, user=request.user)
        loc = UserLocation.current()                    # 現在地
        advice = _fetch_today_advice(loc)               # 天気アドバイス（API呼び出し）
    else:
        next_reminder = None
        loc = UserLocation.current()                    # 下の user_lat 等で使うので取得は維持
        advice = None

    # ------------------------------------------------------------
    # 今日の天気アイコン用の weather_code
    #   ・吹き出し2段目「きょうのお天気」のアイコンを、見える化(charts)ページの
    #     週間天気の“今日”セルと必ず一致させるための値。
    #   ・charts の当日セルと完全に同じ算出方法にすることで齟齬をなくす：
    #       - その日の実測(is_forecast=False)の最後のレコードを採用
    #       - レコードが無い日は曇(2)にフォールバック（charts と同一）
    #   ・アイコン分岐は home.html 側で weather_code に応じて同じSVGを描画する。
    # ------------------------------------------------------------
    today = timezone.localdate()
    today_wr = (WeatherRecord.objects
                .filter(observed_at__date=today, is_forecast=False)
                .order_by('observed_at').last())
    today_weather_code = getattr(today_wr, 'weather_code', 2)

    return render(request, 'tracker/home.html', {
        'now': now,
        'next_reminder': next_reminder,   # dict or None（テンプレ側で属性アクセス）
        'advice': advice,                 # 吹き出し2段目の天気アドバイス
        'today_weather_code': today_weather_code,  # きょうのお天気アイコン分岐用（charts と同一ソース）
        'user_lat': loc.latitude,
        'user_lon': loc.longitude,
        'loc_updated_at': loc.updated_at,
    })


# ============================================================
# 痛み記録 入力（新規作成）
# ============================================================
@login_required
@require_http_methods(["GET", "POST"])
def pain_create(request):
    """
    新規の痛み記録を作成する画面。
    - GET : 入力フォームを表示（現在の気圧も参考表示）
    - POST: 入力内容を保存して履歴ページへリダイレクト
    時刻は丸めて気象データと突き合わせやすくする方針のため、
    日付のみフォームから取得し、時刻は内部で補完している。
    """
    if request.method == "POST":
        # --- 入力値の取り出し（防御的に strip / 範囲制限） ---
        date_str = request.POST.get('recorded_date', '').strip()
        recorded_at = _parse_recorded_at(date_str, '')  # 時刻は空 → 現在時刻

        level = int(request.POST.get('level', 1))             # 1=痛くない / 2=ちょっと痛い / 3=すごく痛い
        pain_type = request.POST.get('pain_type', '').strip()
        memo = request.POST.get('memo', '').strip()[:140]     # メモは140文字でカット

        # ============================================
        # ✅ A案：その他選択時のみ自由記述を採用
        # ============================================
        if pain_type == 'その他':
            other = request.POST.get('pain_type_other', '').strip()[:50]
            if other:
                pain_type = other

        # --- DB保存 ---
        PainRecord.objects.create(
            recorded_at=recorded_at,
            level=max(1, min(3, level)),
            body_part='',
            pain_type=pain_type,
            memo=memo,
            user=request.user,   # ★Lv3：作成者（ログイン中ユーザー）を持ち主として記録
        )
        return redirect('tracker:pain_history')


        # --- DB保存 ---
        PainRecord.objects.create(
            recorded_at=recorded_at,
            level=max(1, min(3, level)),  # 範囲外の値が来ても1～3にクリップ
            body_part='',                 # 現UIでは部位は使わないので空
            pain_type=pain_type,
            memo=memo,
        )
        return redirect('tracker:pain_history')

    # --- GET: フォーム描画 ---
    now = timezone.localtime()

    # ★見える化ページの猫クリックから来た場合、対象日を初期表示に反映（?date=YYYY-MM-DD）
    #   ・不正・未指定なら今日にフォールバック（安全側）
    prefill_date_obj = now.date()
    date_param = request.GET.get('date', '').strip()
    if date_param:
        try:
            prefill_date_obj = timezone.datetime.strptime(date_param, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            prefill_date_obj = now.date()

    # 参考気圧：対象日が今日なら「現在」、過去日ならその日の正午に最も近い実測を表示
    #   （readonly の参考欄。実際の突合気圧は表示時に recorded_at で再計算される）
    if prefill_date_obj == now.date():
        ref_dt = now
    else:
        ref_naive = timezone.datetime.combine(
            prefill_date_obj, timezone.datetime.min.time().replace(hour=12))
        ref_dt = timezone.make_aware(ref_naive, now.tzinfo)
    wr = _nearest_weather(ref_dt)  # 参考表示用の気圧

    return render(request, 'tracker/pain_create.html', {
        'today': prefill_date_obj.isoformat(),
        'current_pressure': wr.pressure_hpa if wr else None,
        'pain_type_choices': PAIN_TYPE_CHOICES,
    })


# ============================================================
# 痛み記録 編集（更新 / 削除）
# ============================================================
@login_required
@require_http_methods(["GET", "POST"])
def pain_edit(request, pk):
    """
    既存の PainRecord を編集または削除する。
    - 削除アクションが来た場合は他の処理に優先して削除する
    - 更新時は日付＋時刻を別々に受け取って aware datetime に再構成
    - body_part は現UIで編集できないため、既存値を保ったまま温存
    """
    # ★Lv3：pk一致 かつ 本人の記録 のときだけ取得。他人の記録は404で弾く（編集・削除の両方を防御）
    record = get_object_or_404(PainRecord, pk=pk, user=request.user)
    
    if request.method == "POST":
        # --- 削除アクション（最優先で処理） ---
        if request.POST.get('action') == 'delete':
            record.delete()
            return redirect('tracker:pain_history')

        # --- 更新処理 ---
        date_str = request.POST.get('recorded_date', '').strip()
        time_str = request.POST.get('recorded_time', '').strip()
        record.recorded_at = _parse_recorded_at(date_str, time_str)

        level = int(request.POST.get('level', record.level))
        record.level = max(1, min(3, level))  # 1～3にクリップ
        record.pain_type = request.POST.get('pain_type', '').strip()
                
        # A案：「その他」選択時のみ自由記述を採用
        if record.pain_type == 'その他':
            other_text = request.POST.get('pain_type_other', '').strip()[:50]
            if other_text:
                record.pain_type = other_text

        record.memo = request.POST.get('memo', '').strip()[:140]
        # body_part は編集UI非搭載のため、ここでは触らず既存値を保持
        record.save()
        return redirect('tracker:pain_history')

    # --- GET: 既存値をフォームに流し込んで描画 ---
    local = timezone.localtime(record.recorded_at)
    wr = _nearest_weather(local)
    return render(request, 'tracker/pain_edit.html', {
        'record': record,
        'recorded_date': local.date().isoformat(),  # <input type="date"> 用
        'recorded_time': local.strftime('%H:%M'),   # <input type="time"> 用
        'current_pressure': wr.pressure_hpa if wr else None,
        'pain_type_choices': PAIN_TYPE_CHOICES,
    })


# ============================================================
# 痛み記録 履歴一覧
# ============================================================
@login_required
def pain_history(request):
    """
    最新200件の痛み記録を、対応する天気・気圧と突き合わせて一覧表示する。
    各行に編集ページへ飛ぶための pk を渡している点に注意。
    """
    # ★Lv3：ログイン中ユーザー本人の記録だけに限定（他人の痛みは見せない）
    records = PainRecord.objects.filter(user=request.user).order_by('-recorded_at')[:200]
    rows = []
    for r in records:
        local = timezone.localtime(r.recorded_at)
        wr = _nearest_weather(local)   # 各記録に最も近い気象データ
        rows.append({
            'pk': r.pk,                                                      # 編集リンク用ID
            'recorded_at': local,
            'weather': WEATHER_LABEL.get(wr.weather_code, '—') if wr else '—',
            'pressure_hpa': wr.pressure_hpa if wr else None,
            'level_label': r.get_level_display(),                            # 1/2/3 → 表示名
            'pain_type': r.pain_type or '—',
            'body_part': r.body_part or '—',
            'memo': r.memo or '',
        })

    return render(request, 'tracker/pain_history.html', {'rows': rows})


# ============================================================
# データの見える化（過去7日間のグラフ）
# ============================================================
@login_required
def charts(request):
    """
    今日を含む直近7日間について、日ごとに
    「天気・気温・気圧・痛みレベル」を1日1点に集約してテンプレへ渡す。
    各日とも「その日最後のレコード」を採用（最新値ベース）。

    データが無い日は None を渡し、グラフ側で
    ・気圧線を途切れさせる（spanGaps:false）
    ・痛み猫を描かない
    ことで「欠測」と「実測」を視覚的に区別する。
    """
    sync_weather_async()# 開くたびに最新の気象データを反映

    today = timezone.localdate()
    start = today - timedelta(days=6)  # 7日間 = 今日 + 過去6日

    # 週間の最高/最低気温を Open-Meteo から取得（過去6日＋今日）
    # past_days:6 で過去分も daily で返る。timezone:Asia/Tokyo で日界をJSTに固定
    daily_max, daily_min = {}, {}
    try:
        loc = UserLocation.current()
        lat = getattr(loc, "latitude", None) or DEFAULT_LAT
        lon = getattr(loc, "longitude", None) or DEFAULT_LON
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "Asia/Tokyo",
                "past_days": 6,      # 過去6日分も取得
                "forecast_days": 1,  # 今日
            },
            timeout=10,
        )
        resp.raise_for_status()
        dj = resp.json().get("daily", {})
        # time は "YYYY-MM-DD" 文字列。d.isoformat() と一致するのでキーに使う
        for t, mx, mn in zip(dj.get("time", []),
                             dj.get("temperature_2m_max", []),
                             dj.get("temperature_2m_min", [])):
            daily_max[t] = mx
            daily_min[t] = mn
    except Exception:
        pass  # 失敗時は空dict → テンプレで「—」フォールバック

    # ============================================================
    # ★整合性改善：痛み予報ページと同一基準の「気圧の急降下」リスクを日別に算出
    #   ・痛み予報と同じ classify_pain_risk（Δ6h ベース）を単一の真実として流用
    #   ・各日の「最大6時間降下(hPa)」を hourly データから求めて区分する
    #   ・実測＋予報を先読みに使う（当日夜→翌朝の降下も拾えるように）
    # ============================================================
    from .services.weather_sync import classify_pain_risk, RISK_WINDOW_H

    # 時間毎の気圧マップ（ローカル時刻 "YYYY-MM-DD HH" をキーに、実測＋予報）
    hourly_p = {}
    for _r in (WeatherRecord.objects
               .filter(observed_at__date__gte=start,
                       observed_at__date__lte=today + timedelta(days=1),
                       pressure_hpa__isnull=False)
               .order_by('observed_at')):
        _k = timezone.localtime(_r.observed_at).strftime('%Y-%m-%d %H')
        hourly_p[_k] = _r.pressure_hpa

    def _day_drop_risk(day):
        """その日の最大6時間降下(hPa)と、痛み予報と同一基準のリスク区分を返す。"""
        worst = None
        base = datetime.datetime.combine(day, datetime.time())
        for _h in range(24):
            t0 = base + timedelta(hours=_h)
            t6 = t0 + timedelta(hours=RISK_WINDOW_H)
            p0 = hourly_p.get(t0.strftime('%Y-%m-%d %H'))
            p6 = hourly_p.get(t6.strftime('%Y-%m-%d %H'))
            if p0 is None or p6 is None:
                continue
            delta = round(p6 - p0, 1)
            if worst is None or delta < worst:
                worst = delta
        return classify_pain_risk(worst), worst

    week = []
    for i in range(7):
        d = start + timedelta(days=i)

        # その日の最後の気象データ（実測のみ。予報は週間集計に混ぜない）
        wr = (WeatherRecord.objects.filter(observed_at__date=d, is_forecast=False) # ← user= を足さない！
              .order_by('observed_at').last())

        # その日の最後の痛み記録（★Lv3：本人の記録だけで集計）
        pr = (PainRecord.objects.filter(user=request.user, recorded_at__date=d)
              .order_by('recorded_at').last())

        day_risk, day_drop = _day_drop_risk(d)

        # ★ツールチップ増強：痛み記録の「詳細」を用意（実記録がある日だけ中身を持たせる）
        #   グラフの描画ロジック（pain_level）はそのまま。ここは表示用の付加情報のみを足す。
        #   種類・部位・メモ・記録時刻はモデルに既にある値で、これまで未活用だった。
        if pr:
            pr_local = timezone.localtime(pr.recorded_at)
            pr_wr = _nearest_weather(pr_local)   # 記録時刻に最も近い実測気圧（痛み↔気圧の突合）
            pain_extra = {
                'has_pain': True,
                'pain_level_label': pr.get_level_display(),   # 痛くない/ちょっと痛い/すごく痛い
                'pain_type': pr.pain_type or '',
                'body_part': pr.body_part or '',
                'memo': pr.memo or '',
                'pain_time': pr_local.strftime('%H:%M'),
                'pain_pressure': (round(pr_wr.pressure_hpa, 1)
                                  if (pr_wr and pr_wr.pressure_hpa is not None) else None),
            }
        else:
            # 記録が無い日：表示は「記録なし」。気象コンテキストだけツールチップに出す。
            pain_extra = {
                'has_pain': False, 'pain_level_label': '', 'pain_type': '',
                'body_part': '', 'memo': '', 'pain_time': '', 'pain_pressure': None,
            }

        week.append({
            'date_label': f"{d.month}/{d.day}",
            'dow': WD[d.weekday()],
            # ★見える化の猫クリック→その日の記録を編集/新規作成へ遷移するための情報
            'date_iso': d.isoformat(),        # その日（YYYY-MM-DD）＝新規作成のプリフィル日付に使う
            'pk': pr.pk if pr else None,      # 記録があれば編集用のpk、無ければ None（→その日付で新規作成）
            # 天気アイコン分岐用。欠測時は曇(2)を仮表示（テーブルが崩れないため既定維持）
            'weather_code': getattr(wr, 'weather_code', 2),
            # ツールチップ表示用の天気ラベル（実測が無い日は「—」＝仮表示しない）
            'weather_label': WEATHER_LABEL.get(wr.weather_code, '—') if wr else '—',
            # 気温は Open-Meteo の週間 daily から取得（DBの代表値ではなくAPI最新の最高/最低）
            'temp_max': round(daily_max[d.isoformat()]) if daily_max.get(d.isoformat()) is not None else None,
            'temp_min': round(daily_min[d.isoformat()]) if daily_min.get(d.isoformat()) is not None else None,
            # 痛み記録が無い日は「痛くない(Lv1)」として扱う（入力忘れ＝痛みなしと解釈）
            'pain_level': pr.level if pr else 1,
            # 気圧は欠測なら None のまま（spanGaps:false で線を繋がない＝捏造防止）
            'pressure_hpa': wr.pressure_hpa if (wr and wr.pressure_hpa is not None) else None,
            # ★痛み予報と同一基準の急降下リスク（'low'/'mid'/'high'）と当日最大6h降下
            'risk': day_risk,
            'max_drop': day_drop,
            # ★ツールチップ用の痛み詳細（has_pain / level_label / type / body_part / memo / time / pressure）
            **pain_extra,
        })

    # 観測地点情報（try失敗でも必ず値を持たせる）
    loc = UserLocation.current()
    view_lat = getattr(loc, 'latitude', None) or DEFAULT_LAT
    view_lon = getattr(loc, 'longitude', None) or DEFAULT_LON

    return render(request, 'tracker/charts.html', {
        'week': week,
        'loc_lat': view_lat,
        'loc_lon': view_lon,
        'loc_updated': getattr(loc, 'updated_at', None),
    })


@require_POST
def update_location(request):
    """
    ブラウザの Geolocation で取得した現在地を保存し、天気を再取得する。
    charts.html の「現在地を取得して更新」ボタンから
    fetch(POST, JSON) で呼ばれ、結果を JSON で返す。

    受信 JSON: { "latitude": float, "longitude": float, "accuracy": float|None }
    返却 JSON: { "ok": bool, "latitude":.., "longitude":.., "updated_at":.., ("error":..) }
    """
    # --- 入力パース ---
    try:
        data = json.loads(request.body)
        lat = float(data["latitude"])
        lon = float(data["longitude"])
        acc = data.get("accuracy")
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "座標が不正です"}, status=400)

    # --- 妥当性チェック（地球上の範囲内か） ---
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return JsonResponse({"ok": False, "error": "座標が範囲外です"}, status=400)

    # --- UserLocation（pk=1 固定）を更新 ---
    loc = UserLocation.current()
    loc.latitude = lat
    loc.longitude = lon
    if acc is not None:
        try:
            loc.accuracy_m = float(acc)
        except (ValueError, TypeError):
            pass
    loc.save()

    # --- 新しい現在地で天気を強制再取得（失敗しても位置保存は成功扱い） ---
    try:
        sync_weather_async(force=True)
    except Exception:
        pass

    return JsonResponse({
        "ok": True,
        "latitude": lat,
        "longitude": lon,
        "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
    })


# ============================================================
# リマインド設定
# ============================================================
@login_required     # ★Lv3：先にログイン判定
@require_http_methods(["GET", "POST"])
def reminder(request):
    """
    薬リマインダーの一覧・新規作成・削除。
    1画面で全てを扱う簡易UI。
    - POST に delete_id が含まれていれば削除を優先
    - そうでなければ新規作成
    - GET は時刻順の一覧を表示
    """
    if request.method == "POST":
        # --- 削除 ---
        delete_id = request.POST.get('delete_id')
        if delete_id:
            # ★Lv3：本人の設定だけ削除（pkだけだと他人のリマインダーを消せる穴になる）
            ReminderSetting.objects.filter(pk=delete_id, user=request.user).delete()
            return redirect('tracker:reminder')

        # --- 新規作成 ---
        reminder_time = request.POST.get('reminder_time')
        medicine_name = request.POST.get('medicine_name', '').strip()
        # チェックボックスは未指定だと値が来ないので 'on' で判定
        is_active = request.POST.get('is_active', 'on') == 'on'

        # 時刻と薬名の両方が揃っているときだけ作成
        if reminder_time and medicine_name:
             ReminderSetting.objects.create(
                reminder_time=reminder_time,
                medicine_name=medicine_name,
                is_active=is_active,
                user=request.user,   # ★Lv3：作成者を持ち主として記録
            )
        return redirect('tracker:reminder')

    # --- GET: 時刻順に一覧表示 ---
    # ★Lv3：本人のリマインダーだけ一覧表示
    reminders = ReminderSetting.objects.filter(user=request.user).order_by('reminder_time')
    return render(request, 'tracker/reminder.html', {'reminders': reminders})


# ============================================================
# 現在地保存 API（ブラウザ Geolocation → DB保存）
# ============================================================
@require_POST
def api_location_update(request):
    """
    フロントの Geolocation API から POST される JSON を受け取り、
    UserLocation（単一レコード運用）を更新する。
    天気取得の緯度経度として後段で利用される。
    リクエストボディ例:
        { "lat": 35.63, "lon": 139.74, "accuracy": 12.5 }
    """
    # --- ペイロードのパースと型変換 ---
    try:
        payload = json.loads(request.body.decode('utf-8'))
        lat = float(payload['lat'])
        lon = float(payload['lon'])
        acc = payload.get('accuracy')
        acc = float(acc) if acc is not None else None
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        # JSONが壊れている / 必須キーが無い / 数値化できない 等 → 400
        return HttpResponseBadRequest(f"invalid payload: {e}")

    # --- 値の妥当性チェック（地球上の座標範囲） ---
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return HttpResponseBadRequest("lat/lon out of range")

    # --- 保存（単一レコード運用なので current() を更新） ---
    loc = UserLocation.current()
    loc.latitude = lat
    loc.longitude = lon
    loc.accuracy_m = acc
    loc.save()

    # --- 成功レスポンス（フロントで即時表示更新できるよう値を返す） ---
    return JsonResponse({
        'ok': True,
        'lat': loc.latitude,
        'lon': loc.longitude,
        'accuracy_m': loc.accuracy_m,
        'updated_at': loc.updated_at.isoformat(),
    })

# ============================================================
# 【追記ブロック 2/4】 tracker/views.py に追加
# ------------------------------------------------------------
# 目的：weather_risk ページ用のビュー。判定は weather_sync に委譲し、
#       ここは「実測＋予報を連結して JSON でテンプレへ渡すだけ」に薄く保つ。
# 前提：weather_sync.py に追記ブロック1/4を入れてあること。
# 注意：既存の import と重複しないように。既にある行は再定義しない（引き継ぎ§4-7）。
# ============================================================

import json
from datetime import timedelta
from django.shortcuts import render
from django.utils import timezone

# 既存の import 群に無ければ追加：
from .services import weather_sync
from .models import WeatherRecord, UserLocation   # プロジェクトの実名に合わせる


def weather_risk(request):
    """気圧の推移と天気痛リスク画面。

    データ構成:
      - 過去(実測)の WeatherRecord
      - 未来(予報)の気圧（Open-Meteo forecast。weather_sync 側で取得・保存する想定）
      を時刻順に連結し、splitIndex(=現在) を境に実線/点線を切り替える。
    """
    now = timezone.now()

    # --- 実測：直近48時間 ---
    past_qs = (WeatherRecord.objects
               .filter(observed_at__lte=now, observed_at__gte=now - timedelta(hours=48))
               .order_by("observed_at"))

    # --- 予報：未来48時間 ---
    #  ※ 予報を別テーブル(例: is_forecast=True)で持つ設計を推奨。
    #    まだ無ければ weather_sync に「予報取得→保存」を実装してから差し替える。
    future_qs = (WeatherRecord.objects
                 .filter(observed_at__gt=now, observed_at__lte=now + timedelta(hours=240))
                 .order_by("observed_at"))

    def to_point(rec):
        return {"time": rec.observed_at, "pressure": float(rec.pressure_hpa)}

    past = [to_point(r) for r in past_qs]
    future = [to_point(r) for r in future_qs]

    # 連結（実測 → 予報）。splitIndex は実測の最後 = 「現在」
    combined = past + future
    split_index = max(len(past) - 1, 0)

    labels = [p["time"].strftime("%m/%d %H:%M") for p in combined]
    pressures = [round(p["pressure"], 1) for p in combined]

    # ★ツールチップ増強：各点の「6時間後までの気圧変化(Δ)」と「気圧リスク」を、
    #   痛み予報・見える化と同一の classify_pain_risk（Δ6h・閾値 -4/-2）で算出する。
    #   ・pressures は1時間刻みなので i+RISK_WINDOW_H が「6時間後」に一致する
    #   ・系列末尾（先の点が無い所）は Δ・risk とも None（ツールチップで非表示）
    #   ・この risks/deltas を帯ゾーン(buildZones)とツールチップの“単一の真実”にする
    _win = weather_sync.RISK_WINDOW_H
    _n = len(pressures)
    deltas, risks = [], []
    for _i in range(_n):
        if _i + _win < _n and pressures[_i] is not None and pressures[_i + _win] is not None:
            _d = round(pressures[_i + _win] - pressures[_i], 1)
            deltas.append(_d)
            risks.append(weather_sync.classify_pain_risk(_d))
        else:
            deltas.append(None)
            risks.append(None)

    # ツールチップ見出し用の日本語日時（例: 7月9日(水) 14:00）
    _JP_DOW = ['月', '火', '水', '木', '金', '土', '日']
    tip_times = [
        f"{p['time'].month}月{p['time'].day}日({_JP_DOW[p['time'].weekday()]}) {p['time']:%H:%M}"
        for p in combined
    ]

    # リスク：現在以降の系列（＝予報含む今の点から）で判定
    series_for_risk = combined[split_index:]
    current = weather_sync.current_pain_risk(series_for_risk)
    timeline = weather_sync.build_risk_timeline(series_for_risk, step_h=24, horizon_h=240)
    advice = weather_sync.build_advice(timeline)

    # タイムラインは datetime を文字列化してから渡す
    timeline_json = [{
        "time": x["time"].strftime("%m/%d\n%H:%M"),
        "risk": x["risk"], "label": x["label"], "desc": x["desc"], "delta": x["delta"],
    } for x in timeline]

    context = {
        # ★json_script が自前でエンコードするので、ここでは dict/list を「生のまま」渡す
        #   （json.dumps で文字列化すると二重エンコードになり、
        #    JSON.parse の結果がオブジェクトでなく文字列になって描画が壊れる）
        "chart_data": {
            "labels": labels,
            "pressures": pressures,
            "splitIndex": split_index,
            # ★ツールチップ＆帯ゾーン用（サーバ側で一元算出＝単一の真実）
            "deltas": deltas,       # 各点の6時間後までのΔ(hPa)。末尾は null
            "risks": risks,         # classify_pain_risk による 'low'/'mid'/'high'。末尾は null
            "tipTimes": tip_times,  # 日本語日時（例: 7月9日(水) 14:00）
        },
        "timeline": timeline_json,     # list のまま渡す
        "current_label": current["label"],
        "current_desc": current["desc"],
        "current_risk": current["risk"],
        "advice": advice,
        "current_pressure": pressures[split_index] if pressures else None,
    }
    return render(request, "tracker/weather_risk.html", context)