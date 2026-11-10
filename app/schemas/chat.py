"""API and LLM output schemas."""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Intent = Literal["info", "price", "comparison", "medical_advice", "booking", "quote_request", "greeting", "out_of_scope"]


class RouterOut(BaseModel):
    need: str = Field(description="What the user actually wants to know or do, in one short English sentence")
    standalone_query: str = Field(description="The main need as one self-contained English search query")
    extra_queries: list[str] = Field(description="0-2 more English search queries, one per other part of a multi-part question")
    assumption: str = Field(description="The default you assumed for a vague question (e.g. 'ITC cancer packages'); empty if none")
    intent: Intent
    language: str = Field(description="Language the user wrote in, e.g. English, Spanish, Arabic")
    direct_reply: str = Field(description="Only for greeting/booking/quote_request/out_of_scope: a short reply in the user's language. Empty otherwise.")


class AnswerOut(BaseModel):
    # NOTE: field order is generation order; citations come before the streamed answer text
    answerable: bool = Field(description="True only if the context contains the facts needed to answer")
    cited_ids: list[str] = Field(description="Ids of the context chunks the answer uses")
    medical_topic: bool = Field(description="True if the answer discusses treatments, risks, eligibility or health outcomes")
    answer: str
    followups: list[str] = Field(description="2-3 short follow-up questions this user is likely to ask next, answerable from the context")


class ClaimVerdict(BaseModel):
    claim: str
    supported: bool = Field(description="True if the sources state or directly imply it")


class ClaimCheck(BaseModel):
    claims: list[ClaimVerdict] = Field(description="Each specific factual claim in the answer with its verdict")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    channel: Literal["text", "voice"] = "text"


class Source(BaseModel):
    title: str
    url: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = []
    answered: bool
    intent: str
    show_lead_form: bool = False
    followups: list[str] = []


class LeadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    question: str = Field(default="", max_length=1000)
