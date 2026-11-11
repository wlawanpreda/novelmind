"""เทสต์ logic เลือกเวลา/กันซ้ำของ auto_mega (ไม่แตะ YouTube/ffmpeg)"""
from datetime import datetime
import auto_mega as am


def test_norm_matches_variants():
    a = am._norm("คุณแม่ลูกแฝดยุค70")
    b = am._norm("ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค_70_พร้อมซูเปอร์มาร์เก็ตลับ")
    assert a in b


def test_slot_is_golden_hour_and_lead_time():
    now = datetime(2026, 11, 11, 23, 0, tzinfo=am.TZ_TH)
    iso = am.next_free_slot({"items": []}, now=now)
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=am.timezone.utc).astimezone(am.TZ_TH)
    assert (dt.hour, dt.minute) in am.GOLDEN_HOURS
    assert (dt - now).total_seconds() >= am.MIN_LEAD_HOURS * 3600


def test_slot_skips_taken():
    now = datetime(2026, 11, 11, 23, 0, tzinfo=am.TZ_TH)
    first = am.next_free_slot({"items": []}, now=now)
    second = am.next_free_slot({"items": [{"publish_at": first}]}, now=now)
    assert second != first


def test_contiguity():
    f = lambda ns: [f"x_Audiobook_{n:02d}.mp3" for n in ns]
    assert am._is_contiguous(f(range(1, 16)))
    assert not am._is_contiguous(f([1, 2, 3, 5]))
    assert not am._is_contiguous([])
