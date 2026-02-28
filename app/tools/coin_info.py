from langchain_core.tools import tool
from app.db import SyncMongo
from app.cache import RedisCache


def _find_in_trending(coin_name: str):
    """Search trending_coins by name, symbol, or _id."""
    db = SyncMongo.get_db()
    col = db["trending_coins"]
    slug = coin_name.lower().strip().replace(" ", "-")

    # Exact match
    query = {
        "$or": [
            {"name": {"$regex": f"^{coin_name}$", "$options": "i"}},
            {"symbol": {"$regex": f"^{coin_name}$", "$options": "i"}},
            {"_id": {"$regex": f"^{slug}$", "$options": "i"}},
        ]
    }
    coin = col.find_one(query)
    if coin:
        return coin

    # Partial match
    return col.find_one({
        "$or": [
            {"name": {"$regex": coin_name, "$options": "i"}},
            {"_id": {"$regex": slug, "$options": "i"}},
        ]
    })


def _find_coin_snapshot(coin_name: str):
    """Search coin_snapshots dynamically — handles names, slugs, symbols, and partial matches."""
    db = SyncMongo.get_db()
    col = db["coin_snapshots"]
    slug = coin_name.lower().strip().replace(" ", "-")

    # 1. Exact coinId match (latest snapshot)
    coin = col.find_one({"coinId": slug}, sort=[("last_updated", -1)])
    if coin:
        return coin

    # 2. Partial coinId match (e.g., "doge" matches "dogecoin", "shiba" matches "shiba-inu")
    coin = col.find_one(
        {"coinId": {"$regex": slug, "$options": "i"}},
        sort=[("last_updated", -1)]
    )
    if coin:
        return coin

    # 3. Try original name as-is
    original = coin_name.lower().replace(" ", "-")
    if original != slug:
        coin = col.find_one(
            {"coinId": {"$regex": original, "$options": "i"}},
            sort=[("last_updated", -1)]
        )
        if coin:
            return coin

    return None


@tool
def resolve_coin(query: str) -> str:
    """Search for a cryptocurrency by partial name, symbol, or abbreviation.
    Returns matching coin candidates. Use this when you're unsure which exact coin the user means,
    or when other tools return 'not found'. Examples: 'shiba', 'pepe', 'inu', 'trump'.
    """
    db = SyncMongo.get_db()
    col = db["coin_snapshots"]
    slug = query.lower().strip().replace(" ", "-")

    # Find distinct coinIds matching the query
    pipeline = [
        {"$match": {"coinId": {"$regex": slug, "$options": "i"}}},
        {"$sort": {"last_updated": -1}},
        {"$group": {
            "_id": "$coinId",
            "price": {"$first": "$current_price"},
            "rank": {"$first": "$market_cap_rank"},
            "change": {"$first": "$price_change_percentage_24h"},
        }},
        {"$sort": {"rank": 1}},
        {"$limit": 5},
    ]

    results = list(col.aggregate(pipeline))

    if not results:
        return f"No coins found matching '{query}'."

    lines = [f"🔍 Coins matching '{query}':\n"]
    for r in results:
        name = r["_id"].replace("-", " ").title()
        rank = r.get("rank", "?")
        price = r.get("price", 0)
        change = r.get("change", 0)
        lines.append(f"• {name} — ${price:,.4f} | Rank #{rank} | 24h: {change:.1f}%")

    return "\n".join(lines)


@tool
def get_coin_info(coin_name: str) -> str:
    """Look up info about a cryptocurrency. Accepts full names, symbols, abbreviations, or partial names.
    Examples: 'Bitcoin', 'BTC', 'doge', 'shiba', 'Solana'
    """
    cache_key = RedisCache.make_key("coin_info", coin_name.lower())
    cached = RedisCache.get(cache_key)
    if cached is not None:
        return cached

    # Try trending first
    coin = _find_in_trending(coin_name)
    if coin:
        result = (
            f"🪙 {coin['name']} ({coin['symbol']})\n"
            f"💰 Price: ${coin['price_usd']:.6f}\n"
            f"📊 Rank: #{coin['market_cap_rank']}\n"
            f"📈 24h: {coin['priceChangePercentage24hUsd']:.2f}%\n"
            f"🔥 Currently trending"
        )
        RedisCache.set(cache_key, result, ttl=300)
        return result

    # Fallback to coin_snapshots
    snap = _find_coin_snapshot(coin_name)
    if snap:
        name = snap['coinId'].replace('-', ' ').title()
        result = (
            f"🪙 {name}\n"
            f"💰 Price: ${snap['current_price']:,.2f}\n"
            f"📊 Rank: #{snap.get('market_cap_rank', 'N/A')}\n"
            f"📈 24h: {snap.get('price_change_percentage_24h', 0):.2f}%\n"
            f"🔺 High: ${snap.get('high_24h', 0):,.2f}\n"
            f"🔻 Low: ${snap.get('low_24h', 0):,.2f}\n"
            f"💎 MCap: ${snap.get('market_cap', 0):,.0f}"
        )
        RedisCache.set(cache_key, result, ttl=300)
        return result

    return f"No data found for '{coin_name}'."


@tool
def compare_coins(coin_a: str, coin_b: str) -> str:
    """Compare two cryptocurrencies side by side.
    Shows price, rank, 24h change, market cap, and volume for both.
    Use when user asks to compare coins, e.g. 'compare BTC and ETH'.
    """
    cache_key = RedisCache.make_key("compare", coin_a.lower(), coin_b.lower())
    cached = RedisCache.get(cache_key)
    if cached is not None:
        return cached

    def get_data(name):
        coin = _find_in_trending(name)
        if coin:
            return {
                "name": coin["name"], "symbol": coin["symbol"],
                "price": coin["price_usd"], "rank": coin["market_cap_rank"],
                "change": coin.get("priceChangePercentage24hUsd", 0),
                "mcap": coin.get("market_cap", 0), "vol": coin.get("total_volume", 0),
            }
        snap = _find_coin_snapshot(name)
        if snap:
            return {
                "name": snap["coinId"].replace("-", " ").title(), "symbol": snap["coinId"][:5].upper(),
                "price": snap["current_price"], "rank": snap.get("market_cap_rank", "?"),
                "change": snap.get("price_change_percentage_24h", 0),
                "mcap": snap.get("market_cap", 0), "vol": snap.get("total_volume", 0),
            }
        return None

    a = get_data(coin_a)
    b = get_data(coin_b)

    if not a:
        return f"Could not find data for '{coin_a}'."
    if not b:
        return f"Could not find data for '{coin_b}'."

    result = (
        f"⚔️ {a['name']} vs {b['name']}\n\n"
        f"{'Metric':<12} | {a['name']:<20} | {b['name']:<20}\n"
        f"{'-'*12} | {'-'*20} | {'-'*20}\n"
        f"{'Price':<12} | ${a['price']:>18,.2f} | ${b['price']:>18,.2f}\n"
        f"{'Rank':<12} | {'#' + str(a['rank']):>18} | {'#' + str(b['rank']):>18}\n"
        f"{'24h Change':<12} | {a['change']:>17.2f}% | {b['change']:>17.2f}%\n"
        f"{'Market Cap':<12} | ${a['mcap']:>17,.0f} | ${b['mcap']:>17,.0f}\n"
        f"{'Volume':<12} | ${a['vol']:>17,.0f} | ${b['vol']:>17,.0f}"
    )

    RedisCache.set(cache_key, result, ttl=300)
    return result
