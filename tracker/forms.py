# -*- coding: utf-8 -*-
"""
tracker/forms.py
ねこのひげ - フォーム定義

Django の ModelForm を使い、モデルからフォームを自動生成する。
- ModelForm にすることで、バリデーションや save() 処理をモデル定義に委譲できる
- widgets で <input> のHTML属性を指定し、ブラウザ側のUI/UXを最適化する

【方針】
- 入力UIは「ブラウザ標準のネイティブUI」を優先（datetime-local / number など）
  → モバイルでも適切な入力ピッカーが自動で出る
- 範囲制限はサーバ側（モデル）でもバリデーションする前提で、
  クライアント側の `min` / `max` は「入力ミスを減らすためのガード」として置く
"""
from django import forms
from .models import PainRecord, MedicationRecord


# ============================================================
# 痛み記録フォーム
# ============================================================
class PainRecordForm(forms.ModelForm):
    """
    PainRecord モデルに対応する入力フォーム。
    新規作成・編集の両画面で共通利用する想定。
    """

    class Meta:
        # 紐付けるモデル
        model = PainRecord

        # フォームに表示するフィールド（順序もこの並びで描画される）
        # - recorded_at : 痛みを記録した日時
        # - level       : 痛みの強さ（0〜10のスケール）
        # - body_part   : 痛む部位（自由入力 or 選択肢）
        # - memo        : 補足メモ
        fields = ["recorded_at", "level", "body_part", "memo"]

        # 各フィールドのHTMLウィジェットをカスタマイズ
        widgets = {
            # 日時入力をブラウザ標準の datetime ピッカーにする
            # （type="datetime-local" でカレンダー+時計UIが出る）
            "recorded_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),

            # 痛みレベルは数値入力。
            # min/max でブラウザ側の入力範囲ガードをかける
            # （※サーバ側のバリデーションも別途必要）
            "level": forms.NumberInput(attrs={"min": 0, "max": 10}),
        }


# ============================================================
# 服薬記録フォーム
# ============================================================
class MedicationRecordForm(forms.ModelForm):
    """
    MedicationRecord モデルに対応する入力フォーム。
    「いつ・何の薬を・補足あれば」を記録するシンプルなフォーム。
    """

    class Meta:
        # 紐付けるモデル
        model = MedicationRecord

        # フォームに表示するフィールド
        # - taken_at : 薬を飲んだ日時
        # - name     : 薬の名前
        # - memo     : 補足メモ（用量や効き方など）
        fields = ["taken_at", "name", "memo"]

        # 各フィールドのHTMLウィジェットをカスタマイズ
        widgets = {
            # 日時入力をブラウザ標準の datetime ピッカーにする
            "taken_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }