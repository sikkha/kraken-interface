from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    model: str | None = None
    context: str | None = None


class ChatResponse(BaseModel):
    ok: bool
    reply: str
    model: str
    source: str
    error: str | None = None
