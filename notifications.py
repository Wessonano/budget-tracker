"""Discord webhook notifications for budget alerts."""

import logging
import os

import aiohttp

log = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_BUDGET", "")


async def check_and_send_alerts(budgets_with_spending: list[dict]):
    """Check budgets and send Discord alerts for 80% and 100% thresholds.

    budgets_with_spending: output of get_budgets_with_spending()
    Each dict has: category_name, category_icon, spent, amount_max, percent
    """
    if not WEBHOOK_URL:
        log.debug("No DISCORD_WEBHOOK_BUDGET configured, skipping alerts")
        return

    alerts = []
    for b in budgets_with_spending:
        pct = b["percent"]
        if pct >= 100:
            alerts.append({"budget": b, "level": "critical"})
        elif pct >= 80:
            alerts.append({"budget": b, "level": "warning"})

    if not alerts:
        return

    for alert in alerts:
        await _send_alert(alert["budget"], alert["level"])


async def _send_alert(budget: dict, level: str):
    """Send a single budget alert to Discord."""
    icon = budget["category_icon"]
    name = budget["category_name"]
    spent = budget["spent"]
    limit = budget["amount_max"]
    pct = budget["percent"]

    if level == "critical":
        color = 0xF44336  # red
        title = "Budget depasse !"
        msg = "Tu as depasse ta limite !"
    else:
        color = 0xFF9800  # orange
        title = "Attention budget"
        msg = "Tu approches de ta limite !"

    embed = {
        "color": color,
        "title": f"{'🚨' if level == 'critical' else '⚠️'} {title}",
        "description": f"{icon} **{name}** : {spent:.2f}€ / {limit:.2f}€ ({pct:.0f}%)\n{msg}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(WEBHOOK_URL, json={"embeds": [embed]}) as resp:
                if resp.status == 204:
                    log.info(f"Alert sent: {name} at {pct:.0f}%")
                else:
                    text = await resp.text()
                    log.error(f"Discord webhook failed {resp.status}: {text}")
    except Exception as e:
        log.error(f"Discord webhook error: {e}")
