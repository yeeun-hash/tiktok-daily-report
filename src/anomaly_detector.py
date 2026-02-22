from config import THRESHOLDS
from data_processor import _safe_change_pct, calculate_completion_rate


# 지표별 설정: (label, 비용계열 여부)
# 비용 계열: 상승=부정, 하락=긍정  /  효율 계열: 상승=긍정, 하락=부정
METRIC_CONFIG = {
    "spend": ("비용", True),
    "ctr": ("CTR", False),
    "cpc": ("CPC", True),
    "conversion": ("전환수", False),
    "cost_per_conversion": ("전환단가", True),
    "frequency": ("Frequency", True),
}


def _format_value(metric: str, value: float) -> str:
    if metric in ("spend", "cpc", "cost_per_conversion", "cpm", "cost_per_result"):
        return f"\u20a9{int(value):,}"
    if metric in ("ctr",):
        return f"{value:.2f}%"
    if metric == "frequency":
        return f"{value:.1f}\ud68c"
    return f"{int(value):,}"


def detect_account_anomalies(today: dict, yesterday: dict, weekly_avg: dict) -> list[dict]:
    anomalies = []

    # 전일 대비 비교 항목
    daily_checks = [
        ("spend", "spend_surge", "spend_save"),
        ("ctr", "ctr_rise", "ctr_drop"),
        ("cpc", "cpc_surge", "cpc_save"),
        ("conversion", "conversion_rise", "conversion_drop"),
        ("cost_per_conversion", "conversion_cost_surge", "conversion_cost_save"),
    ]

    for metric, surge_key, save_key in daily_checks:
        t_val = today.get(metric, 0.0)
        y_val = yesterday.get(metric, 0.0)
        if y_val == 0 and t_val == 0:
            continue

        change_pct = _safe_change_pct(t_val, y_val)
        change_ratio = change_pct / 100
        label, is_cost = METRIC_CONFIG.get(metric, (metric, False))

        # 급증 감지
        if change_ratio >= THRESHOLDS[surge_key]:
            anomaly_type = "negative" if is_cost else "positive"
            anomalies.append({
                "type": anomaly_type,
                "metric": metric,
                "label": label,
                "yesterday_value": y_val,
                "today_value": t_val,
                "change_pct": change_pct,
                "severity": "warning",
                "message": f"{label}이(가) 전일 대비 {change_pct:+.1f}% 변동 ({_format_value(metric, y_val)} \u2192 {_format_value(metric, t_val)})",
            })

        # 급감 감지
        if change_ratio <= THRESHOLDS[save_key]:
            anomaly_type = "positive" if is_cost else "negative"
            anomalies.append({
                "type": anomaly_type,
                "metric": metric,
                "label": label,
                "yesterday_value": y_val,
                "today_value": t_val,
                "change_pct": change_pct,
                "severity": "warning",
                "message": f"{label}이(가) 전일 대비 {change_pct:+.1f}% 변동 ({_format_value(metric, y_val)} \u2192 {_format_value(metric, t_val)})",
            })

    # Frequency 절대값 감지
    freq = today.get("frequency", 0.0)
    if freq >= THRESHOLDS["frequency_critical"]:
        anomalies.append({
            "type": "negative",
            "metric": "frequency",
            "label": "Frequency",
            "yesterday_value": yesterday.get("frequency", 0.0),
            "today_value": freq,
            "change_pct": 0,
            "severity": "critical",
            "message": f"Frequency {freq:.1f} \u2014 \uc624\ub514\uc5b8\uc2a4 \ud53c\ub85c\ub3c4 \uacbd\uace0! \uc989\uc2dc \uc870\uce58 \ud544\uc694",
        })
    elif freq >= THRESHOLDS["frequency_warning"]:
        anomalies.append({
            "type": "negative",
            "metric": "frequency",
            "label": "Frequency",
            "yesterday_value": yesterday.get("frequency", 0.0),
            "today_value": freq,
            "change_pct": 0,
            "severity": "warning",
            "message": f"Frequency {freq:.1f} \u2014 \uc624\ub514\uc5b8\uc2a4 \ud53c\ub85c\ub3c4 \uc8fc\uc758",
        })

    # 완시청률 7일 평균 대비 (계정 레벨에서는 생략 — Ad 레벨에서 처리)

    return anomalies


