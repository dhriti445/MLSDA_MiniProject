"""D6: stand-in for the LLM provider. Fixed response after a realistic delay; measures OUR system, not provider limits."""
import asyncio, os
from fastapi import FastAPI

app = FastAPI()
DELAY = float(os.environ.get("STUB_DELAY_MS", "800")) / 1000
CONTENT = os.environ.get("STUB_CONTENT", '{"article": "vacuum flask", "materials": ["steel", "plastics"]}')


@app.post("/v1/chat/completions")
async def chat(_: dict):
    await asyncio.sleep(DELAY)
    return {"choices": [{"message": {"role": "assistant", "content": CONTENT}}], "usage": {"prompt_tokens": 300, "completion_tokens": 40}}


@app.get("/health")
def health(): return {"status": "ok"}
