import sys
import logging
import traceback
from datetime import datetime, timedelta

from config import TOP_CAMPAIGNS_COUNT, TOP_CREATIVES_COUNT
from tiktok_client import TikTokAPIError, TikTokTokenExpiredError
from tiktok_client import (
    get_account_report,
    get_campaign_report,
    get_ad_report,
    get_report_range,
)
from data_processor import (
    calculate_daily_change,
    calculate_weekly_average,
    compare_with_weekly,
    rank_campaigns,
    rank_creatives,
    calculate_completion_rate,
    build_report_data,
)
from frequency_analyzer import (
    analyze_frequency_trend,
    get_campaign_frequency_ranking,
)
from anomaly_detector import (
    detect_account_anomalies,
    detect_campaign_actions,
    detect_creative_fatigue,
)
from insight_generator import generate_insight
from slack_sender import (
    build_header_block,
    build_summary_block,
    build_anomaly_block,
    build_campaign_ranking_block,
    build_action_alert_block,
    build_creative_ranking_block,
    build_frequency_block,
    build_insight_block,
    send_report,
    send_error_alert,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _get_dates():
    today = datetime.utcnow() + timedelta(hours=9)  # KST
    d1 = (today - timedelta(days=1)).strftime("%Y-%m-%d")  # 어제
    d2 = (today - timedelta(days=2)).strftime("%Y-%m-%d")  # 그제
    d8 = (today - timedelta(days=8)).strftime("%Y-%m-%d")  # 8일 전
    date_display = (today - timedelta(days=1)).strftime("%Y.%m.%d")
    return d1, d2, d8, date_display


def _build_campaign_7d_avg(campaign_7d_data: list[dict]) -> dict:
    by_campaign: dict[str, list[dict]] = {}
    for row in campaign_7d_data:
        cid = row.get("campaign_id", "")
        if cid not in by_campaign:
            by_campaign[cid] = []
        by_campaign[cid].append(row)

    avg_map = {}
    for cid, rows in by_campaign.items():
        n = len(rows)
        if n == 0:
            continue
        avg = {}
        metrics = ["spend", "impressions", "reach", "clicks", "ctr", "cpc", "cpm",
                    "conversion", "cost_per_conversion", "cost_per_result", "frequency"]
        for m in metrics:
            total = sum(r.get(m, 0.0) for r in rows)
            avg[f"{m}_avg"] = round(total / n, 2)
        avg_map[cid] = avg

    return avg_map


def _extract_frequency_trend(account_7d_data: list[dict]) -> list[float]:
    sorted_data = sorted(account_7d_data, key=lambda x: x.get("stat_time_day", ""))
    return [day.get("frequency", 0.0) for day in sorted_data]


def _build_campaign_avg_frequency(campaigns_today: list[dict]) -> dict:
    result = {}
    for c in campaigns_today:
        cid = c.get("campaign_id", "")
        result[cid] = c.get("frequency", 0.0)
    return result


def main():
    logger.info("TikTok Daily Report Bot 시작")

    try:
        # 1. 날짜 계산
        d1, d2, d8, date_display = _get_dates()
        logger.info(f"리포트 대상: {d1} (전일: {d2}, 7일 범위: {d8}~{d1})")

        # 2. TikTok API 데이터 수집
        logger.info("TikTok API 데이터 수집 중...")

        account_d1 = get_account_report(d1)
        account_d2 = get_account_report(d2)
        campaigns_d1 = get_campaign_report(d1)
        campaigns_d2 = get_campaign_report(d2)
        ads_d1 = get_ad_report(d1)

        # 7일 범위 데이터
        account_7d = get_report_range(d8, d1, level="AUCTION_ADVERTISER")
        campaign_7d = get_report_range(d8, d1, level="AUCTION_CAMPAIGN")
        ad_7d = get_report_range(d8, d1, level="AUCTION_AD")

        logger.info("데이터 수집 완료")

        # 3. 데이터 가공
        logger.info("데이터 가공 중...")

        # Frequency 7일 추이
        frequency_trend_7d = _extract_frequency_trend(account_7d)
        frequency_trend_data = analyze_frequency_trend(frequency_trend_7d)

        # 리포트 기본 데이터
        report_data = build_report_data(
            date=date_display,
            account_today=account_d1,
            account_yesterday=account_d2,
            weekly_account_data=account_7d,
            campaigns_today=campaigns_d1,
            ads_today=ads_d1,
            frequency_trend_7d=frequency_trend_7d,
        )

        # 4. Frequency 분석
        logger.info("Frequency 분석 중...")
        campaign_freq_ranking = get_campaign_frequency_ranking(campaigns_d1)

        frequency_data = {
            "account_frequency": account_d1.get("frequency", 0.0),
            "avg_7d": frequency_trend_data["avg"],
            "trend": frequency_trend_data,
            "campaign_ranking": campaign_freq_ranking,
        }

        # 5. 특이사항 감지
        logger.info("특이사항 감지 중...")

        weekly_avg = report_data["weekly_avg"]
        anomalies = detect_account_anomalies(account_d1, account_d2, weekly_avg)

        campaign_7d_avg = _build_campaign_7d_avg(campaign_7d)
        campaign_actions = detect_campaign_actions(campaigns_d1, campaigns_d2, campaign_7d_avg)

        campaign_avg_freq = _build_campaign_avg_frequency(campaigns_d1)
        creative_fatigue = detect_creative_fatigue(ads_d1, ad_7d, campaign_avg_freq)

        logger.info(f"특이사항: {len(anomalies)}건, 캠페인 액션: {len(campaign_actions)}건, 크리에이티브 피로도: {len(creative_fatigue)}건")

        # 6. Claude API 인사이트 생성
        logger.info("AI 인사이트 생성 중...")

        insight_input = {
            **report_data,
            "frequency_trend_data": frequency_trend_data,
            "anomalies": anomalies,
            "campaign_actions": campaign_actions,
            "creative_fatigue": creative_fatigue,
        }
        try:
            insight_text = generate_insight(insight_input)
            logger.info("인사이트 생성 완료")
        except Exception as e:
            logger.warning(f"AI 인사이트 생성 실패 (건너뜀): {e}")
            insight_text = ""

        # 7. Slack 메시지 조립
        logger.info("Slack 메시지 조립 중...")

        blocks = []
        blocks.append(build_header_block(date_display))
        blocks.extend(build_summary_block(report_data["account_summary"]))

        anomaly_blocks = build_anomaly_block(anomalies)
        if anomaly_blocks:
            blocks.extend(anomaly_blocks)

        blocks.extend(build_campaign_ranking_block(
            report_data["top_campaigns"], top_n=TOP_CAMPAIGNS_COUNT
        ))

        blocks.extend(build_action_alert_block(campaign_actions, creative_fatigue))

        blocks.extend(build_creative_ranking_block(
            report_data["top_creatives"], top_n=TOP_CREATIVES_COUNT
        ))

        blocks.extend(build_frequency_block(frequency_data))
        if insight_text and not insight_text.startswith("AI 인사이트 생성 실패"):
            blocks.extend(build_insight_block(insight_text))

        # 8. Slack 발송
        logger.info("Slack 리포트 발송 중...")
        success = send_report(blocks)

        if success:
            logger.info("리포트 발송 완료!")
        else:
            logger.error("리포트 발송 실패")
            sys.exit(1)

    except TikTokTokenExpiredError as e:
        logger.error(f"토큰 만료: {e}")
        send_error_alert(str(e))
        sys.exit(1)

    except TikTokAPIError as e:
        logger.error(f"TikTok API 오류: {e}")
        send_error_alert(f"TikTok API 오류:\n{e}")
        sys.exit(1)

    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"예상치 못한 오류:\n{error_detail}")
        send_error_alert(f"리포트 생성 중 오류 발생:\n{e}\n\n{error_detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