def detect_campaign_actions(
    campaigns_today: list[dict],
    campaigns_yesterday: list[dict],
    campaigns_7d_avg: dict,
) -> list[dict]:
    actions = []
    yesterday_map = {c.get("campaign_id"): c for c in campaigns_yesterday}

    for camp in campaigns_today:
        cid = camp.get("campaign_id", "")
        cname = camp.get("campaign_name", cid)
        issues = []

        avg = campaigns_7d_avg.get(cid, {})

        # CTR 7일 평균 대비 하락
        ctr_today = camp.get("ctr", 0.0)
        ctr_avg = avg.get("ctr_avg", 0.0)
        if ctr_avg > 0:
            ctr_change = _safe_change_pct(ctr_today, ctr_avg)
            if ctr_change / 100 <= THRESHOLDS["campaign_ctr_drop_7d"]:
                issues.append({
                    "metric": "ctr",
                    "label": "CTR",
                    "description": f"CTR이 7일 평균 대비 {ctr_change:+.1f}% 하락 ({ctr_avg:.2f}% \u2192 {ctr_today:.2f}%)",
                    "action": "소재 피로도 점검 또는 타겟 오디언스 재검토 권장",
                    "severity": "warning",
                })

        # 전환단가 7일 평균 대비 상승
        cpa_today = camp.get("cost_per_conversion", 0.0)
        cpa_avg = avg.get("cost_per_conversion_avg", 0.0)
        if cpa_avg > 0:
            cpa_change = _safe_change_pct(cpa_today, cpa_avg)
            if cpa_change / 100 >= THRESHOLDS["campaign_cpa_surge_7d"]:
                issues.append({
                    "metric": "cost_per_conversion",
                    "label": "전환단가",
                    "description": f"전환단가가 7일 평균 대비 {cpa_change:+.1f}% 상승 (\u20a9{int(cpa_avg):,} \u2192 \u20a9{int(cpa_today):,})",
                    "action": "입찰 전략 변경 또는 전환 최적화 이벤트 재설정 검토",
                    "severity": "warning",
                })

        # 전환수 7일 평균 대비 감소
        conv_today = camp.get("conversion", 0.0)
        conv_avg = avg.get("conversions_avg", 0.0)
        if conv_avg > 0:
            conv_change = _safe_change_pct(conv_today, conv_avg)
            if conv_change / 100 <= THRESHOLDS["campaign_conversion_drop_7d"]:
                issues.append({
                    "metric": "conversion",
                    "label": "전환수",
                    "description": f"전환수가 7일 평균 대비 {conv_change:+.1f}% 감소 ({int(conv_avg)} \u2192 {int(conv_today)})",
                    "action": "예산 소진, 소재 리뷰 상태, 오디언스 포화도 확인",
                    "severity": "warning",
                })

        # CPC 7일 평균 대비 상승
        cpc_today = camp.get("cpc", 0.0)
        cpc_avg = avg.get("cpc_avg", 0.0)
        if cpc_avg > 0:
            cpc_change = _safe_change_pct(cpc_today, cpc_avg)
            if cpc_change / 100 >= THRESHOLDS["campaign_cpc_surge_7d"]:
                issues.append({
                    "metric": "cpc",
                    "label": "CPC",
                    "description": f"CPC가 7일 평균 대비 {cpc_change:+.1f}% 상승 (\u20a9{int(cpc_avg):,} \u2192 \u20a9{int(cpc_today):,})",
                    "action": "경쟁 심화 가능성. 타겟 확장 또는 소재 변경 권장",
                    "severity": "warning",
                })

        # Frequency 5.0 이상
        freq = camp.get("frequency", 0.0)
        if freq >= THRESHOLDS["frequency_critical"]:
            issues.append({
                "metric": "frequency",
                "label": "Frequency",
                "description": f"Frequency {freq:.1f} \u2014 \uc624\ub514\uc5b8\uc2a4 \ud3ec\ud654",
                "action": "오디언스 피로도 높음. 타겟 확장 또는 소재 교체 시급",
                "severity": "critical",
            })

        if issues:
            actions.append({
                "campaign_id": cid,
                "campaign_name": cname,
                "issues": issues,
            })

    return actions


