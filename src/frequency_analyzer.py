from config import THRESHOLDS


def calculate_frequency(impressions: int, reach: int) -> float:
    if reach == 0:
        return 0.0
    return round(impressions / reach, 1)


def get_frequency_status(frequency: float) -> dict:
    if frequency >= THRESHOLDS["frequency_critical"]:
        return {
            "value": frequency,
            "level": "critical",
            "emoji": "\U0001f6a8",
            "message": "경고: 즉시 조치 필요",
        }
    if frequency >= THRESHOLDS["frequency_warning"]:
        return {
            "value": frequency,
            "level": "warning",
            "emoji": "\u26a0\ufe0f",
            "message": "주의: 소재 피로도 증가 가능",
        }
    if frequency >= 2.0:
        return {
            "value": frequency,
            "level": "moderate",
            "emoji": "\U0001f7e1",
            "message": "",
        }
    return {
        "value": frequency,
        "level": "normal",
        "emoji": "",
        "message": "",
    }


def analyze_frequency_trend(daily_frequencies: list[float]) -> dict:
    if not daily_frequencies:
        return {
            "values": [],
            "trend": "stable",
            "avg": 0.0,
            "sparkline": "",
            "message": "데이터 없음",
        }

    avg = round(sum(daily_frequencies) / len(daily_frequencies), 2)

    # 추세 판단: 최근 3일 기준
    if len(daily_frequencies) >= 3:
        recent = daily_frequencies[-3:]
        if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
            trend = "increasing"
        elif all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # 스파크라인 생성
    sparkline = _build_sparkline(daily_frequencies)

    messages = {
        "increasing": "Frequency가 점진적으로 상승 중입니다.",
        "decreasing": "Frequency가 하락 추세입니다.",
        "stable": "Frequency가 안정적입니다.",
    }

    return {
        "values": daily_frequencies,
        "trend": trend,
        "avg": avg,
        "sparkline": sparkline,
        "message": messages[trend],
    }


def _build_sparkline(values: list[float]) -> str:
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)
    spread = max_val - min_val
    if spread == 0:
        return blocks[3] * len(values)
    return "".join(
        blocks[min(int((v - min_val) / spread * (len(blocks) - 1)), len(blocks) - 1)]
        for v in values
    )


def get_campaign_frequency_ranking(campaigns: list[dict]) -> list[dict]:
    ranked = []
    for c in campaigns:
        freq = c.get("frequency", 0.0)
        if freq == 0.0:
            impressions = c.get("impressions", 0)
            reach = c.get("reach", 0)
            freq = calculate_frequency(int(impressions), int(reach))

        status = get_frequency_status(freq)
        ranked.append({
            "campaign_id": c.get("campaign_id", ""),
            "campaign_name": c.get("campaign_name", ""),
            "frequency": freq,
            "level": status["level"],
            "emoji": status["emoji"],
        })

    ranked.sort(key=lambda x: x["frequency"], reverse=True)
    return ranked
