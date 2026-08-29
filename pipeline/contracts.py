"""Shared, dependency-free schemas and artifact constants."""

from typing import Final, Literal, TypedDict

CATEGORY_VALUES: Final[tuple[str, ...]] = (
    "payment_issue",
    "account_verification",
    "login_access",
    "trading_problem",
    "other",
)
PRIORITY_VALUES: Final[tuple[str, ...]] = ("low", "medium", "high")
SENTIMENT_VALUES: Final[tuple[str, ...]] = ("neutral", "frustrated", "urgent")

Category = Literal[
    "payment_issue",
    "account_verification",
    "login_access",
    "trading_problem",
    "other",
]
Priority = Literal["low", "medium", "high"]
Sentiment = Literal["neutral", "frustrated", "urgent"]

TICKET_FIELDS: Final[tuple[str, ...]] = (
    "ticket_id",
    "subject",
    "message",
    "channel",
)
PREDICTION_FIELDS: Final[tuple[str, ...]] = (
    "ticket_id",
    "category",
    "priority",
    "sentiment",
    "reasoning",
)
LABEL_FIELDS: Final[tuple[str, ...]] = (
    "category",
    "priority",
    "sentiment",
)
ARTIFACT_NAMES: Final[tuple[str, ...]] = (
    "tickets.json",
    "labels.json",
    "validation.json",
    "metrics.json",
    "report.md",
    "llm_calls.jsonl",
)


class Ticket(TypedDict):
    ticket_id: str
    subject: str
    message: str
    channel: str


class Label(TypedDict):
    category: Category
    priority: Priority
    sentiment: Sentiment


class LabelRecord(Label):
    ticket_id: str


class Prediction(TypedDict):
    ticket_id: str
    category: Category
    priority: Priority
    sentiment: Sentiment
    reasoning: str
