"""痛み記録と気圧記録の時刻突き合わせユーティリティ"""
from .. models import WeatherRecord


def floor_to_hour(dt):
    """日時を正時に丸める（分・秒・マイクロ秒を切り捨て）
    例: 2026-06-04 09:37:21 → 2026-06-04 09:00:00
    """
    return dt.replace(minute=0, second=0, microsecond=0)


def get_pressure_for(recorded_at):
    """痛み記録時刻を正時に丸め、一致する気圧を返す。無ければNone"""
    hour = floor_to_hour(recorded_at)
    w = WeatherRecord.objects.filter(observed_at=hour).first()
    return w.pressure_hpa if w else None
