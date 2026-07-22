#!/usr/bin/env python3
"""
agent-mind build tool — universal compile pipeline

Artifacts (never edit by hand):
  SKILL.md              persona + routing table with tags
  knowledge/_digest.md  high-confidence directives with severity
  knowledge/_edges.md   domain-level AND claim-level relationships

Claim format (in domain files):
  ## [id] Title
  **Confidence**: high | medium | low
  **Severity**:   critical | major | minor | style
  **Context**:    web-backend, database, api, ...
  **Updated**:    YYYY-MM-DD
  **Evidence**:   sources
  **Trigger**:    observable condition
  **Directive**:  what to do
  **Because**:    root cause (property)
  **Smells**:     observable violations
  **When not**:   exclusions (optional)
  **See also**:   [id], [id]  (optional)

Internal relationships section (end of each domain file):
  ## Internal relationships
  [eng.S1] --enables-->  [eng.S2]  note
  [eng.S5] <--tension--> [eng.M5]  note

Commands:
  python build.py
  python build.py --validate
  python build.py --candidates          list low/medium claims (review queue)
  python build.py --claims DOMAIN [--id ID] [--severity SEV] [--full]
  python build.py --log-signal DOMAIN --type TYPE --note "..."   append a WAL signal
  python build.py --distill [--since YYYY-MM-DD]   propose claim skeletons from repeats
  python build.py --add-domain NAME --cluster CLUSTER --summary "..."
  python build.py --package [OUTDIR]
"""

import argparse, re, sys
from datetime import date
from pathlib import Path

# Claim content carries em-dashes and ⚠ — force UTF-8 stdout so --claims/--candidates
# don't mojibake on a Windows console (matches the kanban scripts' convention).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    print("pip install pyyaml --break-system-packages"); sys.exit(1)

ROOT      = Path(__file__).parent
KNOWLEDGE = ROOT / "knowledge"
PERSONA   = ROOT / "persona.md"
SKILL_MD  = ROOT / "SKILL.md"
DIGEST    = KNOWLEDGE / "_digest.md"
EDGES_MD  = KNOWLEDGE / "_edges.md"
JOURNAL   = KNOWLEDGE / "_journal.md"

FM_RE         = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
CLAIM_RE      = re.compile(r"^## \[([^\]]+)\] (.+)$", re.MULTILINE)
CONFIDENCE_RE = re.compile(r"\*\*Confidence\*\*:\s*(\w+)")
SEVERITY_RE   = re.compile(r"\*\*Severity\*\*:\s*(\w+)")
TRIGGER_RE    = re.compile(r"\*\*Trigger\*\*:\s*(.+?)(?=\n\*\*|\Z)", re.DOTALL)
DIRECTIVE_RE  = re.compile(r"\*\*Directive\*\*:\s*(.+?)(?=\n\*\*|\Z)", re.DOTALL)
BECAUSE_RE    = re.compile(r"\*\*Because\*\*:\s*(.+?)(?=\n\*\*|\Z)", re.DOTALL)
EVIDENCE_RE   = re.compile(r"\*\*Evidence\*\*:\s*(.+?)(?=\n\*\*|\Z)", re.DOTALL)
UPDATED_RE    = re.compile(r"\*\*Updated\*\*:\s*(\d{4}-\d{2}-\d{2})")

# Internal relationships: [id] --type--> [id] note
INT_REL_RE = re.compile(
    r"^\[([^\]]+)\]\s+(--(\w+)-->|<--(\w+)-->)\s+\[([^\]]+)\]\s*(.*?)$",
    re.MULTILINE,
)
# Section boundary
INT_SECTION_RE = re.compile(
    r"^## Internal relationships\n(.*?)(?=\n^##|\Z)", re.MULTILINE | re.DOTALL
)

REQUIRED    = {"domain", "cluster", "summary"}
VALID_TYPES = {"supports", "enables", "refines", "tension"}
VALID_CONFIDENCE = {"high", "medium", "low"}
SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "style": 3}

# Recognition signals (persona.md Recognition table) — the kinds of moment worth logging.
SIGNAL_TYPES = {"Gap", "Repeat", "Miss", "Override", "Conflict"}
# One journal row: date | domain | type | note  (append-only, pipe-delimited so it greps).
JOURNAL_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|\s*(.*)$"
)


