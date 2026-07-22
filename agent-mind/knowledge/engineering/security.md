---
domain: security
cluster: engineering
summary: "Application security in code: input validation at trust boundaries, injection prevention, least privilege, defense in depth, fail securely, secrets management, standard crypto, minimal attack surface"
tags: [injection, sql, xss, csrf, authentication, authorization, secrets, crypto, owasp, validation, sanitize, least-privilege]
updated: 2026-06-25
related:
  # maintainability owns the maintainability<->security tension edge (unidirectional)
  - domain: engineering/architecture
    type: supports
    edge: "Stable contracts (A3) make security validation points explicit and auditable"
  - domain: engineering/systems
    type: supports
    edge: "SE7 fail-fast at startup catches misconfigured secrets before serving traffic"
---

# Security — Application (Code-Level)

> **Scope**: Application-level security in source code.
> For infrastructure, network, physical, or occupational safety — see the relevant skill.

## [eng.S1] Validate all input at every trust boundary
**Confidence**: high
**Severity**: critical
**Context**: web-backend, api, cli
**Updated**: 2026-06-25
**Evidence**: OWASP Top 10 A03:2021; CWE-20
**Trigger**: Data crosses a trust boundary — from user input, API response, message queue, file read, or env var — and flows into application logic without validation.
**Directive**: Validate type, range, shape, and encoding at the boundary before the data enters any business logic. Use a schema validator. Reject or sanitize on entry.
**Because**: Most vulnerabilities trace to unvalidated external input being trusted. Boundary validation keeps the attack surface explicit and centralised. (security)
**Smells**: Request parameters used directly in queries or template rendering; no schema validation on incoming API payloads.
**When not**: Data originating entirely within the same trust zone (same process, same service) — but re-validate when it crosses to another zone.
**See also**: [eng.S2], [eng.S5]

## [eng.S2] Parameterize all dynamic content — never interpolate
**Confidence**: high
**Severity**: critical
**Context**: web-backend, database, api
**Updated**: 2026-06-25
**Evidence**: OWASP A03:2021; CWE-89 (SQL injection); CWE-79 (XSS)
**Trigger**: User-controlled or external data is concatenated, formatted, or interpolated into a SQL query, shell command, HTML output, XML, or LDAP query.
**Directive**: Use parameterized queries, prepared statements, and context-aware output encoding. There is no safe way to interpolate untrusted data — parameterization is the only correct solution.
**Because**: Interpolation is structural trust. Parameterization is structural distrust. Injection has been OWASP Top 3 for decades. (security)
**Smells**: `"SELECT * WHERE id = " + userId`; `f"shell {user_input}"`; `innerHTML = data`; `eval()` with external input.
**When not**: ORMs or query builders that handle parameterization transparently — but verify they actually do.
**See also**: [eng.S1], [eng.S4]

## [eng.S3] Apply least privilege — minimum permissions, minimum scope
**Confidence**: high
**Severity**: critical
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: OWASP; NIST SP 800-53
**Trigger**: A service, DB connection, token, or role has broader permissions than the specific operation it performs requires.
**Directive**: Reduce permissions to the minimum needed. Read-only DB connections for read-only services. Scope tokens to specific actions. Revoke unused permissions.
**Because**: A breach is contained by what the compromised component can reach. Least privilege converts total compromise into a bounded one. (security)
**Smells**: Admin DB connection for read-only service; wildcard IAM policies; an OAuth token with all scopes for a narrow operation.
**When not**: N/A — least privilege is universally applicable.
**See also**: [eng.S4], [eng.S8]

## [eng.S4] Layer security controls — assume any single layer can fail
**Confidence**: high
**Severity**: critical
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: OWASP; NIST SP 800-53
**Trigger**: Security is enforced only at one layer — e.g. only at the API gateway, only at the network perimeter, or only in the frontend.
**Directive**: Add controls at multiple layers. Authentication at the gateway AND authorization in each service. Input validation at the API boundary AND in the business logic. Assume the outer layer will be bypassed.
**Because**: No single control is perfect. Layering limits blast radius: a bypassed auth check at the gateway should not give access to all internal data. (security)
**Smells**: "The firewall handles that"; auth only at the gateway with no enforcement downstream; one permission check at the top of a deep call chain.
**When not**: Internal service-to-service calls within a fully trusted, mTLS-secured network — but document the trust assumption explicitly.
**See also**: [eng.S3], [eng.S5]

