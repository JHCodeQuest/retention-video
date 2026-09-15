"""Turns analysis results into a narration script: an ordered list of
segments, each with the words to speak and the text on the PDF page the
camera should focus on while they're spoken (None = whole page).

Wording lives in script_template.json so it can be edited without code
changes; the structure (which segments appear, in what order) lives here.
"""
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / "script_template.json"

_NUMBER_WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]


_GBP_AMOUNT = re.compile(r"-?£([\d,]+)")

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
         "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _under_thousand(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if rest:
        if rest < 20:
            words = _ONES[rest]
        else:
            tens, ones = divmod(rest, 10)
            words = _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
        parts.append(words)
    return " and ".join(parts)


def number_words(n: int) -> str:
    """British English: 150 -> "a hundred and fifty",
    12450 -> "twelve thousand, four hundred and fifty"."""
    if n == 0:
        return "zero"
    lowest = n % 1000
    groups = []
    for scale in ("", " thousand", " million", " billion"):
        n, chunk = divmod(n, 1000)
        if chunk:
            groups.append(_under_thousand(chunk) + scale)
        if not n:
            break
    groups.reverse()
    if len(groups) > 1 and 0 < lowest < 100:
        # "5,020" -> "five thousand and twenty"
        words = ", ".join(groups[:-1]) + " and " + groups[-1]
    else:
        words = ", ".join(groups)
    return re.sub(r"^one (hundred|thousand|million)", r"a \1", words)


def spoken_text(text: str) -> str:
    """Caption text rewritten for TTS: "£12,450" -> "twelve thousand, four
    hundred and fifty pounds". Voices otherwise read £ as dollars, and
    written-out numbers avoid garbled digit readings."""
    def _say(m: re.Match) -> str:
        amount = int(m.group(1).replace(",", ""))
        unit = "pound" if amount == 1 else "pounds"
        prefix = "minus " if m.group(0).startswith("-") else ""
        return f"{prefix}{number_words(amount)} {unit}"
    return _GBP_AMOUNT.sub(_say, text)


@dataclass(frozen=True)
class Segment:
    key: str
    text: str
    focus: str | None

    @property
    def spoken(self) -> str:
        return spoken_text(self.text)


def _count_word(n: int) -> str:
    return _NUMBER_WORDS[n] if n < len(_NUMBER_WORDS) else str(n)


def _join_names(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def build_script(results, urgency: str, format_gbp, template_path: Path = TEMPLATE_PATH,
                 month: str | None = None) -> list[Segment]:
    t = json.loads(Path(template_path).read_text(encoding="utf-8"))
    month = month or time.strftime("%B %Y")
    total = sum(r.profit_gbp for r in results)

    retain = [r for r in results if r.recommendation == "Retain"]
    review = [r for r in results if r.recommendation == "Review"]
    drop = [r for r in results if r.recommendation == "Drop"]

    segments = [
        Segment("intro", t["intro"].format(month=month, client_count=len(results)),
                "Client Retention Report"),
        Segment("headline", t["headline"].format(total_profit=format_gbp(total), urgency=urgency.lower()),
                "Total monthly profit"),
    ]

    if retain:
        top = retain[0]
        segments.append(Segment(
            "retain_top",
            t["retain_top"].format(name=top.name, revenue=format_gbp(top.monthly_revenue_gbp),
                                   profit=format_gbp(top.profit_gbp), margin=round(top.margin_pct)),
            top.name,
        ))
        others = [r.name for r in retain[1:]]
        if others:
            segments.append(Segment(
                "retain_group",
                t["retain_group"].format(count_word=_count_word(len(others)) + " more", names=_join_names(others)),
                None,
            ))

    for r in review:
        segments.append(Segment(
            f"review:{r.name}",
            t["review_item"].format(name=r.name, profit=format_gbp(r.profit_gbp), margin=round(r.margin_pct)),
            r.name,
        ))

    for r in drop:
        segments.append(Segment(
            f"drop:{r.name}",
            t["drop_item"].format(name=r.name, loss=format_gbp(abs(r.profit_gbp))),
            r.name,
        ))

    segments.append(Segment(
        "outro",
        t["outro"].format(retain_count=len(retain), review_count=len(review), drop_count=len(drop)),
        None,
    ))
    return segments
