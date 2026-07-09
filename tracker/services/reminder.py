# -*- coding: utf-8 -*-
"""
tracker/services/reminder.py
ねこのひげ - 次のおくすりリマインダー計算ロジック

役割:
    ホーム画面の吹き出しに表示する「次のおくすり時刻」を1か所で計算する。
    views.py からは get_next_reminder() を呼ぶだけで使える。

ルール:
    1. is_active=True の ReminderSetting だけを対象にする
    2. 現在時刻(Asia/Tokyo) より後で、最も近い時刻を「今日の次」として返す
    3. 今日の残りが無ければ、翌日の一番早い時刻を「明日の最初」として返す
    4. 有効なリマインダーが1件もなければ None を返す
"""

from datetime import datetime, timedelta
from django.utils import timezone
from tracker.models import ReminderSetting


def get_next_reminder(now=None, user=None):   # ★Lv3：user で本人の設定に絞る
    """
    次のリマインダー情報を1件だけ返す。

    Args:
        now (datetime, optional):
            現在時刻。通常は None（= timezone.now() を使う）。
            テストで時刻を固定したい場合だけ渡す。

    Returns:
        dict | None:
            {
                "time": time,             # 例: datetime.time(12, 0)
                "medicine_name": str,     # 例: "ロキソニン"
                "is_tomorrow": bool,      # 今日中なら False, 翌日繰越なら True
                "label": str,             # 表示用 "HH:MM"
                "minutes_until": int,     # 何分後か（負にはならない）
            }
            有効なリマインダーが1件も無ければ None
    """

    # ----- ステップ1: 現在時刻を Asia/Tokyo に変換 -----
    # settings.TIME_ZONE = "Asia/Tokyo" の前提。
    # localtime() を必ず通すことで「UTCのまま比較する」バグを根絶する。
    if now is None:
        now = timezone.localtime()
    else:
        if timezone.is_aware(now):
            now = timezone.localtime(now)

    today_date = now.date()
    current_time = now.time()

    # ----- ステップ2: 有効なリマインダーを reminder_time 昇順で取得 -----
    # ★Lv3：本人の設定だけに絞る（user=None のときは全件＝後方互換）
    base_qs = ReminderSetting.objects.filter(is_active=True)
    if user is not None:
        base_qs = base_qs.filter(user=user)

    reminders = list(
        base_qs
        .order_by("reminder_time")
    )

    # 1件も無い場合は None を返してテンプレ側で分岐させる
    if not reminders:
        return None

    # ----- ステップ3: 今日の残りから「次」を探す -----
    # reminder_time は昇順なので、最初に「現在時刻より後」になったものが答え
    for r in reminders:
        if r.reminder_time > current_time:
            today_dt = datetime.combine(today_date, r.reminder_time)
            current_dt = datetime.combine(today_date, current_time)
            minutes_until = int((today_dt - current_dt).total_seconds() // 60)
            return {
                "time": r.reminder_time,
                "medicine_name": r.medicine_name,
                "is_tomorrow": False,
                "label": r.reminder_time.strftime("%H:%M"),
                "minutes_until": max(minutes_until, 0),
            }

    # ----- ステップ4: 今日の残りが無ければ「明日の最初」を返す -----
    first = reminders[0]
    tomorrow_date = today_date + timedelta(days=1)
    tomorrow_dt = datetime.combine(tomorrow_date, first.reminder_time)
    current_dt = datetime.combine(today_date, current_time)
    minutes_until = int((tomorrow_dt - current_dt).total_seconds() // 60)
    return {
        "time": first.reminder_time,
        "medicine_name": first.medicine_name,
        "is_tomorrow": True,
        "label": first.reminder_time.strftime("%H:%M"),
        "minutes_until": max(minutes_until, 0),
    }
