#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
manage.py
ねこのひげ - Django管理コマンド用エントリポイント

このファイルは Django プロジェクトの「司令塔」。
`python manage.py <subcommand>` の形で呼び出され、内部的に Django の
管理コマンド機構（runserver / migrate / createsuperuser など）に処理を委譲する。

【主な使い方】
    python manage.py runserver           # 開発用サーバ起動
    python manage.py makemigrations      # モデル変更からマイグレーション生成
    python manage.py migrate             # マイグレーションをDBに適用
    python manage.py createsuperuser     # 管理画面用のユーザ作成
    python manage.py shell               # Django環境込みのPython対話シェル
    python manage.py collectstatic       # 静的ファイル収集（本番デプロイ時）

【先頭行 `#!/usr/bin/env python` について】
    Linux/macOS で `./manage.py runserver` のように直接実行できるようにする
    ためのシバン行。Windowsでは無視される。
"""
import os
import sys


def main():
    """
    管理コマンドを実行する本体。

    実行の流れ：
      1. 使用する settings モジュールを環境変数で指定
      2. Djangoの管理コマンド関数を import（失敗時は丁寧なエラーを出す）
      3. コマンドライン引数を渡して実行
    """

    # ------------------------------------------------------------
    # 1. 設定ファイルの指定
    # ------------------------------------------------------------
    # Django は「どの settings.py を使うか」を環境変数
    # `DJANGO_SETTINGS_MODULE` から決める。
    # - `setdefault` を使っているのは、既に環境変数が設定されている場合
    #   （例：本番環境で `DJANGO_SETTINGS_MODULE=config.settings_prod` を
    #   セットしているケース）を尊重するため。
    # - 本プロジェクトの開発時のデフォルトは `config.settings`。
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    # ------------------------------------------------------------
    # 2. Django管理コマンド関数の import
    # ------------------------------------------------------------
    # ここで import に失敗する典型例：
    #   - 仮想環境 (.venv) を activate し忘れている
    #   - `pip install django` を実行していない
    #   - PYTHONPATH が壊れている
    # → ユーザに原因を気づかせるため、Django純正の親切なエラーメッセージを出す。
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # ------------------------------------------------------------
    # 3. コマンドライン引数を渡して実行
    # ------------------------------------------------------------
    # `sys.argv` には ['manage.py', 'runserver', ...] のように
    # コマンドライン全体が入っている。
    # Djangoはこれを解析して、対応する管理コマンド（runserver等）を起動する。
    execute_from_command_line(sys.argv)


# ============================================================
# エントリポイント
# ============================================================
# `python manage.py ...` で直接実行された時のみ main() を走らせる。
# import された場合は何もしない（テストや再利用がしやすい構造）。
if __name__ == '__main__':
    main()