from langchain_core.tools import tool
from app.db import SyncMongo
from app.cache import RedisCache
from app.tools.coin_info import _find_in_trending, _find_coin_snapshot


@tool
def get_market_data(coin_name: str) -> str:
    """Fetch detailed market data for a coin including market cap, volume,
    supply, ATH, and 24h range. Accepts name, symbol, or abbreviation.
    """
    cache_key = RedisCache.make_key("market_data", coin_name.lower())
    cached = RedisCache.get(cache_key)
    if cached is not None:
        return cached

    # Try trending first
    coin = _find_in_trending(coin_name)
    if coin:
        result = (
            f"📊 {coin['name']} ({coin['symbol']})\n"
            f"🏆 Rank: #{coin['market_cap_rank']}\n"
            f"💰 Price: ${coin['price_usd']:.6f}\n"
            f"📈 24h: {coin['priceChangePercentage24hUsd']:.2f}%\n"
            f"🔥 Trending in Crypto Market"
        )
        RedisCache.set(cache_key, result, ttl=300)
        return result

    # Fallback to coin_snapshots
    snap = _find_coin_snapshot(coin_name)
    if snap:
        name = snap['coinId'].replace('-', ' ').title()
        result = (
            f"📊 {name}\n"
            f"🏆 Rank: #{snap.get('market_cap_rank', 'N/A')}\n"
            f"💰 Price: ${snap['current_price']:,.2f}\n"
            f"📈 24h: {snap.get('price_change_percentage_24h', 0):.2f}%\n"
            f"🔺 High: ${snap.get('high_24h', 0):,.2f}\n"
            f"🔻 Low: ${snap.get('low_24h', 0):,.2f}\n"
            f"💎 MCap: ${snap.get('market_cap', 0):,.0f}\n"
            f"📉 Volume: ${snap.get('total_volume', 0):,.0f}\n"
            f"🔄 Circulating: {snap.get('circulating_supply', 0):,.0f}\n"
            f"📦 Max Supply: {snap.get('max_supply', 'N/A')}\n"
            f"🏔️ ATH: ${snap.get('ath', 0):,.2f} ({snap.get('ath_change_percentage', 0):.1f}% from ATH)"
        )
        RedisCache.set(cache_key, result, ttl=300)
        return result

    return f"No market data found for '{coin_name}'."


@tool
def get_trending_coins() -> str:
    """Get the list of currently trending cryptocurrencies."""
    cache_key = RedisCache.make_key("trending", "all")
    cached = RedisCache.get(cache_key)
    if cached is not None:
        return cached

    db = SyncMongo.get_db()
    coins = list(db["trending_coins"].find({}).sort("score", 1).limit(15))

    if not coins:
        return "No trending coins data available."

    lines = ["🔥 Trending Cryptocurrencies\n"]
    for c in coins:
        change = c.get("priceChangePercentage24hUsd", 0)
        emoji = "🟢" if change >= 0 else "🔴"
        lines.append(
            f"{emoji} {c['name']} ({c['symbol']}) — "
            f"${c['price_usd']:.6f} | "
            f"24h: {change:.2f}% | "
            f"Rank #{c['market_cap_rank']}"
        )

    result = "\n".join(lines)
    RedisCache.set(cache_key, result, ttl=300)
    return result


@tool
def get_market_overview() -> str:
    """Get today's overall crypto market summary: total market cap, volume,
    BTC dominance, and active cryptocurrencies.
    """
    cache_key = RedisCache.make_key("market_overview", "latest")
    cached = RedisCache.get(cache_key)
    if cached is not None:
        return cached

    db = SyncMongo.get_db()
    market = db["Market"].find_one(sort=[("lastUpdated", -1)])

    if not market:
        return "No market overview data available."

    result = (
        f"🌍 Crypto Market Overview\n\n"
        f"💰 Total Market Cap: ${market.get('totalMarketCapUsd', 0):,.0f}\n"
        f"📉 24h Volume: ${market.get('TotalVol', 0):,.0f}\n"
        f"₿ BTC Dominance: {market.get('btcCapPercentage', 0):.1f}%\n"
        f"🪙 Active Cryptos: {market.get('activeCrypto', 0):,}\n"
        f"🏦 Active Markets: {market.get('marketsCirculating', 0):,}"
    )

    RedisCache.set(cache_key, result, ttl=300)
    return result
