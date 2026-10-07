"""The single typed state schema. Every value that moves between nodes lives here.

Nodes receive dependencies (page fetcher, MCP client, summariser) through the LangGraph
runtime context, but they never pass data to each other through it: anything a later node
reads was written into this schema by an earlier one.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Literal, TypedDict


class TerminalState(str, Enum):
    """Every run ends in exactly one of these. Declared upfront; nothing else is valid."""

    COMPLETE = "complete"  # record written, every ingredient has a food id
    COMPLETE_PARTIAL = "complete_partial"  # record written, >=1 ingredient unknown or without grams
    FAILED_FETCH = "failed_fetch"  # page could not be fetched from any source
    FAILED_PARSE = "failed_parse"  # page fetched but no schema.org Recipe / no ingredients found
    FAILED_VALIDATION = "failed_validation"  # record built but broke a dataset rule; not written


TERMINAL_STATES = tuple(t.value for t in TerminalState)

IngredientStatus = Literal["pending", "matched", "unknown"]
NutritionStatus = Literal["computed", "no_gram_weight", "no_food_id", "heading"]


class Terminal(TypedDict):
    state: str  # a TerminalState value
    reason: str


class PageProvenance(TypedDict):
    source: Literal["live", "snapshot"]
    fetched_url: str  # where the bytes actually came from
    original_sha256: str  # hash of the unsanitised page bytes
    sanitized: bool


class ParsedRecipe(TypedDict):
    recipe_id: str
    source_url: str
    title: str
    site: str
    category: list[str]
    cuisine: list[str]
    yield_text: str | None
    servings: int | None
    servings_unit: str | None
    ingredient_lines: list[str]
    section_headings: list[str]


class Attempt(TypedDict):
    attempt: int
    query: str
    strategy: str  # name | alias | head_noun | llm_alias
    outcome: str  # matched | no_candidates | rejected | tool_error
    detail: str


class Ingredient(TypedDict, total=False):
    index: int
    raw: str
    name: str  # normalised name used to build queries
    quantity: float | None
    unit: str | None
    size_word: str | None
    stated_grams: float | None  # mass written in the recipe itself, converted exactly
    status: IngredientStatus
    query_plan: list[dict]  # ordered queries: recipe wording, then aliases
    plan_index: int  # next query to try
    attempts: int
    queries_tried: list[str]
    attempt_log: list[Attempt]
    food_id: str | None
    food_description: str | None
    grams: float | None
    gram_basis: str | None  # how grams were obtained, always from the recipe or the food database
    nutrition_status: NutritionStatus
    nutrients: dict[str, float] | None  # contribution of this ingredient, not per 100 g
    unknown_reason: str | None


class Comment(TypedDict):
    comment_id: str
    text: str  # names, handles, emails, links already removed


class Claim(TypedDict):
    text: str
    count: int
    comment_ids: list[str]


class CookNotes(TypedDict):
    status: Literal["produced", "skipped_below_threshold"]
    comment_count: int
    threshold: int
    claims: list[Claim]
    card: str | None
    word_count: int
    backend: str | None


class Validation(TypedDict):
    ok: bool
    errors: list[str]


class RecipeState(TypedDict, total=False):
    # input
    url: str
    # fetch
    raw_page: str  # sanitised page: JSON-LD + comment texts only, no commenter identity
    page_provenance: PageProvenance
    # parse
    recipe: ParsedRecipe
    ingredients: list[Ingredient]
    # nutrition loop
    retry_round: int
    nutrition: dict
    # comments
    comments: list[Comment]
    cook_notes: CookNotes
    # end
    validation: Validation
    record: dict
    terminal: Terminal
    written_to: str
    node_path: Annotated[list[str], operator.add]
