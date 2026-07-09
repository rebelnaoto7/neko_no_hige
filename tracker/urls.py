# -*- coding: utf-8 -*-
"""
tracker/urls.py
ねこのひげ - URLルーティング

このモジュールは tracker アプリ内の全URLパターンを定義する。
- 画面系（home / pain_* / charts / reminder）はHTMLを返す
- API系（api_*）はJSONを返す

テンプレートやリダイレクトからは `tracker:<name>` という形で参照する。
例) {% url 'tracker:pain_history' %}  →  /pain/history/
"""
from django.urls import path
from . import views

# ------------------------------------------------------------
# アプリ名前空間
# ------------------------------------------------------------
# `app_name` を設定することで、name='home' などの識別子を
# 'tracker:home' のように名前空間付きで参照できるようになる。
# 他アプリと name が衝突しても安全。
app_name = 'tracker'


# ------------------------------------------------------------
# URLパターン定義
# ------------------------------------------------------------
# path('URLパス', ビュー関数, name='テンプレ等から参照する識別子')
#
# 並び順は「画面系 → API系」の順にまとめている。
# 画面系の中ではユーザー導線（ホーム → 記録 → 履歴/編集 → 可視化 → 設定）の
# 順番で並べることで、後から読んだときに機能の全体像を追いやすくしている。
urlpatterns = [
    # ============================================================
    # 画面系（HTMLを返す）
    # ============================================================

    path("landing/", views.landing, name="landing"),


    # トップページ：猫の表示・次のリマインド・現在地の取得など
    # URL : /
    path('',                      views.home,                name='home'),

    # 痛み記録の新規入力フォーム
    # URL : /pain/
    path('pain/',                 views.pain_create,         name='pain_create'),

    # 痛み記録の履歴一覧（直近200件 + 天気/気圧の突き合わせ表示）
    # URL : /pain/history/
    path('pain/history/',         views.pain_history,        name='pain_history'),

    # 痛み記録の編集 / 削除（<pk> はPainRecordの主キー）
    # URL 例 : /pain/12/edit/
    path('pain/<int:pk>/edit/',   views.pain_edit,           name='pain_edit'),

    # 直近7日間の天気・気温・気圧・痛みレベルをグラフ表示
    # URL : /charts/
    path('charts/',               views.charts,              name='charts'),

    # 薬リマインダーの一覧 / 追加 / 削除
    # URL : /reminder/
    path('reminder/',             views.reminder,            name='reminder'),

    # ============================================================
    # API（JSONを返す）
    # ============================================================

    # 現在地（緯度経度）保存API。
    # フロントの Geolocation API から POST されるJSONを受け取り、
    # UserLocation を更新する。GETは受け付けない（@require_POST）。
    # URL : /api/location/
    path('api/location/',         views.api_location_update, name='api_location_update'),
    path("signup/", views.signup, name="signup"),
    path('update-location/', views.update_location, name='update_location'),
    path("weather-risk/", views.weather_risk, name="weather_risk"),
]
