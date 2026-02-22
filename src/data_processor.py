def _safe_change_pct(today_val: float, yesterday_val: float) -> float:
    if yesterday_val == 0:
        return 0.0 if today_val == 0 else 100.0
    return round((today_val - yesterday_val) / abs(yesterday_val) * 100, 2)


def calculate_daily_change(today: dict, yesterday: dict) -> dict:
    metrics = [
        "spend", "impressions", "reach", "clicks", "ctr", "cpc", "cpm",
        "conversion", "cost_per_conversion", "cost_per_result", "frequency",
    ]
    result = {}
    for m in metrics:
        t_val = today.get(m, 0.0)
        y_val = yesterday.get(m, 0.0)
        result[f"{m}_change"] = _safe_change_pct(t_val, y_val)
    return result


def calculate_weekly_average(week_data: list[dict]) -> dict:
    if not week_data:
        return {}

    metrics = [
        "spend", "impressions", "reach", "clicks", "ctr", "cpc", "cpm",
        "conversion", "cost_per_conversion", "cost_per_result", "frequency",
    ]
    result = {}
    n = len(week_data)
    for m in metrics:
        total = sum(day.get(m, 0.0) for day in week_data)
        result[f"{m}_avg"] = round(total / n, 2) if n > 0 else 0.0
    return result


def compare_with_weekly(today: dict, weekly_avg: dict) -> dict:
    metrics = [
        "spend", "impressions", "reach", "clicks", "ctr", "cpc", "cpm",
        "conversion", "cost_per_conversion", "cost_per_result", "frequency",
    ]
    result = {}
    for m in metrics:
        t_val = today.get(m, 0.0)
        avg_val = weekly_avg.get(f"{m}_avg", 0.0)
        result[f"{m}_vs_avg"] = _safe_change_pct(t_val, avg_val)
    return result


def rank_campaigns(campaigns: list[dict], sort_by: str = "spend", top_n: int = 5) -> list[dict]:
    sorted_list = sorted(campaigns, key=lambda x: x.get(sort_by, 0), reverse=True)
    return sorted_list[:top_n]


def rank_creatives(ads: list[dict], sort_by: str = "conversion", top_n: int = 5) -> list[dict]:
    sorted_list = sorted(ads, key=lambda x: x.get(sort_by, 0), reverse=True)
    return sorted_list[:top_n]


def calculate_completion_rate(ad: dict) -> float:
    views_p100 = ad.get("video_views_p100", 0)
    impressions = ad.get("impressions", 0)
    if impressions == 0:
        return 0.0
    return round(views_p100 / impressions * 100, 2)


def format_currency(amount: float) -> str:
    if amount >= 1:
        return f"₩{int(amount):,}"
    if amount > 0:
        return f"₩{amount:.2f}"
    return "₩0"


def format_percentage(value: float, with_sign: bool = True) -> str:
    if with_sign:
        return f"{value:+.1f}%"
    return f"{value:.1f}%"


def format_number(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{int(value):,}"


def build_report_data(
    date: str,
    account_today: dict,
    account_yesterday: dict,
    weekly_account_data: list[dict],
    campaigns_today: list[dict],
    ads_today: list[dict],
    frequency_trend_7d: list[float],
) -> dict:
    daily_change = calculate_daily_change(account_today, account_yesterday)
    weekly_avg = calculate_weekly_average(weekly_account_data)
    weekly_comparison = compare_with_weekly(account_today, weekly_avg)

    account_summary = {**account_today}
    account_summary.update(daily_change)
    account_summary.update(weekly_comparison)

    top_campaigns = rank_campaigns(campaigns_today, sort_by="spend")
    top_creatives = rank_creatives(ads_today, sort_by="conversion")

    for ad in ads_today:
        ad["completion_rate"] = calculate_completion_rate(ad)
    for ad in top_creatives:
        ad["completion_rate"] = calculate_completion_rate(ad)

    return {
        "date": date,
        "account_summary": account_summary,
        "top_campaigns": top_campaigns,
        "top_creatives": top_creatives,
        "weekly_avg": weekly_avg,
        "weekly_comparison": weekly_comparison,
        "daily_change": daily_change,
        "frequency_trend_7d": frequency_trend_7d,
    }
