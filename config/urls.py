# -*- coding: utf-8 -*-
# config/urls.py（プロジェクト全体のURL振り分け）
#
# 【2026-06-22 改修：全ページ ログイン必須化（deny by default）】
#  ・settings.py に LoginRequiredMiddleware を入れると、全ビューが
#    デフォルトでログイン必須になる。
#  ・ただし「ログイン画面」自体もブロック対象になり、未ログインだと
#    /accounts/login/ → /accounts/login/ → … と無限リダイレクトに陥る。
#  ・そこで login だけを login_not_required でラップし、
#    include('django.contrib.auth.urls') より「前」に定義して
#    URL解決が先にこちらへ当たるようにする（無限ループ防止）。
#  ・URLパスは同じ /accounts/login/ なので reverse('login') も矛盾しない。

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_not_required  # ★追加
from django.contrib.auth import views as auth_views            # ★追加

urlpatterns = [
    path('admin/', admin.site.urls),

    # ★追加：login だけ「ログイン不要」で先に定義（無限リダイレクト防止）
    #   include より前に置くことが重要（URL解決はリスト先頭から順に当たる）。
    path('accounts/login/',
         login_not_required(auth_views.LoginView.as_view()),
         name='login'),

    # Django標準の認証ビュー群を一括追加
    # logout / password_change / password_reset 等が name付きで使える。
    # （login は上で先取り定義済みなので、ここでは重複してもこちらは当たらない）
    path('accounts/', include('django.contrib.auth.urls')),

    # 既存の tracker アプリ
    path('', include('tracker.urls')),

]
