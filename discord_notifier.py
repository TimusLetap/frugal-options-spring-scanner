"""
discord_notifier.py - Formatted Discord webhook notifications for
Gamma Squeeze, 0DTE Spring (<= $0.25), and Long/LEAPS Spring (<= $0.25) scans.

Highlights undervalued <= $0.25 entry prices, multi-layer volatility spring thesis,
and asymmetric payoff targets ($1.00 4x+ and $10.00+ 40x+ potential).
"""

import os
import logging
from datetime import date
from typing import List, Dict, Any, Optional
import requests
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_WEBHOOK = os.getenv(
    "DISCORD_GAMMA_WEBHOOK",
    os.getenv("DISCORD_WEBHOOK_URL", ""),
)


def post_discord_webhook(
    embeds: List[Dict[str, Any]],
    content: Optional[str] = None,
    webhook_url: Optional[str] = None,
    dry_run: bool = True,
) -> bool:
    """
    Send Discord webhook with embeds and content.
    If dry_run is True, prints payload to stdout instead of sending HTTP request.
    """
    url = webhook_url or DEFAULT_WEBHOOK

    payload: Dict[str, Any] = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds[:10]

    if dry_run:
        def _safe_print(text):
            try:
                print(text)
            except UnicodeEncodeError:
                print(str(text).encode("ascii", errors="backslashreplace").decode("ascii"))

        _safe_print("\n[DRY_RUN] Discord webhook payload (not sent to live channel):")
        if content:
            _safe_print(f"Content: {content}")
        for i, emb in enumerate(payload.get("embeds", [])):
            _safe_print(f"--- Embed {i+1}: {emb.get('title')} ---")
            _safe_print(f"Description:\n{emb.get('description', '')}")
            for f in emb.get("fields", []):
                _safe_print(f"  * {f.get('name')}: {f.get('value')}")
        return True

    if not url:
        logger.warning("No Discord webhook URL configured — set DISCORD_GAMMA_WEBHOOK or DISCORD_WEBHOOK_URL.")
        return False

    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if resp.status_code in [200, 204]:
            print("[OK] Successfully posted report to Discord.")
            return True
        else:
            logger.error(f"Discord webhook failed with status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Error posting Discord webhook: {e}")
        return False


def build_gamma_squeeze_embed(gamma_df: pd.DataFrame, top_n: int = 5) -> Optional[Dict[str, Any]]:
    """Build embed for top Gamma Squeeze & Volatility Coil candidates."""
    if gamma_df is None or gamma_df.empty:
        return None

    top = gamma_df.head(top_n)
    lines = []
    for _, row in top.iterrows():
        ticker = row.get("Ticker")
        score = row.get("Opportunity_Score")
        tier = row.get("Tier", "")
        spot = row.get("Spot_Price", 0)
        wall = row.get("Gamma_Wall_Strike", 0)
        dist = row.get("Distance_to_Wall_%", 0)
        exp = row.get("Expiration", "")
        coil_badge = " 🌀[COIL]" if row.get("Is_In_Coil") else ""
        lines.append(
            f"**${ticker}**{coil_badge} | Score: `{score}` ({tier})\n"
            f"• Spot: ${spot:.2f} ➔ Wall: ${wall:.2f} ({dist:+.1f}%) | Exp: {exp}\n"
        )

    return {
        "title": "⚡ Top Gamma Squeeze & Volatility Coil Candidates",
        "description": "\n".join(lines),
        "color": 0xFFA500,
        "footer": {"text": f"Scanned on {date.today().isoformat()} | Frugal Options Spring Scanner"},
    }


