import os
from dotenv import load_dotenv

load_dotenv()

# TikTok Marketing API
TIKTOK_APP_ID = os.getenv("TIKTOK_APP_ID", "")
TIKTOK_SECRET = os.getenv("TIKTOK_SECRET", "")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_ADVERTISER_ID = os.getenv("TIKTOK_ADVERTISER_ID", "")

# Slack
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Anthropic (Claude API)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# TikTok API Base URL
TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"

# 특이사항 감지 임계값
THRESHOLDS = {
    "spend_surge": 0.30,
    "spend_save": -0.20,
    "ctr_drop": -0.20,
    "ctr_rise": 0.20,
    "cpc_surge": 0.30,
    "cpc_save": -0.20,
    "conversion_drop": -0.30,
    "conversion_rise": 0.30,
    "conversion_cost_surge": 0.30,
    "conversion_cost_save": -0.20,
    "frequency_warning": 3.0,
    "frequency_critical": 5.0,
    "creative_vtr_drop": -0.30,
    "creative_vtr_rise": 0.30,
    "campaign_ctr_drop_7d": -0.30,
    "campaign_cpa_surge_7d": 0.40,
    "campaign_conversion_drop_7d": -0.50,
    "campaign_cpc_surge_7d": 0.40,
    "consecutive_decline_days": 3,
}

# Claude API 설정
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_MAX_TOKENS = 1500
CLAUDE_TEMPERATURE = 0.3

# 리포트 설정
TOP_CAMPAIGNS_COUNT = 5
TOP_CREATIVES_COUNT = 5
