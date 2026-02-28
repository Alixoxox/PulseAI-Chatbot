from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from groq import BadRequestError
from app.config import get_settings
from app.cache import RedisCache
from app.tools.coin_info import get_coin_info, resolve_coin, compare_coins
from app.tools.market_data import get_market_data, get_trending_coins, get_market_overview
from app.tools.risk_score import get_risk_score
import json
import logging

log = logging.getLogger(__name__)
SYSTEM_PROMPT = """You are PulseAI 🤖 — a crypto data analyst. You read risk scores, market trends, and on-chain data, then call it straight.

Rules:
- Answer ONLY what was asked. No unsolicited data.
- Greetings → short reply, no tools.
- Use tools only when user asks for data (price, market, risk, trending, etc.).
- If a coin isn't found, call resolve_coin first, then retry with the correct name.
- If user says "it" or "this coin", infer from conversation history.
- For buy/sell/suggest questions: pull get_trending_coins, get_risk_score, get_market_data — then give a DIRECT verdict ("Data says: Buy" / "Data says: Avoid") with one line of reasoning. Never refuse or say "I can't provide financial advice". You're reading and advising based on data.
- You may provide MetaData to the user if needed. 
- Max 5 lines per response unless user asks for detail.
- No emojis. Output in Markdown.
"""

TOOLS = [get_coin_info, get_market_data, get_trending_coins, get_market_overview, get_risk_score, resolve_coin, compare_coins]
TOOL_MAP = {t.name: t for t in TOOLS}

_llm_with_tools = None
MEMORY_TTL = 3600


def _mem_key(sid: str) -> str:
    return f"chat:mem:{sid}"


def load_history(sid: str) -> list:
    raw = RedisCache.get(_mem_key(sid))
    if not raw or not isinstance(raw, list):
        return []
    msgs = []
    for m in raw[-20:]:
        cls = HumanMessage if m["role"] == "human" else AIMessage
        msgs.append(cls(content=m["content"]))
    return msgs


def save_history(sid: str, user_msg: str, ai_msg: str):
    raw = RedisCache.get(_mem_key(sid)) or []
    raw += [{"role": "human", "content": user_msg}, {"role": "ai", "content": ai_msg}]
    RedisCache.set(_mem_key(sid), raw[-20:], ttl=MEMORY_TTL)


def get_agent(tools: bool = True):
    global _llm_with_tools
    s = get_settings()
    llm = ChatGroq(api_key=s.GROQ_API_KEY, model=s.GROQ_MODEL, temperature=0.3, max_tokens=2048)
    if not tools:
        return llm  # plain LLM, no tool binding — used as fallback
    if _llm_with_tools:
        return _llm_with_tools
    _llm_with_tools = llm.bind_tools(TOOLS)
    print(f"✅ Agent ready — {s.GROQ_MODEL}")
    return _llm_with_tools


def run_agent(user_message: str, session_id: str, max_iter: int = 5) -> str:
    llm = get_agent()
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + load_history(session_id)
    messages.append(HumanMessage(content=user_message))

    called = set()
    for _ in range(max_iter):
        try:
            resp = llm.invoke(messages)
        except BadRequestError as e:
            log.warning("Groq tool_use_failed, falling back to plain LLM: %s", e)
            # Groq rejects malformed tool-call history — start fresh without tools
            plain_llm = get_agent(tools=False)
            fallback_messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ]
            try:
                resp = plain_llm.invoke(fallback_messages)
            except Exception as e2:
                log.error("Plain LLM fallback also failed: %s", e2)
                return "Sorry, I hit a temporary issue. Please try again in a moment."
        messages.append(resp)
        if not resp.tool_calls:
            break
        for tc in resp.tool_calls:
            key = f"{tc['name']}:{json.dumps(tc['args'], sort_keys=True)}"
            if key in called:
                messages.append(ToolMessage(content="Already called.", tool_call_id=tc["id"]))
                continue
            called.add(key)
            fn = TOOL_MAP.get(tc["name"])
            try:
                result = fn.invoke(tc["args"]) if fn else f"Unknown tool: {tc['name']}"
            except Exception as e:
                result = f"Error: {e}"
            messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    output = messages[-1].content or ""

    # Fallback: raw tool data if LLM gave empty/short answer
    if len(output) < 30:
        data = [m.content for m in messages if isinstance(m, ToolMessage) and m.content != "Already called."]
        if data:
            output = "\n\n".join(data)

    save_history(session_id, user_message, output)
    return output
