"""Reduce a fetched recipe page to the PII-free subset the agent keeps in state.

What survives: canonical URL, schema.org Recipe JSON-LD (allow-listed keys only)
and the text of each comment with its comment id. What is dropped: commenter names, handles,
avatars, profile links, review/author blocks, scripts and markup. Commenter names are also
redacted from inside comment texts (people address each other by name in replies).
"""

from __future__ import annotations

import html as html_lib
import json
import re

from bs4 import BeautifulSoup, Tag

from .pii import expand_names, scrub_text

RECIPE_KEYS = (
    "@type", "name", "recipeIngredient", "recipeYield", "recipeCategory", "recipeCuisine", "url",
)

COMMENT_ID_RE = re.compile(r"^comment-(\d+)$")
CONTENT_CLASSES = (
    "comment-content", "comment-text", "wpd-comment-text", "ast-comment-content",
    "wp-block-comment-content", "wprm-comment-text",
)
AUTHOR_SELECTORS = (
    ".fn", ".comment-author", ".comment-author-name", ".wpd-comment-author",
    ".ast-comment-cite-wrap", ".comment-meta cite", ".says",
)



def _is_recipe(node: dict) -> bool:
    t = node.get("@type")
    return t == "Recipe" or (isinstance(t, list) and "Recipe" in t)


def _walk_jsonld(data) -> list[dict]:
    found = []
    if isinstance(data, list):
        for item in data:
            found.extend(_walk_jsonld(item))
    elif isinstance(data, dict):
        if _is_recipe(data):
            found.append(data)
        for key in ("@graph", "mainEntity"):
            if key in data:
                found.extend(_walk_jsonld(data[key]))
    return found


def extract_recipe_jsonld(soup: BeautifulSoup) -> list[dict]:
    recipes = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw, strict=False)
        except json.JSONDecodeError:
            continue
        for node in _walk_jsonld(data):
            recipes.append({k: node[k] for k in RECIPE_KEYS if k in node})
    return recipes


def _owner(el: Tag) -> Tag | None:
    for parent in el.parents:
        if isinstance(parent, Tag) and COMMENT_ID_RE.match(parent.get("id") or ""):
            return parent
    return None


def collect_names(soup: BeautifulSoup, jsonld_names: set[str]) -> set[str]:
    names: set[str] = set(jsonld_names)
    for sel in AUTHOR_SELECTORS:
        for el in soup.select(sel):
            txt = el.get_text(" ", strip=True)
            txt = re.sub(r"\bsays:?\s*$", "", txt).strip()
            if txt and len(txt) <= 60:
                names.add(txt)
    for el in soup.select("[aria-label^='Reply to'], [data-replyto]"):
        for attr in ("aria-label", "data-replyto"):
            m = re.match(r"Reply to (.+)", el.get(attr) or "")
            if m:
                names.add(m.group(1).strip())
    return expand_names(names)


def jsonld_person_names(soup: BeautifulSoup) -> set[str]:
    """Names of people appearing anywhere in JSON-LD (authors, reviewers), for redaction."""
    names: set[str] = set()

    def walk(x):
        if isinstance(x, dict):
            if x.get("@type") == "Person" and isinstance(x.get("name"), str):
                names.add(x["name"])
            for key in ("author", "creator"):
                v = x.get(key)
                if isinstance(v, str):
                    names.add(v)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(script.string or script.get_text() or "", strict=False))
        except json.JSONDecodeError:
            pass
    return names


def extract_comments(soup: BeautifulSoup, names: set[str]) -> list[dict]:
    comments = []
    seen = set()
    for el in soup.find_all(id=COMMENT_ID_RE):
        cid = COMMENT_ID_RE.match(el["id"]).group(1)
        if cid in seen:
            continue
        seen.add(cid)
        classes = el.get("class") or []
        content = None
        for cls in CONTENT_CLASSES:
            for cand in el.find_all(class_=cls):
                if _owner(cand) is el:
                    content = cand
                    break
            if content:
                break
        if content is None:
            continue
        text = scrub_text(content.get_text(" ", strip=True), names)
        comments.append(
            {
                "comment_id": cid,
                "text": text,
                "post_author": "bypostauthor" in classes,
                "reply": _owner(el) is not None,
            }
        )
    return comments


def sanitize_page(raw_html: str) -> tuple[str, dict]:
    """Return (sanitised page, summary). The sanitised page is what enters state as raw_page."""
    soup = BeautifulSoup(raw_html, "lxml")
    canonical = soup.find("link", rel="canonical")
    canonical_url = canonical.get("href") if canonical else None
    og_url = soup.find("meta", property="og:url")
    if not canonical_url and og_url:
        canonical_url = og_url.get("content")
    recipes = extract_recipe_jsonld(soup)
    names = collect_names(soup, jsonld_person_names(soup))
    comments = extract_comments(soup, names)

    parts = ["<html><head>"]
    if canonical_url:
        parts.append(f'<link rel="canonical" href="{html_lib.escape(canonical_url)}">')
    for r in recipes:
        parts.append(
            '<script type="application/ld+json">'
            + json.dumps(r, ensure_ascii=False).replace("</", "<\\/")
            + "</script>"
        )
    parts.append('</head><body><ol class="comments">')
    for c in comments:
        parts.append(
            f'<li data-comment-id="{c["comment_id"]}" data-post-author="{int(c["post_author"])}" '
            f'data-reply="{int(c["reply"])}">{html_lib.escape(c["text"])}</li>'
        )
    parts.append("</ol></body></html>")
    return "".join(parts), {"recipes": len(recipes), "comments": len(comments)}