def iter_claims(text: str):
    """Yield (node_id, title, chunk) for each claim in a domain file.

    Single source of truth for claim parsing — both build_digest() and the
    validate() hygiene pass read claims through here so they never diverge.
    """
    for m in CLAIM_RE.finditer(text):
        start = m.end()
        nx    = CLAIM_RE.search(text, start)
        chunk = text[start: nx.start() if nx else len(text)]
        yield m.group(1), m.group(2), chunk


# ── Discovery ─────────────────────────────────────────────────────────────────

def cluster_dirs() -> list[Path]:
    return sorted(d for d in KNOWLEDGE.iterdir()
                  if d.is_dir() and not d.name.startswith("_"))


def domain_files() -> list[Path]:
    out = []
    for d in cluster_dirs():
        out += sorted(f for f in d.glob("*.md") if not f.name.startswith("_"))
    return out


def domain_id(p: Path) -> str:
    return f"{p.parent.name}/{p.stem}"


def read_fm(p: Path) -> dict:
    m = FM_RE.match(p.read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"No frontmatter in {p.name}")
    return yaml.safe_load(m.group(1)) or {}


def read_scope(cluster_dir: Path) -> str:
    f = cluster_dir / "_scope.md"
    if not f.exists():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


# ── Validate ──────────────────────────────────────────────────────────────────

def check_claim_hygiene(files: list[Path]) -> None:
    """Warn on claims that violate the self-learning invariants (README §Self-Learning).

    A high-confidence claim reaches the always-loaded _digest.md and drives default
    behavior, so it must be grounded: cite Evidence and state a Because. Every claim
    needs a Because (root cause). Confidence must be a known level so the lifecycle
    (low -> medium -> high) stays meaningful. These are warnings, not errors — they
    guide the LEARN workflow without blocking a build.
    """
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        did = domain_id(f)
        for nid, _title, chunk in iter_claims(text):
            cm   = CONFIDENCE_RE.search(chunk)
            conf = cm.group(1).lower() if cm else ""
            if conf not in VALID_CONFIDENCE:
                print(f"WARN  [{nid}] ({did}): confidence "
                      f"'{conf or 'missing'}' not in high|medium|low")
            if not BECAUSE_RE.search(chunk):
                print(f"WARN  [{nid}] ({did}): missing **Because** (root cause) "
                      f"-- required by claim format")
            if conf == "high" and not EVIDENCE_RE.search(chunk):
                print(f"WARN  [{nid}] ({did}): high-confidence claim must cite "
                      f"**Evidence** -- demote to low/medium or add a source")