def build_0dte_embed(
    top_calls: pd.DataFrame,
    top_puts: pd.DataFrame,
    paper_status: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Build embeds for 0DTE Spring Scanner (<= $0.25 entry, $1.00 to $10.00+ targets):
    Separates Top-5 Calls and Top-5 Puts, includes spring/undervaluation metrics and paper-trading status.
    """
    embeds = []
    paper_badge = (
        f"⚠️ **PAPER TRADING ACTIVE** ({paper_status['distinct_cycles']}/{paper_status['required_cycles']} cycles)\n"
        f"*Win Rate: {paper_status['win_rate']}% | Expectancy: {paper_status['expectancy']} | Live Sizing Locked*"
        if not paper_status["approved_for_live_capital"]
        else f"✅ **VALIDATION COMPLETE**: Live Capital Sizing Approved (Expectancy: {paper_status['expectancy']})"
    )

    # 1. Top Calls Embed
    call_lines = []
    if top_calls is not None and not top_calls.empty:
        for idx, row in top_calls.head(5).iterrows():
            sym = row.get("Ticker")
            strike = row.get("Strike", 0)
            ask = row.get("Ask", 0)
            score = row.get("Opportunity_Score", 0)
            atr_dist = row.get("Dist_ATR_Units", 0)
            oi = row.get("Open_Interest", 0)
            vol_oi = row.get("Vol_OI_Ratio", 0)
            max_loss = row.get("Max_Loss_Held_To_Zero", 0)
            flag = row.get("Averaging_Down_Violation_Flag", "")
            catalyst = row.get("Catalyst_Flag", "None")
            val_3atr = row.get("Proj_Value_3ATR")
            val_5atr = row.get("Proj_Value_5ATR")
            spot_1 = row.get("Spot_For_1_00")
            spot_10 = row.get("Spot_For_10_00")

            payoff_line = ""
            if val_3atr is not None and spot_1 is not None:
                payoff_line = (
                    f"• Spring Targets: `$1.00` @ ${spot_1:.2f} | `$10.00` @ ${spot_10:.2f} "
                    f"(3xATR Val: `${val_3atr:.2f}`, 5xATR Val: `${val_5atr:.2f}`)\n"
                )

            call_lines.append(
                f"**#{idx+1} ${sym} {strike:.1f}C** | Score: `{score}` | Ask: `${ask:.2f}`\n"
                f"• Dist: `{atr_dist}x ATR` | OI: `{oi}` | Vol/OI: `{vol_oi}x` | Cat: {catalyst}\n"
                f"{payoff_line}"
                f"• Max Loss: `${max_loss:.2f}` | Rule: `{flag}`\n"
            )
    else:
        call_lines.append("_No qualifying <= $0.25 0DTE call spring setups found._")

    embeds.append({
        "title": "🟢 0DTE Scanner: Top 5 Calls (<= $0.25 Spring Setups)",
        "description": f"{paper_badge}\n\n" + "\n".join(call_lines),
        "color": 0x00FF00,
        "footer": {"text": "Frugal Cap: <= $0.25 ($25/contract) | Targets: $1.00 (4x+) & $10.00+ (40x+)"},
    })

    # 2. Top Puts Embed
    put_lines = []
    if top_puts is not None and not top_puts.empty:
        for idx, row in top_puts.head(5).iterrows():
            sym = row.get("Ticker")
            strike = row.get("Strike", 0)
            ask = row.get("Ask", 0)
            score = row.get("Opportunity_Score", 0)
            atr_dist = row.get("Dist_ATR_Units", 0)
            oi = row.get("Open_Interest", 0)
            vol_oi = row.get("Vol_OI_Ratio", 0)
            max_loss = row.get("Max_Loss_Held_To_Zero", 0)
            flag = row.get("Averaging_Down_Violation_Flag", "")
            catalyst = row.get("Catalyst_Flag", "None")
            val_3atr = row.get("Proj_Value_3ATR")
            val_5atr = row.get("Proj_Value_5ATR")
            spot_1 = row.get("Spot_For_1_00")
            spot_10 = row.get("Spot_For_10_00")

            payoff_line = ""
            if val_3atr is not None and spot_1 is not None:
                payoff_line = (
                    f"• Spring Targets: `$1.00` @ ${spot_1:.2f} | `$10.00` @ ${spot_10:.2f} "
                    f"(3xATR Val: `${val_3atr:.2f}`, 5xATR Val: `${val_5atr:.2f}`)\n"
                )

            put_lines.append(
                f"**#{idx+1} ${sym} {strike:.1f}P** | Score: `{score}` | Ask: `${ask:.2f}`\n"
                f"• Dist: `{atr_dist}x ATR` | OI: `{oi}` | Vol/OI: `{vol_oi}x` | Cat: {catalyst}\n"
                f"{payoff_line}"
                f"• Max Loss: `${max_loss:.2f}` | Rule: `{flag}`\n"
            )
    else:
        put_lines.append("_No qualifying <= $0.25 0DTE put spring setups found._")

    embeds.append({
        "title": "🔴 0DTE Scanner: Top 5 Puts (<= $0.25 Spring Setups)",
        "description": "\n".join(put_lines),
        "color": 0xFF0000,
        "footer": {"text": "Frugal Cap: <= $0.25 ($25/contract) | Targets: $1.00 (4x+) & $10.00+ (40x+)"},
    })

    return embeds


def build_leaps_embed(leaps_df: pd.DataFrame, top_n: int = 5) -> Optional[Dict[str, Any]]:
    """
    Build embed for Long & LEAPS Spring Scanner (<= $0.25 entry with $1.00 to $10.00+ potential).
    """
    if leaps_df is None or leaps_df.empty:
        return None

    lines = []
    for _, row in leaps_df.head(top_n).iterrows():
        sym = row.get("Ticker")
        opt_type = str(row.get("Type", "CALL"))[0]
        strike = row.get("Strike", 0)
        exp = row.get("Expiration")
        dte = row.get("DTE")
        delta = row.get("Delta_Est")
        mid = row.get("Ask") or row.get("Mid", 0)
        oi = row.get("Open_Interest", 0)
        be_move = row.get("Breakeven_Move_Pct", 0)
        val_3atr = row.get("Proj_Value_3ATR")
        val_5atr = row.get("Proj_Value_5ATR")
        tier = row.get("Payoff_Tier", "")

        delta_str = f"{delta:.2f}" if delta is not None and pd.notna(delta) else "N/A"
        spring_str = ""
        if val_3atr is not None and pd.notna(val_3atr):
            spring_str = f"• Spring Repricing: 3xATR `${val_3atr:.2f}` | 5xATR `${val_5atr:.2f}` ({tier})\n"

        lines.append(
            f"**${sym} ${strike:.1f}{opt_type}** Exp: `{exp}` ({dte}d) | Delta: `{delta_str}`\n"
            f"• Premium: `${mid:.2f}` | OI: `{oi}` | B/E Move: `{be_move:.1f}%`\n"
            f"{spring_str}"
        )

    return {
        "title": "🔭 Top Long & LEAPS Spring Candidates (<= $0.25 Entry ➔ $1.00 / $10.00+ Target)",
        "description": (
            "**Strategy Profile**: Undervalued long/swing options (≤ $0.25) on coiled-spring candidates targeting $1.00 (4x+) to $10.00+ (40x+).\n\n"
            + "\n".join(lines)
        ),
        "color": 0x3498DB,
        "footer": {"text": "Powered by Frugal Options Spring Scanner"},
    }


def dispatch_full_scan_report(
    gamma_df: Optional[pd.DataFrame] = None,
    zero_dte_calls: Optional[pd.DataFrame] = None,
    zero_dte_puts: Optional[pd.DataFrame] = None,
    leaps_df: Optional[pd.DataFrame] = None,
    paper_status: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
) -> bool:
    """Construct and dispatch all scan results to Discord."""
    embeds = []

    if gamma_df is not None and not gamma_df.empty:
        g_embed = build_gamma_squeeze_embed(gamma_df)
        if g_embed:
            embeds.append(g_embed)

    if (zero_dte_calls is not None and not zero_dte_calls.empty) or (
        zero_dte_puts is not None and not zero_dte_puts.empty
    ):
        if paper_status is None:
            paper_status = {
                "paper_trading_mode": True,
                "distinct_cycles": 0,
                "required_cycles": 12,
                "approved_for_live_capital": False,
                "win_rate": 0.0,
                "expectancy": 0.0,
            }
        z_embeds = build_0dte_embed(zero_dte_calls, zero_dte_puts, paper_status)
        embeds.extend(z_embeds)

    if leaps_df is not None and not leaps_df.empty:
        l_embed = build_leaps_embed(leaps_df)
        if l_embed:
            embeds.append(l_embed)

    if not embeds:
        logger.info("No scan results to report to Discord.")
        return True

    header = f"📊 **Frugal Options Spring Scanner Intelligence Briefing** (<= $0.25 ➔ $1.00 / $10.00+) — {date.today().strftime('%A, %b %d, %Y')}"

    print("\n" + "=" * 72)
    print(f"[SCAN SUMMARY] {date.today().isoformat()} | {len(embeds)} embed(s) ready to dispatch")
    for emb in embeds:
        print(f"  • {emb.get('title')}")
        desc = emb.get("description", "")
        print(f"    {desc[:500]}{'...' if len(desc) > 500 else ''}")
    print("=" * 72 + "\n")

    return post_discord_webhook(embeds=embeds, content=header, dry_run=dry_run)
