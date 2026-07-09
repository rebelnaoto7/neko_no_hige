# -*- coding: utf-8 -*-
"""
tracker/management/commands/seed_demo_forecast.py
発表用ダミー予報データ生成コマンド。

使い方:
  投入 : python manage.py seed_demo_forecast
  削除 : python manage.py seed_demo_forecast --clear
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.models import WeatherRecord


class Command(BaseCommand):
    help = "発表用のダミー予報データ(未来48h)を投入/削除する"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="未来の予報行(is_forecast=True)を全削除する",
        )

    def handle(self, *args, **opts):
        now = timezone.now()

        # --- 削除モード ---
        if opts["clear"]:                       # ★修正：バックスラッシュを除去
            deleted, _ = (WeatherRecord.objects
                          .filter(is_forecast=True, observed_at__gt=now)
                          .delete())
            self.stdout.write(self.style.SUCCESS(
                f"[seed] 予報行を削除しました: {deleted} 件"))
            return

        # --- 投入モード ---
        start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        base = 1012.0
        pressures = []
        for h in range(49):                     # 0〜48h
            if h <= 4:
                p = base
            elif h <= 14:
                p = base - (h - 4) * 1.8        # 6h差 約 -10.8hPa → 高リスク
            elif h <= 26:
                p = base - 18.0                 # 底(≒994)
            else:
                p = (base - 18.0) + (h - 26) * (16.0 / 22.0)
            pressures.append(round(p, 1))

        created = updated = 0
        for h, p in enumerate(pressures):
            obs = start + timedelta(hours=h)
            _, was_created = WeatherRecord.objects.update_or_create(
                observed_at=obs,
                defaults={
                    "weather_code": 3 if 5 <= h <= 26 else 2,
                    "temperature_c": 24.0,
                    "pressure_hpa": p,
                    "is_forecast": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"[seed] ダミー予報を投入: created={created} updated={updated} "
            f"(開始={timezone.localtime(start):%m/%d %H:%M})"))
        self.stdout.write(
            "→ この後は /weather-risk/ を直接開いてください"
            "（home/charts を開くと実データで上書きされます）")