def validate(verbose: bool = True) -> bool:
    ok, seen = True, set()
    files = domain_files()

    for d in cluster_dirs():
        if not (d / "_scope.md").exists():
            print(f"WARN  {d.name}/: no _scope.md")

    for f in files:
        did = domain_id(f)
        try:
            fm = read_fm(f)
        except Exception as e:
            print(f"FAIL  {did}: {e}"); ok = False; continue

        miss = REQUIRED - set(fm.keys())
        if miss:
            print(f"FAIL  {did}: missing {', '.join(sorted(miss))}"); ok = False; continue

        declared = f"{fm.get('cluster','')}/{fm.get('domain','')}"
        if declared != did:
            print(f"WARN  {did}: frontmatter says '{declared}'")

        if did in seen:
            print(f"FAIL  duplicate: {did}"); ok = False
        seen.add(did)

        for rel in fm.get("related", []):
            if rel.get("type", "") not in VALID_TYPES:
                print(f"WARN  {did}: bad edge type '{rel.get('type')}'")

        if verbose:
            tags = fm.get("tags", [])
            tag_str = f"  tags: {tags}" if tags else ""
            print(f"OK    {did}{tag_str}")

    all_ids = set(seen)
    # build_edges() dedups related: by unordered pair and keeps only the
    # alphabetically-first file, silently dropping the other file's type/note.
    # Warn so each pair is declared in exactly one file (unidirectional).
    edge_owner: dict[frozenset, tuple[str, str]] = {}
    for f in files:
        try:
            fm = read_fm(f)
        except Exception:
            continue
        src = domain_id(f)
        for rel in fm.get("related", []):
            ref = rel.get("domain", "")
            if ref and ref not in all_ids:
                print(f"WARN  {src}: related '{ref}' not found")
            if not ref:
                continue
            typ = rel.get("type", "supports")
            key = frozenset([src, ref])
            if key in edge_owner:
                prev_src, prev_typ = edge_owner[key]
                winner = min(prev_src, src)
                if prev_typ != typ:
                    print(f"WARN  related edge {src} <-> {ref} declared in both "
                          f"files with different types ({prev_src}={prev_typ}, "
                          f"{src}={typ}); build keeps only '{winner}' and drops the "
                          f"other -- make related: unidirectional")
                else:
                    print(f"WARN  related edge {src} <-> {ref} declared in both "
                          f"files (type {typ}); redundant -- make related: "
                          f"unidirectional (one file owns each pair)")
            else:
                edge_owner[key] = (src, typ)

    # Claim-level edges (## Internal relationships) also dedup in build_edges(),
    # keyed by ordered (src, tgt) — so only an exact-duplicate directed edge A->B
    # declared twice silently drops one (A->B and B->A stay legitimately distinct).
    claim_edge_owner: dict[tuple, str] = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        did = domain_id(f)
        for rel in parse_internal_rels(text, did):
            key = (rel["src"], rel["tgt"])
            if key in claim_edge_owner:
                prev = claim_edge_owner[key]
                where = f"twice in '{did}'" if prev == did else f"in '{prev}' and '{did}'"
                print(f"WARN  claim-level edge [{rel['src']}] -> [{rel['tgt']}] "
                      f"declared {where}; build keeps only the first -- declare each "
                      f"directed edge once")
            else:
                claim_edge_owner[key] = did

    check_claim_hygiene(files)

    if ok and verbose:
        print(f"\n{len(files)} files valid.")
    return ok


# ── Parse internal relationships ──────────────────────────────────────────────

def parse_internal_rels(text: str, source_did: str) -> list[dict]:
    """Extract claim-level edges from ## Internal relationships section."""
    sm = INT_SECTION_RE.search(text)
    if not sm:
        return []
    section = sm.group(1)
    out = []
    for m in INT_REL_RE.finditer(section):
        src_id   = m.group(1)
        tgt_id   = m.group(5)
        note     = m.group(6).strip()
        # Determine kind from arrow
        if m.group(3):   # --type-->
            kind = m.group(3)
        elif m.group(4): # <--type-->
            kind = m.group(4)
        else:
            kind = "supports"
        if kind not in VALID_TYPES:
            kind = "supports"
        out.append({"src": src_id, "tgt": tgt_id, "kind": kind,
                    "note": note, "domain": source_did})
    return out


# ── Build _edges.md ───────────────────────────────────────────────────────────

def build_edges(files: list[Path]) -> str:
    # Domain-level edges from related:
    seen_domain: set[frozenset] = set()
    d_tension, d_support = [], []

    for f in files:
        try:
            fm = read_fm(f)
        except Exception:
            continue
        src = domain_id(f)
        for rel in fm.get("related", []):
            tgt  = rel.get("domain", "")
            note = rel.get("edge", "").strip()
            kind = rel.get("type", "supports")
            if not tgt:
                continue
            key = frozenset([src, tgt])
            if key in seen_domain:
                continue
            seen_domain.add(key)
            arrow = "<--tension-->" if kind == "tension" else f"--{kind}-->"
            row   = f"  {src:<34} {arrow:<16} {tgt:<34} {note}"
            (d_tension if kind == "tension" else d_support).append(row)

    # Claim-level edges from ## Internal relationships
    seen_claim: set[tuple] = set()
    c_tension, c_support = [], []

    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        did = domain_id(f)
        for rel in parse_internal_rels(text, did):
            key = (rel["src"], rel["tgt"])
            if key in seen_claim:
                continue
            seen_claim.add(key)
            arrow = "<--tension-->" if rel["kind"] == "tension" else f"--{rel['kind']}-->"
            row   = f"  [{rel['src']}]{'':<4} {arrow:<16} [{rel['tgt']}]{'':<4} {rel['note']}"
            (c_tension if rel["kind"] == "tension" else c_support).append(row)

    out = [
        "# Cross-domain and claim-level edges",
        "_Generated from `related:` fields and `## Internal relationships` sections._",
        "_Edit source domain files, not this file._",
        "",
    ]
    if d_support:
        out += ["## Domain — reinforcing", "```"] + sorted(d_support) + ["```", ""]
    if d_tension:
        out += ["## Domain — tension ⚠  (name the trade-off when these domains meet)",
                "```"] + sorted(d_tension) + ["```", ""]
    if c_support:
        out += ["## Claim-level — reinforcing", "```"] + sorted(c_support) + ["```", ""]
    if c_tension:
        out += ["## Claim-level — tension ⚠", "```"] + sorted(c_tension) + ["```", ""]

    return "\n".join(out)


