---
domain: naming
cluster: engineering
summary: "Identifiers as communication: nouns for data, verbs for functions, booleans as questions, SHOUT constants, English only, clarity over brevity, no filler words"
tags: [naming, identifiers, variables, functions, constants, booleans, readability, transliteration]
updated: 2026-06-25
related:
  # code-design owns the naming<->code-design edge (unidirectional)
  - domain: engineering/maintainability
    type: supports
    edge: "Consistent naming lowers the cost of reading unfamiliar code during change"
---

# Naming

## [eng.N1] Nouns for data, verbs for functions
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code Ch.2; Code Complete Ch.11
**Trigger**: An identifier's part of speech doesn't match its role — a function named as a noun (`price()`), a variable named as a verb (`getUser = ...`).
**Directive**: Rename so variables/types are nouns answering "what is this?" and functions start with a verb answering "what does it do?"
**Because**: Part of speech signals role before the body is read. A mismatch forces a mental correction on every encounter. (readability)
**Smells**: `price()` as a function; `getUser` as a variable; anything you can't say "the X" about.
**When not**: Boolean variables — handled by [eng.N2]. Constants — handled by [eng.N3].
**See also**: [eng.N2], [eng.N3]

## [eng.N2] Booleans as yes/no questions
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code; common style guides
**Trigger**: A boolean variable is named as a noun or adjective (`status`, `active`, `enabled`).
**Directive**: Rename with prefix `is`, `has`, `can`, or `should` — (`isActive`, `hasToken`, `canEdit`, `shouldRetry`).
**Because**: `if (isActive)` reads as English; `if (active)` is ambiguous — flag? count? the object itself? (readability)
**Smells**: Boolean named as noun (`status`, `flag`); double negatives (`isNotDisabled`).
**When not**: N/A — applies universally to boolean variables.
**See also**: [eng.N1]

## [eng.N3] Constants SHOUT
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Code Complete Ch.12; universal convention
**Trigger**: A value that never changes at runtime is named in camelCase or lowercase.
**Directive**: Rename to `UPPER_SNAKE_CASE` — `MAX_USERS`, `API_URL`, `DEFAULT_TIMEOUT_MS`.
**Because**: Case signals "defined once; change it here" and warns against reassignment. (readability + maintainability)
**Smells**: Magic numbers or strings inline; a "constant" that is actually mutated.
**When not**: Enum members in languages where enum already signals immutability.
**See also**: [eng.N1]

## [eng.N4] English only — no transliteration
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Ubiquitous language principle
**Trigger**: An identifier uses transliterated characters from another language (`knopka`, `polzovatel`, `tovar`).
**Directive**: Replace with plain English (`button`, `user`, `product`). If no good translation exists, use the original term directly — not transliteration.
**Because**: Mixed languages break grep, autocomplete, and onboarding for any non-native contributor. (maintainability)
**Smells**: Latin-letter renderings of Cyrillic, Arabic, or other scripts; mixed-language identifiers in one file.
**When not**: Domain-specific proper nouns with no standard English equivalent.
**See also**: [eng.N5]

## [eng.N5] Clarity over brevity
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code; A Philosophy of Software Design Ch.14
**Trigger**: An identifier is abbreviated or shortened to the point where its meaning requires context to decode (`d`, `tmp`, `val`, `usr`).
**Directive**: Use the full descriptive name. Scale length to scope: a 3-line loop index `i` is fine; a module export needs a full name like `daysUntilExpiration`.
**Because**: The writer pays the naming cost once; every future reader pays for obscurity on every read. (readability)
**Smells**: Single-letter names outside tiny scopes; non-universal abbreviations; names needing context to decode.
**When not**: Mathematical algorithms where single-letter variable names are standard convention (`i`, `j`, `x`, `y`, `n`).
**See also**: [eng.N6]

## [eng.N6] No filler words
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code; Ousterhout on information leakage in names
**Trigger**: An identifier contains words that add no meaning: `data`, `info`, `value`, `manager`, `object`, `helper`, `util`.
**Directive**: Remove the filler. `userData` → `user`; `configObject` → `config`; `paymentManager` → `payments`.
**Because**: Noise words dilute signal and create false distinctions — `user` vs `userData` vs `userInfo` all meaning the same thing. (readability)
**Smells**: `*Data`, `*Info`, `*Value`, `*Manager`, `*Helper` suffixes; `xxxObject`; `the2`/`theOther` patterns.
**When not**: When the suffix genuinely distinguishes (`rawData` vs `parsedData` are meaningfully different).
**See also**: [eng.N5]

## Internal relationships
[eng.N2] --refines-->  [eng.N1]   booleans-as-questions is a specific case of nouns-for-data
[eng.N3] --refines-->  [eng.N1]   SHOUT constants are a specific case of nouns-for-data
[eng.N6] --refines-->  [eng.N5]   removing filler is a specific application of clarity-over-brevity
[eng.N4] --supports--> [eng.N5]   English identifiers are clearer to a wider audience
