import re

RESUME_ACTION_VERBS = frozenset(
    {
        "achieved",
        "administered",
        "analyzed",
        "architected",
        "automated",
        "built",
        "collaborated",
        "configured",
        "coordinated",
        "created",
        "delivered",
        "deployed",
        "designed",
        "developed",
        "drove",
        "engineered",
        "enhanced",
        "established",
        "implemented",
        "improved",
        "increased",
        "integrated",
        "launched",
        "led",
        "maintained",
        "managed",
        "mentored",
        "migrated",
        "monitored",
        "optimized",
        "orchestrated",
        "owned",
        "partnered",
        "planned",
        "produced",
        "programmed",
        "reduced",
        "refactored",
        "resolved",
        "scaled",
        "secured",
        "shipped",
        "streamlined",
        "supported",
        "tested",
        "transformed",
        "upgraded",
        "used",
        "worked",
        "wrote",
    }
)

FIRST_WORD_RE = re.compile(r"[A-Za-z]+")
DANGLING_FACT_END_RE = re.compile(
    r"(?:\b(?:a|an|and|as|at|by|for|from|in|of|on|or|the|to|using|via|with)[.!?]?|"
    r"[,;:/&-])$",
    re.IGNORECASE,
)


def starts_with_resume_action_verb(value: str) -> bool:
    first_word = FIRST_WORD_RE.match(value)
    return bool(first_word and first_word.group(0).casefold() in RESUME_ACTION_VERBS)


def has_dangling_fact_ending(value: str) -> bool:
    return bool(DANGLING_FACT_END_RE.search(value))