# ── Build _digest.md ──────────────────────────────────────────────────────────

SEVERITY_BADGE = {"critical": "`critical` ", "major": "`major` "}
DIGEST_MAX = 120


def _trunc(s: str, max_len: int = DIGEST_MAX) -> str:
    """Truncate at word boundary; appends '…' only when content is cut."""
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    boundary = cut.rfind(" ")
    if boundary > max_len * 0.6:
        return cut[:boundary] + "…"
    return cut + "…"


def build_digest(files: list[Path]) -> str:
    out = [
        "# Knowledge Digest",
        "_High-confidence directives. `critical`/`major` badges indicate review severity._",
        "_Load domain files for full detail: context, when-not, smells, evidence._",
        "",
    ]
    cur_cluster = None

    for f in files:
        try:
            fm   = read_fm(f)
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue

        cluster = fm.get("cluster", "")
        did     = domain_id(f)

        if cluster != cur_cluster:
            scope = read_scope(f.parent)
            out.append(f"\n## {cluster.upper()}")
            if scope:
                out.append(f"_{scope}_")
            cur_cluster = cluster

        out.append(f"\n### {did}")
        claims = []

        for nid, title, chunk in iter_claims(text):
            cm = CONFIDENCE_RE.search(chunk)
            if not cm or cm.group(1).lower() != "high":
                continue

            sm  = SEVERITY_RE.search(chunk)
            sev = sm.group(1).lower() if sm else "minor"

            tm = TRIGGER_RE.search(chunk)
            dm = DIRECTIVE_RE.search(chunk)
            bm = BECAUSE_RE.search(chunk)

            trigger   = _trunc(tm.group(1).strip().replace("\n", " ")) if tm else title
            directive = _trunc(dm.group(1).strip().replace("\n", " ")) if dm else ""
            tag       = ""
            if bm:
                t = re.search(r"\(([^)]+)\)", bm.group(1))
                tag = f" ({t.group(1)})" if t else ""

            badge = SEVERITY_BADGE.get(sev, "")
            if directive:
                line = f"- **[{nid}]** {badge}{trigger} → {directive}{tag}"
            else:
                line = f"- **[{nid}]** {badge}{trigger}{tag}"

            sort_key = SEVERITY_ORDER.get(sev, 2)
            claims.append((sort_key, line))

        if claims:
            claims.sort(key=lambda x: x[0])
            out += [c[1] for c in claims]
        else:
            out.append(f"_No high-confidence claims yet._")

    return "\n".join(out)


# ── Build SKILL.md ────────────────────────────────────────────────────────────

