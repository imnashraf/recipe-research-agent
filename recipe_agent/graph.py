"""The LangGraph state machine.

    START -> fetch -> parse_recipe -> parse_ingredients -> match_nutrition
    match_nutrition --(retry)--> match_nutrition          # conditional edge 1, capped per ingredient
                    --(give_up)--> mark_unknown -> gather_comments
                    --(done)--> gather_comments
    gather_comments --(summarise)--> summarise -> validate   # conditional edge 2
                    --(skip)--> validate
    validate -> write -> END

A fetch or parse failure records its terminal state; the remaining nodes see it in state and
pass through (logged as "<node>:skipped") so validate/write still record the run. That keeps
exactly two conditional edges, both reading only state.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import nodes
from .nodes import AgentDeps
from .state import RecipeState

NODE_ORDER = (
    "fetch", "parse_recipe", "parse_ingredients", "match_nutrition", "mark_unknown",
    "gather_comments", "summarise", "validate", "write",
)


def build_graph(checkpointer=None):
    g = StateGraph(RecipeState, context_schema=AgentDeps)
    for name in NODE_ORDER:
        g.add_node(name, getattr(nodes, name))
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "parse_recipe")
    g.add_edge("parse_recipe", "parse_ingredients")
    g.add_edge("parse_ingredients", "match_nutrition")
    g.add_conditional_edges(
        "match_nutrition",
        nodes.route_after_match,
        {"retry": "match_nutrition", "give_up": "mark_unknown", "done": "gather_comments"},
    )
    g.add_edge("mark_unknown", "gather_comments")
    g.add_conditional_edges(
        "gather_comments",
        nodes.route_after_comments,
        {"summarise": "summarise", "skip": "validate"},
    )
    g.add_edge("summarise", "validate")
    g.add_edge("validate", "write")
    g.add_edge("write", END)
    return g.compile(checkpointer=checkpointer)