def detect_creative_fatigue(
    ads_today: list[dict],
    ads_history: list[dict],
    campaign_avg_frequency: dict,
) -> list[dict]:
    fatigue_list = []

    # ads_history를 ad_id별로 그룹핑 (날짜순)
    history_by_ad: dict[str, list[dict]] = {}
    for ad in ads_history:
        aid = ad.get("ad_id", "")
        if aid not in history_by_ad:
            history_by_ad[aid] = []
        history_by_ad[aid].append(ad)

    for ad in ads_today:
        aid = ad.get("ad_id", "")
        aname = ad.get("ad_name", aid)
        cname = ad.get("campaign_name", "")
        cid = ad.get("campaign_id", "")
        issues = []

        history = history_by_ad.get(aid, [])
        history_sorted = sorted(history, key=lambda x: x.get("stat_time_day", ""))

        # 완시청률 7일 평균 대비 하락
        if history:
            completion_rates = [calculate_completion_rate(h) for h in history]
            avg_cr = sum(completion_rates) / len(completion_rates) if completion_rates else 0
            today_cr = calculate_completion_rate(ad)

            if avg_cr > 0:
                cr_change = _safe_change_pct(today_cr, avg_cr)
                if cr_change / 100 <= THRESHOLDS["creative_vtr_drop"]:
                    issues.append({
                        "metric": "completion_rate",
                        "label": "완시청률",
                        "description": f"완시청률이 7일 평균 대비 {cr_change:+.1f}% 하락 ({avg_cr:.1f}% \u2192 {today_cr:.1f}%)",
                        "action": "영상 도입부(Hook)가 약해졌을 가능성. 신규 소재 테스트 권장",
                        "severity": "warning",
                    })

        # CTR 3일 연속 하락
        if len(history_sorted) >= THRESHOLDS["consecutive_decline_days"]:
            recent_ctrs = [h.get("ctr", 0.0) for h in history_sorted[-(THRESHOLDS["consecutive_decline_days"]):]]
            # 오늘 값 추가
            recent_ctrs.append(ad.get("ctr", 0.0))
            if _detect_consecutive_decline(recent_ctrs[-THRESHOLDS["consecutive_decline_days"]:]):
                vals = " \u2192 ".join(f"{v:.1f}%" for v in recent_ctrs[-THRESHOLDS["consecutive_decline_days"]:])
                issues.append({
                    "metric": "ctr_trend",
                    "label": "CTR 추세",
                    "description": f"CTR {THRESHOLDS['consecutive_decline_days']}일 연속 하락 ({vals})",
                    "action": "소재 피로도 진행 중. 썸네일/CTA 변경 또는 신규 소재 투입",
                    "severity": "critical",
                })

        # CPC 3일 연속 상승
        if len(history_sorted) >= THRESHOLDS["consecutive_decline_days"]:
            recent_cpcs = [h.get("cpc", 0.0) for h in history_sorted[-(THRESHOLDS["consecutive_decline_days"]):]]
            recent_cpcs.append(ad.get("cpc", 0.0))
            if _detect_consecutive_increase(recent_cpcs[-THRESHOLDS["consecutive_decline_days"]:]):
                vals = " \u2192 ".join(f"\u20a9{int(v):,}" for v in recent_cpcs[-THRESHOLDS["consecutive_decline_days"]:])
                issues.append({
                    "metric": "cpc_trend",
                    "label": "CPC 추세",
                    "description": f"CPC {THRESHOLDS['consecutive_decline_days']}일 연속 상승 ({vals})",
                    "action": "소재 효율 저하. A/B 테스트로 고효율 소재 발굴 필요",
                    "severity": "warning",
                })

        # Frequency가 캠페인 평균의 1.5배 이상
        # Ad 레벨에서는 reach가 없을 수 있으므로 impressions 기반 추정
        camp_avg_freq = campaign_avg_frequency.get(cid, 0.0)
        ad_impressions = ad.get("impressions", 0)
        # Ad 레벨 frequency는 직접 계산 불가 (reach 없음), 캠페인 평균과 비교만
        if camp_avg_freq > 0 and ad_impressions > 0:
            # 캠페인 내 광고 비중이 높으면 피로도 가능성 표시
            pass  # Ad 레벨에서 개별 frequency는 TikTok API에서 제공하지 않음

        if issues:
            fatigue_list.append({
                "ad_id": aid,
                "ad_name": aname,
                "campaign_name": cname,
                "issues": issues,
            })

    return fatigue_list


def _detect_consecutive_decline(values: list[float], days: int = 3) -> bool:
    if len(values) < days:
        return False
    return all(values[i] > values[i + 1] for i in range(len(values) - 1))


def _detect_consecutive_increase(values: list[float], days: int = 3) -> bool:
    if len(values) < days:
        return False
    return all(values[i] < values[i + 1] for i in range(len(values) - 1))