def build() -> None:
    if not PERSONA.exists():
        print("persona.md not found"); sys.exit(1)
    if not validate(verbose=False):
        print("Fix validation errors first."); sys.exit(1)

    files = domain_files()
    clusters: dict[str, list[dict]] = {}
    for f in files:
        fm = read_fm(f)
        c  = fm["cluster"]
        tags = fm.get("tags", [])
        clusters.setdefault(c, []).append({
            "id":   domain_id(f),
            "file": f"knowledge/{f.relative_to(KNOWLEDGE).as_posix()}",
            "summ": fm.get("summary", "")[:80],
            "tags": ", ".join(tags[:8]) if tags else "",
        })

    table = [
        "## Domain routing table",
        "",
        "Match task to domain and load that file directly.",
        "Unsure? → `knowledge/_digest.md`   |   2+ domains? → `knowledge/_edges.md`",
        "",
    ]
    for c, domains in sorted(clusters.items()):
        scope = read_scope(KNOWLEDGE / c)
        table.append(f"### {c}")
        if scope:
            table.append(f"_{scope}_")
        table.append("")
        table.append("| Domain ID | File | Covers | Tags |")
        table.append("|-----------|------|--------|------|")
        for d in domains:
            table.append(
                f"| `{d['id']}` | `{d['file']}` | {d['summ']} | {d['tags']} |"
            )
        table.append("")
    table.append("<!-- Generated by build.py -->")

    persona_text = PERSONA.read_text(encoding="utf-8").rstrip()
    fm_match = FM_RE.match(persona_text)
    if fm_match:
        notice = "<!-- Generated from persona.md by build.py — do not edit SKILL.md directly -->\n\n"
        skill_body = persona_text[:fm_match.end()] + notice + persona_text[fm_match.end():]
    else:
        skill_body = persona_text
    SKILL_MD.write_text(
        skill_body + "\n\n---\n\n" + "\n".join(table) + "\n",
        encoding="utf-8",
    )
    print(f"OK  SKILL.md  ({SKILL_MD.stat().st_size // 1024 + 1} KB, {len(files)} domains)")

    EDGES_MD.write_text(build_edges(files), encoding="utf-8")
    print(f"OK  _edges.md  ({EDGES_MD.stat().st_size} bytes)")

    DIGEST.write_text(build_digest(files), encoding="utf-8")
    print(f"OK  _digest.md  ({DIGEST.stat().st_size} bytes)")


# ── Candidates (review queue) ───────────────────────────────────────────────────

def list_candidates(files: list[Path]) -> None:
    """List low/medium claims — the self-learning quarantine / review queue.

    Only `high` claims reach _digest.md (the operating set), so low/medium are
    knowledge the agent has captured but not yet promoted. This is a VIEW over the
    confidence field, not a separate store — the queue is a query. Age (from
    **Updated**) surfaces stale candidates a review should promote or retire.
    """
    today = date.today()
    buckets: dict[str, list[str]] = {"medium": [], "low": []}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        did = domain_id(f)
        for nid, title, chunk in iter_claims(text):
            cm   = CONFIDENCE_RE.search(chunk)
            conf = cm.group(1).lower() if cm else ""
            if conf not in ("low", "medium"):
                continue
            um = UPDATED_RE.search(chunk)
            try:
                age_str = f"{(today - date.fromisoformat(um.group(1))).days}d" if um else "?"
            except ValueError:
                age_str = "?"
            buckets[conf].append(f"  [{nid}] {did}  ({age_str})  {title}")

    total = len(buckets["low"]) + len(buckets["medium"])
    if total == 0:
        print("No candidates: every claim is high-confidence (operating set), or the "
              "graph is empty.")
        print("The low/medium quarantine is where self-learned claims wait for "
              "evidence before promotion into _digest.md.")
        return

    print(f"Candidate claims (low/medium) -- NOT in _digest.md, awaiting promotion. "
          f"{total} total.")
    print("Promote by adding independent Evidence; retire if stale/unconfirmed.\n")
    for conf in ("medium", "low"):
        rows = buckets[conf]
        if rows:
            print(f"{conf.upper()} ({len(rows)}):")
            print("\n".join(sorted(rows)))
            print()


# ── Retrieve claims (token-efficient slice) ─────────────────────────────────────

def emit_claims(domain: str, ids: str = "", severity: str = "",
                full: bool = False) -> None:
    """Print a minimal slice of one domain's claims — retrieval instead of loading
    the whole file. Token spend then scales with relevance, not domain size — which
    matters as the self-learning graph grows. Filters compose: --id (comma list),
    --severity. Default: one line per claim; --full prints the entire claim body.
    """
    want_ids = {i.strip() for i in ids.split(",") if i.strip()}
    target = next((f for f in domain_files()
                   if domain_id(f) == domain or f.stem == domain), None)
    if target is None:
        known = ", ".join(domain_id(f) for f in domain_files())
        print(f"Domain not found: {domain}. Known: {known}"); sys.exit(1)

    text  = target.read_text(encoding="utf-8")
    shown = 0
    for nid, title, chunk in iter_claims(text):
        if want_ids and nid not in want_ids:
            continue
        sm  = SEVERITY_RE.search(chunk)
        sev = sm.group(1).lower() if sm else "minor"
        if severity and sev != severity.lower():
            continue
        shown += 1
        if full:
            print(f"## [{nid}] {title}\n{chunk.strip()}\n")
        else:
            dm = DIRECTIVE_RE.search(chunk)
            directive = _trunc(dm.group(1).strip().replace("\n", " ")) if dm else ""
            line = f"- [{nid}] ({sev}) {title}"
            if directive:
                line += f" -> {directive}"
            print(line)
    if shown == 0:
        print(f"No claims matched in {domain_id(target)} "
              f"(id={ids or '*'}, severity={severity or '*'}).")


