# -*- coding: utf-8 -*-
"""
tracker/models.py
ねこのひげ - データモデル定義

このファイルの役割:
  DBに保存するテーブルの設計図。1クラス=1テーブル、1変数=1カラム。
  変更したら必ず makemigrations → migrate でDBへ反映する。
"""
# Djangoのモデル機能(テーブルの土台)を読み込む
from django.db import models
from django.conf import settings    # ★追加：AUTH_USER_MODEL を参照するため


class PainRecord(models.Model):
    """痛み記録（1回の痛みにつき1行）"""

    # ★Lv3追加：この痛み記録の持ち主。null許可で既存行を救済してから backfill する
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="ユーザー",
    )

    # 痛みの強さの選択肢。(DB保存値, 画面表示ラベル) のペア。
    LEVEL_CHOICES = [
        (1, "痛くない"),
        (2, "ちょっと痛い"),
        (3, "すごく痛い"),
    ]
    # 痛みを記録した日時
    recorded_at = models.DateTimeField("記録日時")
    # 痛み度。PositiveSmallIntegerField=小さな正の整数専用(0以上)。初期値1。
    level = models.PositiveSmallIntegerField("痛み度", choices=LEVEL_CHOICES, default=1)
    # 部位(例:頭)。空欄も許可(blank=True)
    body_part = models.CharField("部位", max_length=50, blank=True)
    # 痛みの種類(例:ズキズキ)。空欄も許可
    pain_type = models.CharField("痛みの種類", max_length=50, blank=True)
    # 自由メモ。最大140文字。空欄も許可
    memo = models.CharField("メモ", max_length=140, blank=True)

    class Meta:
        # 一覧の並び順。「-」付きで新しい順(降順)
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        # 管理画面などでの1行の見た目。例: [2026-06-05 14:00] L3 ズキズキ
        return f"[{self.recorded_at:%Y-%m-%d %H:%M}] L{self.level} {self.pain_type}"


class MedicationRecord(models.Model):
    """服薬記録（1回飲むごとに1行）"""
    # 飲んだ日時
    taken_at = models.DateTimeField("服薬日時")
    # 薬名
    name = models.CharField("薬名", max_length=50)

    class Meta:
        ordering = ["-taken_at"]  # 新しい順

    def __str__(self) -> str:
        return f"[{self.taken_at:%Y-%m-%d %H:%M}] {self.name}"


class WeatherRecord(models.Model):
    """天気記録（観測時刻でunique）

    実測・予報を1テーブルで持ち、is_forecast で区別する。
      - is_forecast=False : Open-Meteo の実測(過去〜現在)
      - is_forecast=True  : Open-Meteo の予報(未来)
    観測時刻が過ぎて実測に切り替わると、同じ observed_at 行が
    upsert で is_forecast=False に更新される（unique=True なので1時刻1行を維持）。
    """
    # 観測時刻。unique=True で「同じ時刻は1行だけ」を保証。
    # → weather_sync.py が再取得しても重複が増えない(upsertの土台)
    observed_at = models.DateTimeField("観測時刻", unique=True)
    # 天気コード(4分類:0晴/1晴のち曇/2曇/3雨)。初期値2(曇)
    weather_code = models.PositiveSmallIntegerField("天気コード", default=2)
    # 気温(℃)。小数を扱うので FloatField
    temperature_c = models.FloatField("気温(℃)")
    # 気圧(hPa)。痛みとの突合で使う中核データ
    pressure_hpa = models.FloatField("気圧(hPa)")
    # ★案B追加：予報フラグ。True=未来の予報値 / False=実測値
    #   既存行はすべて実測なので default=False で安全に追加できる
    is_forecast = models.BooleanField("予報フラグ", default=False)

    class Meta:
        ordering = ["-observed_at"]  # 新しい順

    def __str__(self) -> str:
        tag = "予報" if self.is_forecast else "実測"
        return f"[{self.observed_at:%Y-%m-%d %H:%M}] {tag} {self.temperature_c}℃ / {self.pressure_hpa}hPa"


class ReminderSetting(models.Model):
    """薬リマインド設定（何時に・何の薬を・有効か）"""

    # ★Lv3追加：この服薬設定の持ち主。null許可で既存行を救済してから backfill する
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="ユーザー",
    )

    # 通知時刻(時:分のみ。日付は持たない)
    reminder_time = models.TimeField("リマインド時刻")
    # 通知対象の薬名
    medicine_name = models.CharField("薬名", max_length=50)
    # 有効フラグ。True=ON / False=OFF。外すだけで通知停止できる
    is_active = models.BooleanField("有効", default=True)

    class Meta:
        ordering = ["reminder_time"]  # 時刻が早い順

    def __str__(self) -> str:
        flag = "ON" if self.is_active else "OFF"
        return f"{self.reminder_time:%H:%M} {self.medicine_name} [{flag}]"


class UserLocation(models.Model):
    """ユーザー現在地（単一行: pk=1 を固定使用）

    ブラウザの Geolocation API で取得した位置を保存。
    weather_sync.py はこの値を読んで Open-Meteo を叩く。
    アプリ全体で1地点あれば足りるので、常に pk=1 の1行を使い回す。
    """
    # 緯度。初期値は東京駅相当
    latitude = models.FloatField("緯度", default=35.6895)
    # 経度
    longitude = models.FloatField("経度", default=139.6917)
    # 位置精度(m)。取得できないこともあるので null/空欄を許可
    accuracy_m = models.FloatField("精度(m)", null=True, blank=True)
    # 最終更新日時。保存のたびに自動で現在時刻へ更新(auto_now=True)
    updated_at = models.DateTimeField("最終更新", auto_now=True)

    class Meta:
        verbose_name = "ユーザー現在地"

    def __str__(self) -> str:
        return f"({self.latitude:.4f}, {self.longitude:.4f}) ±{self.accuracy_m}m"

    @classmethod
    def current(cls) -> "UserLocation":
        """常に pk=1 の1レコードを返す。無ければデフォルト値で作成。"""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj