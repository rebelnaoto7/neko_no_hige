# -*- coding: utf-8 -*-
"""
tracker/services/advice.py
気温データから猫のアドバイス文を生成する（ルールベース）
"""

DIFF_THRESHOLD = 10.0  # 寒暖差「大」とみなす閾値(℃)


def build_temperature_advice(temp_max, temp_min):
    """
    最高/最低気温から寒暖差を計算し、猫のアドバイス文を返す。
    temp_max, temp_min: float（None可）
    戻り値: dict（データ不足時は advice=None）
    """
    if temp_max is None or temp_min is None:
        return {
            "temp_max": None,
            "temp_min": None,
            "diff": None,
            "diff_msg": None,
            "feel": None,
            "advice": None,
            "reason": "本日の気象データがまだありません。",
        }

    diff = round(temp_max - temp_min, 1)

    # ② 寒暖差による補足
    if diff >= DIFF_THRESHOLD:
        diff_msg = "本日は寒暖差が大きいため、昼間は暖かいですが、朝晩は冷え込む可能性があるにゃ。"
    else:
        diff_msg = "気温の変動が少なく、快適に過ごせる一日だにゃ。"

    # 絶対気温による「暑い/寒い」（猫の口調）
    if temp_max >= 27:
        feel = "今日は暑いにゃ。水分補給を忘れずににゃ。"
    elif temp_min <= 10:
        feel = "今日は冷えるにゃ。あったかくして過ごしてにゃ。"
    else:
        feel = "過ごしやすい気温だにゃ。"

    return {
        "temp_max": temp_max,
        "temp_min": temp_min,
        "diff": diff,
        "diff_msg": diff_msg,
        "feel": feel,
        "advice": f"{feel}\n{diff_msg}",    # 猫の最終セリフ
        "reason": None,
    }
