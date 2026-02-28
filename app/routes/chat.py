import asyncio, json, uuid, time, traceback
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from app.agent import run_agent

router = APIRouter()

# Rate limiter: 15 req/min per IP
_hits: dict[str, list[float]] = defaultdict(list)


def _allowed(ip: str, limit=15, window=60) -> bool:
    now = time.time()
    _hits[ip] = [t for t in _hits[ip] if now - t < window]
    if len(_hits[ip]) >= limit:
        return False
    _hits[ip].append(now)
    return True


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    if not _allowed(request.client.host):
        raise HTTPException(429, "Rate limited. Try again in a minute.")
    try:
        out = await asyncio.to_thread(run_agent, req.message, req.session_id)
        return {"response": out, "session_id": req.session_id}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, str(e))


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    if not _allowed(request.client.host):
        async def limited():
            yield {"event": "message", "data": json.dumps({"chunk": "⚠️ Rate limited. Wait a minute."})}
            yield {"event": "done", "data": json.dumps({"session_id": req.session_id})}
        return EventSourceResponse(limited())

    async def stream():
        try:
            out = await asyncio.to_thread(run_agent, req.message, req.session_id)
            for i in range(0, len(out), 20):
                yield {"event": "message", "data": json.dumps({"chunk": out[i:i+20]})}
                await asyncio.sleep(0.015)
            yield {"event": "done", "data": json.dumps({"session_id": req.session_id})}
        except Exception as e:
            traceback.print_exc()
            yield {"event": "message", "data": json.dumps({"chunk": f"⚠️ Error: {e}"})}
            yield {"event": "done", "data": json.dumps({"session_id": req.session_id})}

    return EventSourceResponse(stream())
