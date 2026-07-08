import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

from app.schemas.common import SkillCategory
from app.services.text import normalize_token


@dataclass(frozen=True)
class SkillDefinition:
    canonical: str
    category: SkillCategory
    variants: tuple[str, ...]


@lru_cache
def skill_definitions() -> tuple[SkillDefinition, ...]:
    raw = _load_dictionary()
    return tuple(
        SkillDefinition(
            canonical=item["canonical"],
            category=SkillCategory(item["category"]),
            variants=tuple(item["variants"]),
        )
        for item in raw["skills"]
    )


@lru_cache
def variant_to_skill() -> dict[str, SkillDefinition]:
    return {
        normalize_token(variant): definition
        for definition in skill_definitions()
        for variant in (*definition.variants, definition.canonical)
    }


@lru_cache
def implied_by() -> dict[str, tuple[str, ...]]:
    raw = _load_dictionary()
    return {skill: tuple(sources) for skill, sources in raw["implied_by"].items()}


def canonicalize_skill(value: str) -> str:
    definition = variant_to_skill().get(normalize_token(value))
    return definition.canonical if definition else value.strip()


def category_for_skill(value: str) -> SkillCategory:
    definition = variant_to_skill().get(normalize_token(value))
    if definition:
        return definition.category
    for item in skill_definitions():
        if item.canonical.lower() == value.lower():
            return item.category
    return SkillCategory.other


def find_skills(text: str) -> list[str]:
    normalized_text = f" {normalize_token(text)} "
    found: set[str] = set()
    for variant, definition in variant_to_skill().items():
        needle = f" {variant} "
        slash_needle = f" {variant}/"
        comma_needle = f" {variant},"
        period_needle = f" {variant}."
        if (
            needle in normalized_text
            or slash_needle in normalized_text
            or comma_needle in normalized_text
            or period_needle in normalized_text
        ):
            found.add(definition.canonical)
    return sorted(found)


def is_inferred_match(job_skill: str, resume_skills: set[str]) -> bool:
    implied_sources = implied_by().get(job_skill, ())
    return any(source in resume_skills for source in implied_sources)


@lru_cache
def _load_dictionary() -> dict[str, Any]:
    dictionary_path = files("app.data").joinpath("skill_dictionary.json")
    return json.loads(dictionary_path.read_text(encoding="utf-8"))