# ── WAL: log a recognition signal ───────────────────────────────────────────────

def resolve_domain(domain: str) -> str:
    """Canonicalize a --log-signal domain arg to its `cluster/domain` id.

    The arg is accepted in either form — full id (`engineering/performance`) or bare
    stem (`performance`). The journal stores it verbatim and --distill groups repeats
    by the exact domain string, so an un-canonicalized stem would split one signal
    across two buckets (`performance` vs `engineering/performance`) and the rule of
    three would never fire — distillation silently misses the repeat. Canonicalize at
    the boundary instead of trusting callers to pick one spelling ([eng.M1] single
    source of truth). Ambiguous stem (matches >1 cluster) or unknown -> exit 1.
    """
    files = domain_files()
    ids   = {domain_id(f) for f in files}
    if domain in ids:
        return domain
    matches = sorted({domain_id(f) for f in files if f.stem == domain})
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous domain '{domain}' -- matches {', '.join(matches)}. "
              f"Use the full 'cluster/domain' form.")
    else:
        print(f"Domain not found: {domain}. Known: {', '.join(sorted(ids))}")
    sys.exit(1)


def log_signal(domain: str, sig_type: str, note: str) -> None:
    """Append one recognition signal to knowledge/_journal.md (append-only WAL).

    Cheap always-on OBSERVATION, split from the expensive periodic DISTILLATION
    (WAL -> compaction from databases). A signal only records that a learnable
    moment fired during WRITE/REVIEW/REFACTOR; it never mutates a domain file.
    Distillation (--distill) later proposes claim skeletons from repeats; the
    agent still decides via the capture gate. Row: date | domain | type | note.
    """
    domain = resolve_domain(domain)  # canonical `cluster/domain` so --distill groups repeats
    if sig_type not in SIGNAL_TYPES:
        print(f"Unknown --type '{sig_type}'. Valid: {', '.join(sorted(SIGNAL_TYPES))}")
        sys.exit(1)
    note = " ".join(note.split())  # collapse newlines/whitespace: one line per signal
    if not note:
        print("--note must be non-empty"); sys.exit(1)

    if not JOURNAL.exists():
        JOURNAL.write_text(
            "# Recognition journal (WAL)\n"
            "_Append-only signals logged via `build.py --log-signal`. "
            "`build.py --distill` compacts repeats into claim skeletons._\n"
            "_One row: `date | domain | type | note`. Do not hand-edit; append via the script._\n\n",
            encoding="utf-8",
        )
    row = f"{date.today().isoformat()} | {domain} | {sig_type} | {note}\n"
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(row)
    print(f"OK  logged {sig_type} signal for {domain} -> {JOURNAL.relative_to(ROOT)}")


# ── Distill: propose claim skeletons from repeated signals ───────────────────────

def iter_journal(since: str = ""):
    """Yield (date_str, domain, type, note) for each journal row on/after --since.

    Single parse path for the WAL — matches iter_claims()'s role for domain files.
    """
    if not JOURNAL.exists():
        return
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        m = JOURNAL_RE.match(line.strip())
        if not m:
            continue
        d, domain, sig_type, note = (g.strip() for g in m.groups())
        if since and d < since:
            continue
        yield d, domain, sig_type, note


def _note_key(note: str) -> str:
    """Normalize a note for similarity grouping: lowercase word set, no punctuation."""
    return " ".join(sorted(re.findall(r"\w+", note.lower())))


