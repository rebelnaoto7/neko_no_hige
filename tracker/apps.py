# -*- coding: utf-8 -*-
"""
tracker/apps.py
ねこのひげ - アプリケーション設定

Django は INSTALLED_APPS に登録されたアプリごとに AppConfig を持つ。
このファイルは tracker アプリの起動時設定をまとめたもの。

【主な役割】
- アプリ名の宣言（Django内部での識別子）
- モデルの主キーのデフォルト型を指定
- （必要に応じて）アプリ起動時の初期化処理を ready() に書く場所
"""
from django.apps import AppConfig


class TrackerConfig(AppConfig):
    """
    tracker アプリの設定クラス。

    settings.py の INSTALLED_APPS に
        'tracker'
    と書くだけで、Djangoがこのクラスを自動的に読み込んでくれる
    （`default_app_config` を明示しなくても、apps.py 内の AppConfig 派生クラスが拾われる）。
    """

    # ------------------------------------------------------------
    # 主キーのデフォルト型
    # ------------------------------------------------------------
    # モデルで `id` フィールドを明示していない場合、Django が自動で付与する
    # 主キーの型をここで指定する。
    # - BigAutoField : 64bit整数（最大値が約9.2京）。Django 3.2以降の推奨デフォルト。
    # - AutoField    : 32bit整数。レコードが20億件を超えるとオーバーフローする。
    # ねこのひげは長期運用しても件数は控えめだが、将来の安全側に倒して BigAutoField を採用。
    default_auto_field = 'django.db.models.BigAutoField'

    # ------------------------------------------------------------
    # アプリの内部名
    # ------------------------------------------------------------
    # - INSTALLED_APPS や ForeignKey の文字列参照（例: 'tracker.PainRecord'）で使われる識別子
    # - 通常はディレクトリ名と一致させる（このアプリは `tracker/` 配下にあるため 'tracker'）
    name = 'tracker'

    # ------------------------------------------------------------
    # （任意）アプリ起動時の初期化処理を書く場所
    # ------------------------------------------------------------
    # シグナル(signals.py)の登録など、起動時に一度だけ実行したい処理は
    # ここに書くのが定石。現状は不要なので未実装。
    #
    # def ready(self):
    #     from . import signals  # noqa: F401