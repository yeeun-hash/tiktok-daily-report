import time
import logging
import requests
from config import (
    TIKTOK_API_BASE,
    TIKTOK_ACCESS_TOKEN,
    TIKTOK_ADVERTISER_ID,
)

logger = logging.getLogger(__name__)

REPORT_URL = f"{TIKTOK_API_BASE}/report/integrated/get/"

ACCOUNT_METRICS = [
    "spend", "impressions", "reach", "clicks", "ctr", "cpc", "cpm",
    "conversions", "cost_per_conversion", "cost_per_result", "frequency",
]

CAMPAIGN_METRICS = [
    "spend", "impressions", "reach", "clicks", "ctr", "cpc", "cpm",
    "conversions", "cost_per_conversion", "cost_per_result", "frequency",
]

AD_METRICS = [
    "spend", "impressions", "clicks", "ctr", "cpc",
    "conversions", "cost_per_conversion",
    "video_play_actions", "video_watched_2s", "video_watched_6s",
    "video_views_p25", "video_views_p50", "video_views_p75", "video_views_p100",
    "average_video_play", "likes", "comments", "shares",
]

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2


class TikTokAPIError(Exception):
    pass


class TikTokTokenExpiredError(TikTokAPIError):
    pass


def _make_request(payload: dict, retry_count: int = 0) -> dict:
    headers = {"Access-Token": TIKTOK_ACCESS_TOKEN}

    try:
        import json
        params = {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in payload.items()}
        resp = requests.get(REPORT_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        if retry_count < MAX_RETRIES:
            delay = RETRY_BASE_DELAY ** (retry_count + 1)
            logger.warning(f"API 호출 실패, {delay}초 후 재시도 ({retry_count + 1}/{MAX_RETRIES}): {e}")
            time.sleep(delay)
            return _make_request(payload, retry_count + 1)
        raise TikTokAPIError(f"API 호출 실패 (최대 재시도 초과): {e}") from e

    code = data.get("code", -1)

    if code == 40105:
        raise TikTokTokenExpiredError(
            "TikTok Access Token이 만료되었습니다. "
            "TikTok for Business 개발자 센터에서 토큰을 재발급해주세요. "
            "https://business-api.tiktok.com/"
        )

    if code != 0:
        msg = data.get("message", "알 수 없는 오류")
        if retry_count < MAX_RETRIES:
            delay = RETRY_BASE_DELAY ** (retry_count + 1)
            logger.warning(f"API 응답 오류 (code={code}), {delay}초 후 재시도: {msg}")
            time.sleep(delay)
            return _make_request(payload, retry_count + 1)
        raise TikTokAPIError(f"TikTok API 오류 (code={code}): {msg}")

    return data


def _build_payload(
    data_level: str,
    metrics: list[str],
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    page_size: int = 1000,
) -> dict:
    payload = {
        "advertiser_id": TIKTOK_ADVERTISER_ID,
        "report_type": "BASIC",
        "data_level": data_level,
        "metrics": metrics,
        "start_date": start_date,
        "end_date": end_date,
        "page_size": page_size,
    }
    if dimensions:
        payload["dimensions"] = dimensions
    return payload


def _parse_metrics(row: dict) -> dict:
    metrics = row.get("metrics", {})
    dimensions = row.get("dimensions", {})
    result = {}

    for key, value in dimensions.items():
        result[key] = value

    for key, value in metrics.items():
        try:
            result[key] = float(value) if value not in (None, "", "None") else 0.0
        except (ValueError, TypeError):
            result[key] = 0.0

    return result


def get_account_report(date: str) -> dict:
    payload = _build_payload(
        data_level="AUCTION_ADVERTISER",
        metrics=ACCOUNT_METRICS,
        start_date=date,
        end_date=date,
        dimensions=["advertiser_id"],
    )
    data = _make_request(payload)
    rows = data.get("data", {}).get("list", [])
    if not rows:
        logger.warning(f"Account 리포트 데이터 없음: {date}")
        return {}
    return _parse_metrics(rows[0])


def get_campaign_report(date: str) -> list[dict]:
    payload = _build_payload(
        data_level="AUCTION_CAMPAIGN",
        metrics=CAMPAIGN_METRICS,
        start_date=date,
        end_date=date,
        dimensions=["campaign_id", "campaign_name"],
    )
    data = _make_request(payload)
    rows = data.get("data", {}).get("list", [])
    return [_parse_metrics(row) for row in rows]


def get_ad_report(date: str) -> list[dict]:
    payload = _build_payload(
        data_level="AUCTION_AD",
        metrics=AD_METRICS,
        start_date=date,
        end_date=date,
        dimensions=["ad_id", "ad_name", "campaign_id", "campaign_name"],
    )
    data = _make_request(payload)
    rows = data.get("data", {}).get("list", [])
    return [_parse_metrics(row) for row in rows]


def get_report_range(
    start_date: str,
    end_date: str,
    level: str = "AUCTION_ADVERTISER",
) -> list[dict]:
    if level == "AUCTION_ADVERTISER":
        metrics = ACCOUNT_METRICS
        dimensions = ["stat_time_day"]
    elif level == "AUCTION_CAMPAIGN":
        metrics = CAMPAIGN_METRICS
        dimensions = ["campaign_id", "campaign_name", "stat_time_day"]
    else:
        metrics = AD_METRICS
        dimensions = ["ad_id", "ad_name", "campaign_id", "campaign_name", "stat_time_day"]

    payload = _build_payload(
        data_level=level,
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
        dimensions=dimensions,
    )
    data = _make_request(payload)
    rows = data.get("data", {}).get("list", [])
    return [_parse_metrics(row) for row in rows]