## [eng.S5] Fail securely — deny by default, expose generic external errors
**Confidence**: high
**Severity**: critical
**Context**: web-backend, api
**Updated**: 2026-06-25
**Evidence**: OWASP; CWE-636
**Trigger**: An error or unexpected condition causes access to be granted (fail-open), or a detailed error message (stack trace, SQL, file path) is exposed to the caller.
**Directive**: On any error or unrecognised condition, deny access and return a generic error message externally. Log full diagnostic detail internally with structured logging. Default: deny.
**Because**: Fail-open errors have caused more breaches than direct attacks. Detailed errors are reconnaissance for attackers. (security)
**Smells**: `catch(e) { return true; }`; stack traces in HTTP responses; `if (role === null) grant_access()`; verbose SQL errors visible in browser.
**When not**: Internal debugging tools in a fully isolated development environment — but never in production.
**See also**: [eng.S1], [eng.S4]

## [eng.S6] Secrets out of code and out of version control
**Confidence**: high
**Severity**: critical
**Context**: general
**Updated**: 2026-06-25
**Evidence**: OWASP; 12-factor app Config principle
**Trigger**: A password, API key, token, certificate, or other secret appears in source code, a config file that could be committed, or CI/CD logs.
**Directive**: Remove it immediately. Use environment variables, a secret manager (Vault, AWS Secrets Manager, GCP Secret Manager). Treat any committed secret as compromised and rotate it.
**Because**: Source code is shared, archived, and often public. A secret committed to git is effectively public from that moment. (security)
**Smells**: Hardcoded API key in source; `.env` file in the repo; credentials in CI run logs; secrets baked into Docker image layers.
**When not**: N/A — secrets must never appear in code or committed files.
**See also**: [eng.S3]

## [eng.S7] Use established cryptography — never implement your own
**Confidence**: high
**Severity**: critical
**Context**: general
**Updated**: 2026-06-25
**Evidence**: OWASP Cryptographic Storage; Schneier's Law
**Trigger**: Code implements a cryptographic primitive, key exchange protocol, token signing, or password hashing from scratch.
**Directive**: Use vetted libraries: libsodium, BouncyCastle, or stdlib crypto. Use bcrypt/argon2 for passwords. Use well-reviewed JWT libraries for tokens.
**Because**: Cryptographic implementations have subtle, non-obvious flaws that are invisible in testing and exploitable at scale. (security)
**Smells**: Home-grown hashing function; custom JWT signing; "XOR encryption"; "it just needs to be obfuscated."
**When not**: N/A — custom cryptography is never acceptable in production systems.
**See also**: [eng.S5]

## [eng.S8] Minimize the attack surface
**Confidence**: high
**Severity**: major
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: OWASP; CWE-1053
**Trigger**: Endpoints, features, permissions, or capabilities exist in production that aren't actively used, or interfaces are broader than what callers actually need.
**Directive**: Disable unused endpoints. Remove unused features. Shorten token lifetimes. Narrow API interfaces to what callers genuinely need.
**Because**: Attack surface is the upper bound on exposure. Structural reduction is more durable than ongoing vigilance. (security)
**Smells**: Debug endpoints active in production; overly broad CORS policies; admin interfaces on the public internet; tokens that never expire.
**When not**: N/A — minimizing attack surface is always beneficial.
**See also**: [eng.S3], [eng.S4]

## Internal relationships
[eng.S1] --enables-->  [eng.S2]   must validate at boundary before parameterizing makes sense
[eng.S1] --enables-->  [eng.S5]   boundary validation is a prerequisite for knowing what to deny
[eng.S3] --supports--> [eng.S4]   least privilege is one concrete layer in defense in depth
[eng.S4] --supports--> [eng.S5]   multiple layers include failing securely as one of them
[eng.S6] --supports--> [eng.S3]   removing secrets from code is part of minimizing privilege surface
[eng.S7] --supports--> [eng.S5]   standard crypto fails securely; custom crypto fails unpredictably
[eng.S8] --supports--> [eng.S3]   smaller attack surface = fewer permissions needed
[eng.S8] --supports--> [eng.S4]   fewer exposed capabilities = fewer layers to defend