def distill(since: str = "") -> None:
    """Compact the WAL into proposed claim skeletons (rule of three, [eng.M2]).

    A repeated signal (same domain+type+similar note appearing >=2x) is surfaced as
    ONE claim skeleton at Confidence: low, with the journal dates + source carried
    into Evidence:. This only PROPOSES — it never writes into a domain file; the
    agent decides via the capture gate + confidence lifecycle. Idempotent: --since
    filters by date so already-distilled rows can be excluded on the next pass.
    """
    # Group by (domain, type, normalized note) — the "same trigger" bucket.
    groups: dict[tuple, list[str]] = {}
    labels: dict[tuple, tuple] = {}
    for d, domain, sig_type, note in iter_journal(since):
        key = (domain, sig_type, _note_key(note))
        groups.setdefault(key, []).append(d)
        labels.setdefault(key, (domain, sig_type, note))  # first-seen note as the label

    repeats = {k: v for k, v in groups.items() if len(v) >= 2}
    scope = f" since {since}" if since else ""
    if not repeats:
        print(f"No repeated signals{scope} (rule of three needs the same trigger >=2x). "
              f"Nothing to propose.")
        return

    print(f"Proposed claim skeletons from repeated signals{scope} "
          f"({len(repeats)} candidate(s)) -- NOT written to any domain. "
          f"Review against the capture gate, then place manually at Confidence: low.\n")
    for key in sorted(repeats):
        domain, sig_type, note = labels[key]
        dates = sorted(repeats[key])
        cluster = domain.split("/")[0]  # e.g. "engineering/performance" -> "engineering"
        abbr = cluster.replace("-", "")[:3].lower() or "eng"
        provenance = (f"Distilled from journal: {sig_type} x{len(dates)} "
                      f"({', '.join(dates)}); domain {domain}")
        print(f"## [{abbr}.X?] {note[:60]}")
        print(f"**Confidence**: low")
        print(f"**Severity**: minor")
        print(f"**Context**: general")
        print(f"**Updated**: {date.today().isoformat()}")
        print(f"**Evidence**: {provenance}")
        print(f"**Trigger**: {note}")
        print(f"**Directive**: (fill in -- what to do when the trigger is detected)")
        print(f"**Because**: (fill in -- root-cause property and mechanism)")
        print(f"  -> target domain: {domain}\n")


# ── Add domain ────────────────────────────────────────────────────────────────

TEMPLATE = """\
---
domain: {domain}
cluster: {cluster}
summary: "{summary}"
tags: []
  # search terms: synonyms and related concepts for this domain
  # e.g. [sql, injection, xss, validation, sanitize]
updated: {today}
related: []
  # - domain: <cluster>/<name>
  #   type: supports | enables | refines | tension
  #   edge: "one-line note"
---

# {title}

## [{abbr}.X1] First directive title
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: {today}
**Evidence**: Source
**Trigger**: The observable condition that activates this directive.
**Directive**: What to do when the trigger is detected.
**Because**: Root cause — what property (readability / maintainability / security /
             performance / scalability) and through what mechanism?
**Smells**: Observable signals this directive is being violated.
**When not**: Conditions where this directive does not apply.
**See also**: 

## Internal relationships
<!-- claim-level edges within this domain
[{abbr}.X1] --supports--> [{abbr}.X2]  note
[{abbr}.X2] <--tension--> [{abbr}.X3]  note
-->
"""

SCOPE_TEMPLATE = """\
# {cluster} — scope

In this skill, **{cluster}** means: {summary}

**Covers:**
- (add specifics)

**Not covered here:**
- (add exclusions to prevent domain collision with other clusters/skills)
"""


def add_domain(name: str, cluster: str, summary: str) -> None:
    slug = name.lower().replace(" ", "-")
    cdir = KNOWLEDGE / cluster
    target = cdir / f"{slug}.md"
    cdir.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"Already exists: {target}"); sys.exit(1)

    scope_file = cdir / "_scope.md"
    if not scope_file.exists():
        scope_file.write_text(SCOPE_TEMPLATE.format(
            cluster=cluster, summary=summary or f"the {cluster} domain",
        ), encoding="utf-8")
        print(f"Scaffolded {scope_file.relative_to(ROOT)}")
        print(f"  → fill in _scope.md to disambiguate this cluster")

    abbr = "".join(w[0] for w in cluster.split("-"))[:3].lower()
    target.write_text(TEMPLATE.format(
        domain=slug, cluster=cluster,
        summary=summary or slug,
        today=date.today().isoformat(),
        title=name.title(), abbr=abbr,
    ), encoding="utf-8")
    print(f"Scaffolded {target.relative_to(ROOT)}")
    print(f"  → fill in claims, then: python build.py")


