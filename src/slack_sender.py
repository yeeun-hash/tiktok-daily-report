import logging
import requests
from config import SLACK_WEBHOOK_URL
from data_processor import format_currency, format_percentage, format_number

logger = logging.getLogger(__name__)


def _change_emoji(change_pct: float, is_cost: bool = False) -> str:
    if change_pct > 0:
        arrow = "\U0001f53a"
        color = "\U0001f534" if is_cost else "\U0001f7e2"
    elif change_pct < 0:
        arrow = "\U0001f53b"
        color = "\U0001f7e2" if is_cost else "\U0001f534"
    else:
        return "\u2796 0.0%"
    return f"{color} {arrow} {change_pct:+.1f}%"


def _freq_emoji(frequency: float) -> str:
    if frequency >= 5.0:
        return "\U0001f6a8"
    if frequency >= 3.0:
        return "\u26a0\ufe0f"
    if frequency >= 2.0:
        return "\U0001f7e1"
    return ""


def build_header_block(date: str) -> dict:
    return {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"\U0001f4ca TikTok \uad11\uace0 \uc77c\uc77c \ub9ac\ud3ec\ud2b8 ({date})",
            "emoji": True,
        },
    }


def build_summary_block(account_data: dict) -> list[dict]:
    spend = account_data.get("spend", 0)
    impressions = account_data.get("impressions", 0)
    clicks = account_data.get("clicks", 0)
    ctr = account_data.get("ctr", 0)
    cpc = account_data.get("cpc", 0)
    conversions = account_data.get("conversion", 0)
    cpa = account_data.get("cost_per_conversion", 0)
    frequency = account_data.get("frequency", 0)

    spend_chg = account_data.get("spend_change", 0)
    impressions_chg = account_data.get("impressions_change", 0)
    clicks_chg = account_data.get("clicks_change", 0)
    ctr_chg = account_data.get("ctr_change", 0)
    cpc_chg = account_data.get("cpc_change", 0)
    conv_chg = account_data.get("conversions_change", 0)
    cpa_chg = account_data.get("cost_per_conversion_change", 0)
    freq_chg = account_data.get("frequency_change", 0)

    freq_emoji = _freq_emoji(frequency)
    freq_7d_avg = account_data.get("frequency_vs_avg", 0)

    lines = [
        f"*\ube44\uc6a9:* {format_currency(spend)}  {_change_emoji(spend_chg, is_cost=True)}",
        f"*\ub178\ucd9c:* {format_number(impressions)}  {_change_emoji(impressions_chg)}",
        f"*\ud074\ub9ad:* {format_number(clicks)}  {_change_emoji(clicks_chg)}",
        f"*CTR:* {ctr:.2f}%  {_change_emoji(ctr_chg)}",
        f"*CPC:* {format_currency(cpc)}  {_change_emoji(cpc_chg, is_cost=True)}",
        f"*\uc804\ud658:* {int(conversions):,}\uac74  {_change_emoji(conv_chg)}",
        f"*\uc804\ud658\ub2e8\uac00:* {format_currency(cpa)}  {_change_emoji(cpa_chg, is_cost=True)}",
        f"*\U0001f464 Frequency:* {frequency:.1f}\ud68c {freq_emoji}  (7\uc77c \ud3c9\uade0 \ub300\ube44 {freq_7d_avg:+.1f}%)",
    ]

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\U0001f4cc *\uc804\uccb4 \uc131\uacfc \uc694\uc57d*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            },
        },
    ]


def build_anomaly_block(anomalies: list[dict]) -> list[dict]:
    if not anomalies:
        return []

    lines = []
    for a in anomalies:
        if a["type"] == "positive":
            emoji = "\U0001f7e2"
        elif a["severity"] == "critical":
            emoji = "\U0001f6a8"
        else:
            emoji = "\U0001f534"
        lines.append(f"{emoji} {a['message']}")

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\u26a1 *\ud2b9\uc774\uc0ac\ud56d*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            },
        },
    ]


def build_campaign_ranking_block(campaigns: list[dict], top_n: int = 5) -> list[dict]:
    if not campaigns:
        return []

    lines = []
    for i, c in enumerate(campaigns[:top_n], 1):
        name = c.get("campaign_name", "")
        spend = format_currency(c.get("spend", 0))
        ctr = c.get("ctr", 0)
        conv = int(c.get("conversion", 0))
        cpa = format_currency(c.get("cost_per_conversion", 0))
        freq = c.get("frequency", 0)
        freq_e = _freq_emoji(freq)

        lines.append(
            f"*{i}. {name}*\n"
            f"   \ube44\uc6a9 {spend} | CTR {ctr:.2f}% | \uc804\ud658 {conv}\uac74 | \uc804\ud658\ub2e8\uac00 {cpa} | Freq {freq:.1f} {freq_e}"
        )

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\U0001f3c6 *\uce60\ud398\uc778 TOP {top_n} (\ube44\uc6a9 \uae30\uc900)*".format(top_n=top_n),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n\n".join(lines),
            },
        },
    ]


