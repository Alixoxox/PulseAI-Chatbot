from langchain_core.tools import tool
from app.db import SyncMongo
from app.cache import RedisCache
from app.tools.coin_info import _find_in_trending, _find_coin_snapshot


@tool
def get_risk_score(coin_name: str) -> str:
    """Risk assessment for a cryptocurrency. Analyzes rank, volatility, and price.
    Returns Low/Medium/High risk with reasoning.
    """
    cache_key = RedisCache.make_key("risk_score", coin_name.lower())
    cached = RedisCache.get(cache_key)
    if cached is not None:
        return cached

    # Try trending then snapshots
    coin = _find_in_trending(coin_name)
    if coin:
        name, rank = coin["name"], coin.get("market_cap_rank", 999)
        change_24h = abs(coin.get("priceChangePercentage24hUsd", 0))
        price = coin.get("price_usd", 0)
    else:
        snap = _find_coin_snapshot(coin_name)
        if not snap:
            return f"Cannot assess risk for '{coin_name}' — not found."
        name = snap["coinId"].replace("-", " ").title()
        rank = snap.get("market_cap_rank", 999)
        change_24h = abs(snap.get("price_change_percentage_24h", 0))
        price = snap.get("current_price", 0)

    risk_points = 0
    reasons = []

    if rank <= 20:
        risk_points += 1; reasons.append(f"✅ Strong rank (#{rank})")
    elif rank <= 100:
        risk_points += 2; reasons.append(f"⚠️ Mid-tier rank (#{rank})")
    else:
        risk_points += 3; reasons.append(f"🚨 Low rank (#{rank})")

    if change_24h <= 3:
        risk_points += 1; reasons.append(f"✅ Low volatility ({change_24h:.1f}%)")
    elif change_24h <= 10:
        risk_points += 2; reasons.append(f"⚠️ Moderate volatility ({change_24h:.1f}%)")
    else:
        risk_points += 3; reasons.append(f"🚨 High volatility ({change_24h:.1f}%)")

    if price >= 1.0:
        risk_points += 1; reasons.append(f"✅ Solid price (${price:,.2f})")
    elif price >= 0.01:
        risk_points += 2; reasons.append(f"⚠️ Low price (${price:.6f})")
    else:
        risk_points += 3; reasons.append(f"🚨 Micro price (${price:.8f})")

    if risk_points <= 4:
        level = "🟢 LOW RISK"
    elif risk_points <= 7:
        level = "🟡 MEDIUM RISK"
    else:
        level = "🔴 HIGH RISK"

    result = (
        f"⚖️ Risk — {name}\n"
        f"Overall: {level} ({risk_points}/9)\n\n"
        + "\n".join(reasons)
    )

    RedisCache.set(cache_key, result, ttl=300)
    return result