# ── Package ────────────────────────────────────────────────────────────────────

# Never shipped in a package: caches and the ephemeral recognition WAL (session
# data, not skill content). Keeps a shared/packaged skill clean and portable.
PACKAGE_EXCLUDE = {"__pycache__", ".git", "_journal.md"}


def _find_skill_creator() -> "Path | None":
    """Locate skill-creator across Claude environments — not one hardcoded path.

    Order: $SKILL_CREATOR_PATH, then known Claude locations. Returns None if absent
    so packaging falls back to a portable stdlib zip that works anywhere.
    """
    import os
    env = os.environ.get("SKILL_CREATOR_PATH", "").strip()
    candidates = ([Path(env)] if env else []) + [
        Path("/mnt/skills/examples/skill-creator"),
        Path("/mnt/skills/public/skill-creator"),
    ]
    return next((c for c in candidates if c.exists()), None)


def _zip_package(outdir: str | None) -> None:
    """Portable fallback: zip the skill dir with stdlib, excluding ephemeral/generated
    files. Works in ANY Claude environment — no external dependency."""
    import zipfile
    dest_dir = Path(outdir).expanduser() if outdir else ROOT.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{ROOT.name}.zip"
    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob("*")):
            rel = p.relative_to(ROOT)
            if any(part in PACKAGE_EXCLUDE for part in rel.parts):
                continue
            if p.is_file():
                z.write(p, Path(ROOT.name) / rel)
                count += 1
    print(f"OK  packaged {count} files (stdlib zip) -> {dest}")
    print("    skill-creator not found; used portable fallback "
          "(set SKILL_CREATOR_PATH for richer packaging).")


def package(outdir: str | None) -> None:
    creator = _find_skill_creator()
    if creator is None:
        _zip_package(outdir)
        return
    import subprocess
    args = ["python", "-m", "scripts.package_skill", str(ROOT)]
    if outdir:
        args.append(outdir)
    sys.exit(subprocess.run(args, cwd=creator).returncode)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="agent-mind build tool")
    p.add_argument("--validate",   action="store_true")
    p.add_argument("--candidates", action="store_true",
                   help="list low/medium claims (self-learning review queue)")
    p.add_argument("--claims",     metavar="DOMAIN",
                   help="retrieve a slice of one domain's claims (token-efficient)")
    p.add_argument("--id",         default="", help="filter --claims to id(s), comma-separated")
    p.add_argument("--severity",   default="", help="filter --claims by severity")
    p.add_argument("--full",       action="store_true", help="print full claim body for --claims")
    p.add_argument("--log-signal", metavar="DOMAIN",
                   help="append a recognition signal to knowledge/_journal.md (WAL)")
    p.add_argument("--type",       default="",
                   help="signal type for --log-signal: Gap|Repeat|Miss|Override|Conflict")
    p.add_argument("--note",       default="", help="one-line signal note for --log-signal")
    p.add_argument("--distill",    action="store_true",
                   help="propose claim skeletons from repeated journal signals")
    p.add_argument("--since",      default="",
                   help="filter --distill to signals on/after YYYY-MM-DD (idempotency)")
    p.add_argument("--add-domain", metavar="NAME")
    p.add_argument("--cluster",    default="general")
    p.add_argument("--summary",    default="")
    p.add_argument("--package",    nargs="?", const=".", metavar="OUTDIR")
    a = p.parse_args()

    if a.validate:
        sys.exit(0 if validate() else 1)
    elif a.candidates:
        list_candidates(domain_files())
    elif a.claims:
        emit_claims(a.claims, a.id, a.severity, a.full)
    elif a.log_signal:
        log_signal(a.log_signal, a.type, a.note)
    elif a.distill:
        distill(a.since)
    elif a.add_domain:
        add_domain(a.add_domain, a.cluster, a.summary)
    elif a.package is not None:
        build()
        package(None if a.package == "." else a.package)
    else:
        build()

if __name__ == "__main__":
    main()
