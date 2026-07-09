# -*- coding: utf-8 -*-
"""
tracker/admin.py
ねこのひげ - Django管理画面（admin）設定

`python manage.py createsuperuser` で作成した管理者ユーザでログインすると、
/admin/ から各モデルのレコードをブラウザ上でCRUDできる。

【方針】
- list_display : 一覧画面で列として見せたい項目（運用で頻繁に確認するもの）
- list_filter  : 右サイドの絞り込みUIに出したい項目（カテゴリ系のフィールド）
- 各モデルは `@admin.register(...)` デコレータで登録（admin.site.register より宣言的）
"""
from django.contrib import admin
from .models import (
    PainRecord,
    MedicationRecord,
    WeatherRecord,
    ReminderSetting,
)


# ============================================================
# 痛み記録
# ============================================================
@admin.register(PainRecord)
class PainRecordAdmin(admin.ModelAdmin):
    """
    痛み記録の管理画面。
    日々の入力データの確認・修正・削除を運用者がブラウザから行う用途。
    """

    # 一覧画面に表示する列（左から順）
    # - recorded_at : いつ記録したか（時系列で並べたいので最左）
    # - pain_type   : 痛みの種類（頭痛/腰痛など）
    # - body_part   : 部位（現UIでは未使用だが将来用に表示）
    # - level       : 痛みのレベル
    # - memo        : 補足メモ
    list_display = ("recorded_at", "pain_type", "body_part", "level", "memo")

    # 右サイドのフィルタUI：種類や部位での絞り込みが多いので採用
    list_filter = ("pain_type", "body_part")


# ============================================================
# 服薬記録
# ============================================================
@admin.register(MedicationRecord)
class MedicationRecordAdmin(admin.ModelAdmin):
    """
    服薬記録の管理画面。
    いつ・何の薬を飲んだかを一覧で確認できる。
    """

    # 一覧表示：日時と薬名のみのシンプル構成
    list_display = ("taken_at", "name")


# ============================================================
# 気象記録（Open-Meteo等から取得した1時間ごとのデータ）
# ============================================================
@admin.register(WeatherRecord)
class WeatherRecordAdmin(admin.ModelAdmin):
    """
    気象データの管理画面。
    痛み記録との突き合わせに使うデータなので、
    観測時刻と主要な気象指標を一覧で見られるようにしている。
    """

    # 一覧表示：観測時刻 + 天気コード + 気温 + 気圧
    # （痛みとの相関を運用者が目視チェックするのに最低限必要なカラム）
    list_display = ("observed_at", "weather_code", "temperature_c", "pressure_hpa")


# ============================================================
# 薬リマインダー設定
# ============================================================
@admin.register(ReminderSetting)
class ReminderSettingAdmin(admin.ModelAdmin):
    """
    薬リマインダー設定の管理画面。
    ユーザが画面から操作する想定だが、運用上の確認・無効化用に admin にも登録。
    """

    # 一覧表示：時刻 / 薬名 / 有効フラグ
    # is_active を表示しておくことで、無効化済みの設定もパッと見で判別できる
    list_display = ("reminder_time", "medicine_name", "is_active")