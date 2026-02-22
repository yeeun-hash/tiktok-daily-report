import json
import logging
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 10년 경력의 퍼포먼스 마케팅 전문가입니다.
TikTok 광고 데이터를 분석하여 실행 가능한 인사이트를 한국어로 제공합니다.

규칙:
1. 데이터에 근거한 분석만 제공하세요. 추측은 최소화하세요.
2. 각 인사이트는 "현상 → 원인 추정 → 액션 제안" 구조로 작성하세요.
3. 가장 임팩트가 큰 변화부터 우선순위로 언급하세요.
4. Frequency(1인당 노출 빈도)가 높을 경우 반드시 언급하세요.
5. 크리에이티브 성과 변화가 있으면 소재 전략 제안을 포함하세요.
6. 3~5개 핵심 포인트, 각 포인트는 2~3문장으로 간결하게 작성하세요.
7. 전문 용어와 함께 쉬운 설명을 병기하세요."""

USER_PROMPT_TEMPLATE = """아래는 TikTok 광고 계정의 일일 성과 데이터입니다. 분석해주세요.

## 날짜: {date}

## 계정 전체 요약
{account_summary_json}

## 전일 대비 변화
{daily_change_json}

## 7일 평균 대비 비교
{weekly_comparison_json}

## Frequency(1인당 노출 빈도)
- 어제: {frequency_yesterday}
- 7일 평균: {frequency_7d_avg}
- 추이: {frequency_trend}

## 캠페인별 성과
{campaign_data_json}

## 특이사항 감지 결과
{anomalies_json}

## 크리에이티브 성과 (상위 10개)
{creative_data_json}

## 크리에이티브 피로도 감지 결과
{creative_fatigue_json}

위 데이터를 기반으로:
1. 가장 주목할 만한 성과 변화와 원인을 분석해주세요.
2. Frequency 상태를 평가하고, 오디언스 피로도 관련 조언을 주세요.
3. 성과가 하락한 캠페인/크리에이티브에 대해 구체적인 개선 액션을 제안해주세요.
4. 성과가 좋은 캠페인/크리에이티브가 있다면, 스케일업 방안을 제안해주세요.
5. 오늘 마케터가 가장 먼저 해야 할 액션 1가지를 추천해주세요."""


def generate_insight(report_data: dict) -> str:
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        account_summary = report_data.get("account_summary", {})
        frequency_trend = report_data.get("frequency_trend_data", {})

        user_prompt = USER_PROMPT_TEMPLATE.format(
            date=report_data.get("date", ""),
            account_summary_json=json.dumps(account_summary, ensure_ascii=False, indent=2),
            daily_change_json=json.dumps(report_data.get("daily_change", {}), ensure_ascii=False, indent=2),
            weekly_comparison_json=json.dumps(report_data.get("weekly_comparison", {}), ensure_ascii=False, indent=2),
            frequency_yesterday=account_summary.get("frequency", 0),
            frequency_7d_avg=frequency_trend.get("avg", 0),
            frequency_trend=frequency_trend.get("message", "데이터 없음"),
            campaign_data_json=json.dumps(report_data.get("top_campaigns", []), ensure_ascii=False, indent=2),
            anomalies_json=json.dumps(report_data.get("anomalies", []), ensure_ascii=False, indent=2),
            creative_data_json=json.dumps(report_data.get("top_creatives", [])[:10], ensure_ascii=False, indent=2),
            creative_fatigue_json=json.dumps(report_data.get("creative_fatigue", []), ensure_ascii=False, indent=2),
        )

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            temperature=CLAUDE_TEMPERATURE,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text

    except anthropic.APIError as e:
        logger.error(f"Claude API 오류: {e}")
        return f"AI 인사이트 생성 실패: {e}"
    except Exception as e:
        logger.error(f"인사이트 생성 중 오류: {e}")
        return f"AI 인사이트 생성 실패: {e}"