def build_action_alert_block(campaign_actions: list[dict], creative_fatigue: list[dict]) -> list[dict]:
    if not campaign_actions and not creative_fatigue:
        return [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\u2705 *\ubaa8\ub4e0 \uce60\ud398\uc778/\uc18c\uc7ac \uc815\uc0c1 \uc6b4\uc601 \uc911*",
                },
            },
        ]

    lines = []

    for ca in campaign_actions:
        cname = ca.get("campaign_name", "")
        for issue in ca.get("issues", []):
            lines.append(
                f"\U0001f6a8 *[{cname}]* {issue['description']}\n"
                f"   \u2192 {issue['action']}"
            )

    for cf in creative_fatigue:
        aname = cf.get("ad_name", "")
        cname = cf.get("campaign_name", "")
        for issue in cf.get("issues", []):
            lines.append(
                f"\U0001f6a8 *[{aname}]* ({cname}) {issue['description']}\n"
                f"   \u2192 {issue['action']}"
            )

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\U0001f6a8 *\uc561\uc158 \ud544\uc694*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n\n".join(lines),
            },
        },
    ]


def build_creative_ranking_block(creatives: list[dict], top_n: int = 5) -> list[dict]:
    if not creatives:
        return []

    lines = []
    for i, ad in enumerate(creatives[:top_n], 1):
        name = ad.get("ad_name", "")
        spend = format_currency(ad.get("spend", 0))
        ctr = ad.get("ctr", 0)
        cr = ad.get("completion_rate", 0)
        conv = int(ad.get("conversion", 0))

        lines.append(
            f"*{i}. {name}*\n"
            f"   \ube44\uc6a9 {spend} | CTR {ctr:.2f}% | \uc644\uc2dc\uccad\ub960 {cr:.1f}% | \uc804\ud658 {conv}\uac74"
        )

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"\U0001f3ac *\ud06c\ub9ac\uc5d0\uc774\ud2f0\ube0c TOP {top_n} (\uc804\ud658 \uae30\uc900)*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n\n".join(lines),
            },
        },
    ]


def build_frequency_block(frequency_data: dict) -> list[dict]:
    account_freq = frequency_data.get("account_frequency", 0)
    avg_7d = frequency_data.get("avg_7d", 0)
    trend_data = frequency_data.get("trend", {})
    campaign_ranking = frequency_data.get("campaign_ranking", [])

    freq_emoji = _freq_emoji(account_freq)
    avg_change = 0
    if avg_7d > 0:
        avg_change = round((account_freq - avg_7d) / avg_7d * 100, 1)

    lines = [
        f"*\uacc4\uc815 \uc804\uccb4:* {account_freq:.1f}\ud68c {freq_emoji} (7\uc77c \ud3c9\uade0 {avg_7d:.1f}\ud68c, {avg_change:+.1f}%)",
    ]

    if campaign_ranking:
        lines.append("")
        lines.append("*\uce60\ud398\uc778\ubcc4 Frequency TOP 3:*")
        for i, cr in enumerate(campaign_ranking[:3], 1):
            emoji = cr.get("emoji", "")
            lines.append(f"   {i}. [{cr['campaign_name']}] {cr['frequency']:.1f}\ud68c {emoji}")

    sparkline = trend_data.get("sparkline", "")
    values = trend_data.get("values", [])
    if values:
        val_str = " \u2192 ".join(f"{v:.1f}" for v in values)
        lines.append(f"\n\U0001f4ca *7\uc77c \ucd94\uc774:* {sparkline}\n   {val_str}")

    trend_msg = trend_data.get("message", "")
    if trend_msg:
        lines.append(f"   _{trend_msg}_")

    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\U0001f464 *Frequency(1\uc778\ub2f9 \ub178\ucd9c \ube48\ub3c4) \ud604\ud669*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(lines),
            },
        },
    ]


def build_insight_block(insight_text: str) -> list[dict]:
    return [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\U0001f916 *AI \uc778\uc0ac\uc774\ud2b8*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": insight_text,
            },
        },
    ]


def send_report(blocks: list[dict]) -> bool:
    payload = {"blocks": blocks}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text == "ok":
            logger.info("Slack 리포트 발송 성공")
            return True
        logger.error(f"Slack 발송 실패: status={resp.status_code}, body={resp.text}")
        return False
    except requests.RequestException as e:
        logger.error(f"Slack 발송 오류: {e}")
        return False


def send_error_alert(error_message: str) -> bool:
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "\U0001f6a8 TikTok \ub9ac\ud3ec\ud2b8 \uc624\ub958 \ubc1c\uc0dd",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```{error_message}```",
            },
        },
    ]
    payload = {"blocks": blocks}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        return resp.status_code == 200
    except requests.RequestException as e:
        logger.error(f"에러 알림 발송 실패: {e}")
        return False
