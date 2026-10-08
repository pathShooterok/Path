"""Do the profiles found for one username belong to the same person?

A username existing on many platforms proves nothing: 'durov' on DEV is a
different person than 'durov' on Telegram. This module looks for evidence that
links profiles to each other and groups them:

  * cross-link  (strong): profile A's page/API points to profile B
  * name tokens (weak):   profiles show the same display-name words

It never changes existing findings; it only adds `correlation` findings.
"""
import re

from core.models import Finding
from extractors.social import parse_social_url, translit

# words that appear in page titles of the platforms themselves, not in names
NOISE = {
    "github", "gitlab", "overview", "instagram", "photos", "videos", "photo", "video",
    "telegram", "view", "contact", "profile", "keybase", "community", "habr", "pikabu",
    "twitter", "followers", "following", "posts", "post", "founder", "the", "and",
    "with", "from", "page", "user", "users", "official", "channel", "right", "away",
    "you", "can", "now", "app", "open", "source", "encryption", "cryptography",
    "chevron", "down", "icon", "дзен", "яндекс",
}

NAME_KINDS = {"name", "linked_name"}
TITLE_KINDS = {"linked_og_title", "linked_title", "og_title", "title"}


def _key(url: str):
    p = parse_social_url(url)
    return (p["platform"], p["username"].lower()) if p else None


def _tokens(text: str, drop: set[str]) -> set[str]:
    text = re.sub(r"\(@[^)]*\)", " ", text)           # "(@durov)"
    words = re.findall(r"[A-Za-zА-Яа-яЁё]{4,}", text)
    out = set()
    for w in words:
        t = translit(w)
        if t in NOISE or w.lower() in NOISE or t in drop:
            continue
        out.add(t)
    return out


def correlate_profiles(report, target: str) -> None:
    drop = {translit(target)}

    # 1) profiles = direct social findings (probe / search / profile scan)
    profiles: dict[tuple, dict] = {}
    for f in report.findings:
        if f.kind != "social":
            continue
        key = parse_social_url(f.value.split(": ", 1)[-1])
        if not key:
            continue
        k = (key["platform"], key["username"].lower())
        profiles.setdefault(k, {"name": key["platform"], "url": key["url"], "tokens": set()})

    if len(profiles) < 2:
        return

    # 2) name tokens per profile, from findings whose source is that profile page
    for f in report.findings:
        k = _key(f.source) if f.source else None
        if k not in profiles:
            continue
        if f.kind in NAME_KINDS or f.kind in TITLE_KINDS:
            profiles[k]["tokens"] |= _tokens(f.value, drop | {translit(k[1])})

    # 3) edges
    edges: dict[frozenset, dict] = {}

    keys = list(profiles)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            shared = profiles[a]["tokens"] & profiles[b]["tokens"]
            if shared:
                e = edges.setdefault(frozenset((a, b)), {"strong": False, "why": set()})
                e["why"].add("name words: " + ", ".join(sorted(shared)))

    for f in report.findings:
        if f.kind not in ("linked_social", "link", "linked_og_url") and f.source_type != "github_api":
            continue
        src = _key(f.source) if f.source else None
        raw = f.value.split(": ", 1)[-1]
        dst = _key(raw)
        if src in profiles and dst in profiles and src != dst:
            e = edges.setdefault(frozenset((src, dst)), {"strong": False, "why": set()})
            e["strong"] = True
            e["why"].add(f"{profiles[src]['name']} links to {profiles[dst]['name']}")

    if not edges:
        _emit_unmatched(report, profiles, set())
        return

    # 4) union-find clusters
    parent = {k: k for k in profiles}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for pair in edges:
        a, b = tuple(pair)
        parent[find(a)] = find(b)

    clusters: dict[tuple, list] = {}
    for k in profiles:
        clusters.setdefault(find(k), []).append(k)

    matched = set()
    for members in clusters.values():
        if len(members) < 2:
            continue
        matched.update(members)
        why, strong = set(), False
        for pair, e in edges.items():
            if pair <= set(members):
                why |= e["why"]
                strong |= e["strong"]
        names = ", ".join(sorted(profiles[m]["name"] for m in members))
        report.findings.append(Finding(
            kind="correlation",
            value=names,
            source=" | ".join(sorted(profiles[m]["url"] for m in members)),
            evidence=("Profiles likely belong to one person. " if strong else
                      "Profiles may belong to one person (weak signal). ")
                     + "; ".join(sorted(why)),
            confidence="high" if strong else "medium",
            source_type="correlation",
        ))

    _emit_unmatched(report, profiles, matched)


def _emit_unmatched(report, profiles, matched):
    rest = [p for k, p in profiles.items() if k not in matched]
    if rest and matched:
        report.findings.append(Finding(
            kind="correlation_unmatched",
            value=", ".join(sorted(p["name"] for p in rest)),
            source=" | ".join(sorted(p["url"] for p in rest)),
            evidence="Username exists here, but no shared name or cross-link with the other "
                     "profiles: may be a different person",
            confidence="low",
            source_type="correlation",
        ))
    elif rest and not matched:
        report.findings.append(Finding(
            kind="correlation_unmatched",
            value=", ".join(sorted(p["name"] for p in rest)),
            source=" | ".join(sorted(p["url"] for p in rest)),
            evidence="No evidence linking these profiles to each other",
            confidence="low",
            source_type="correlation",
        ))
