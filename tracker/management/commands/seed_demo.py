# -*- coding: utf-8 -*-
"""
tracker/management/commands/seed_demo.py
ねこのひげ - デモ用テストデータ投入コマンド

【目的】
開発・デモ用のサンプルデータを「クリーンな状態」でDBに流し込む。
新規環境で動作確認したい時や、画面の見た目をスクショ撮りたい時に使う。

【このコマンドがやること】
  1. 既存の全データを削除（クリーン投入）
  2. 痛み記録を3件作成（現在 / 3時間前 / 6時間前）
  3. 各痛み記録の時刻に対応する気圧データを作成（突き合わせ前提）
  4. 服薬記録を1件作成
  5. 12:00 のリマインダーを1件登録

【実行方法】
    python manage.py seed_demo

【⚠️ 重要な注意】
  - 既存データを全削除する破壊的なコマンド
  - 本番DBで絶対に実行しないこと
  - 実行前に必ず DEBUG=True / 開発DB であることを確認

【Djangoコマンド機構について】
  tracker/management/commands/ 配下に置いたファイルは、
  python manage.py <ファイル名> で自動的に呼び出せるようになる。
  Command クラスの handle() メソッドが実体。
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, time

from tracker.models import (
    PainRecord,
    MedicationRecord,
    WeatherRecord,
    ReminderSetting,
)
# 痛み記録時刻を「正時」に切り捨てるユーティリティ。
# 気象データを1時間粒度で持っているため、突き合わせのキーを揃える目的で使う。
from tracker.services.matching import floor_to_hour


class Command(BaseCommand):
    """
    Djangoカスタム管理コマンドの本体。
    `python manage.py seed_demo` で起動される。
    """

    # `python manage.py help seed_demo` で表示される説明文
    help = "デモ用のテストデータを投入する"

    def handle(self, *args, **options):
        """
        コマンドの実処理。
        BaseCommand のインターフェース上、必ずこのメソッド名で定義する。
        """

        # ============================================================
        # 1. 既存データの全削除（クリーン再投入）
        # ============================================================
        # デモデータは「毎回まっさらな状態から作り直す」前提のため、
        # 4テーブルの全レコードを先に消し去る。
        # ⚠️ ここで本番データが消えないよう、実行環境を必ず確認すること。
        PainRecord.objects.all().delete()
        MedicationRecord.objects.all().delete()
        WeatherRecord.objects.all().delete()
        ReminderSetting.objects.all().delete()

        # 全レコードの時刻を「実行した瞬間」基準で組み立てる。
        # → デモを実行した時点を「今」として、過去のデータを生成する。
        now = timezone.now()

        # ============================================================
        # 2. 痛み記録を3件作成（時系列でばらして "履歴っぽさ" を出す）
        # ============================================================
        # 意図：
        #   - 今(level=3 すごく痛い) → 3時間前(2 痛い) → 6時間前(1 痛くない)
        #     と痛みが強まっていく流れを再現
        #   - グラフ画面で「気圧低下に伴って痛みが増す」相関を視覚化しやすい
        #
        # 注意：
        #   body_part / pain_type は初版マイグレーション(0001)の choices値（英字）を
        #   そのまま使っている。現行のviews.pyは日本語キー（"頭痛"等）で扱うため、
        #   表示時にラベル変換が効かない場合がある（要見直し候補）。
        pains = [
            PainRecord.objects.create(
                recorded_at=now,                       # いま
                level=3, body_part="head",     pain_type="throbbing", memo="朝から"),
            PainRecord.objects.create(
                recorded_at=now - timedelta(hours=3),  # 3時間前
                level=2, body_part="shoulder", pain_type="dull",      memo="昼"),
            PainRecord.objects.create(
                recorded_at=now - timedelta(hours=6),  # 6時間前
                level=1, body_part="back",     pain_type="stiffness", memo="朝方"),
        ]

        # ============================================================
        # 3. 気圧記録を投入（痛み記録と "同じ正時" に紐付け）
        # ============================================================
        # 設計意図：
        #   - 各痛み記録の時刻を `floor_to_hour` で正時に丸めて、
        #     WeatherRecord の observed_at と一致させる
        #   - これにより charts 画面の "気圧と痛みの突き合わせ" が確実に成立
        #
        # 気圧値の並び（1008.5 → 1011.2 → 1013.0）は意図的に
        #   「現在ほど低い」= 低気圧 + 痛み強の相関 を演出している
        #
        # update_or_create を使う理由：
        #   observed_at は unique=True 制約があるため、
        #   同時刻のレコードを2回作るとIntegrityErrorになる。
        #   既存があれば更新、無ければ作成する安全な書き方。
        for p, hpa in zip(pains, [1008.5, 1011.2, 1013.0]):
            WeatherRecord.objects.update_or_create(
                observed_at=floor_to_hour(p.recorded_at),
                defaults={
                    "weather_code": 3,       # 3=雨（Open-Meteo準拠）
                    "temperature_c": 22.0,   # 仮の気温
                    "pressure_hpa": hpa,     # 上記の意図的な並び
                },
            )

        # ============================================================
        # 4. 服薬記録を1件作成
        # ============================================================
        # 5時間前に「ロキソニン」を服用したことにする。
        # 履歴一覧や将来の服薬×痛みの相関分析の足場データ。
        MedicationRecord.objects.create(
            taken_at=now - timedelta(hours=5),
            name="ロキソニン",
        )

        # ============================================================
        # 5. リマインダー設定を1件作成
        # ============================================================
        # ホーム画面右下の吹き出し「次のお薬は12:00だにゃ！」を表示させるための元データ。
        #
        # get_or_create を使う理由：
        #   既に同時刻のリマインダーが存在していた場合の重複作成を防ぐ。
        #   （このコマンドは冒頭で全削除しているので実質的には常に作成側に倒れるが、
        #    将来「削除をやめて追記だけにしたい」変更に強くしておく保険）
        ReminderSetting.objects.get_or_create(
            reminder_time=time(12, 0),
            defaults={
                "medicine_name": "ロキソニン",
                "is_active": True,
            },
        )

        # ============================================================
        # 完了メッセージ
        # ============================================================
        # self.style.SUCCESS は緑文字でコンソール出力するDjango標準のヘルパー。
        # print() ではなく self.stdout.write を使うのがコマンド作法。
        # → テスト時に出力をキャプチャしやすく、I/Oフックも効くため。
        self.stdout.write(self.style.SUCCESS("デモデータを投入しました"))