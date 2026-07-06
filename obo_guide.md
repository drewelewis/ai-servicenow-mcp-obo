# MCP OBO Security Specification

## 1. Purpose

This document defines a technology-neutral security specification for implementing OAuth On-Behalf-Of (OBO) in a Model Context Protocol (MCP) server.

Goal:
- Establish a normative standard that implementation must follow.
- Preserve user-level authorization boundaries across tool execution.
- Prevent privilege escalation from shared or app-only credentials.

Non-goal:
- Describe a specific codebase.
- Explain one provider SDK in detail.

## 2. Design Principles

1. User identity is the security boundary.
2. Session context is immutable after authentication.
3. Tokens are short-lived, scoped, and never shared across sessions.
4. Least privilege and explicit audience/scope are mandatory.
5. Fail closed on any auth, token, or context ambiguity.

## 3. Threat Model

Primary threats:
1. Token replay across sessions.
2. Cross-user context leakage in concurrent requests.
3. Downstream token over-scoping.
4. Trusting unverified transport headers.
5. Logging or persistence of bearer tokens.
6. Mid-execution token expiry causing partial operations.

Security objective:
- Ensure each downstream call executes with the delegated identity and scopes of the initiating user only.

## 4. Normative Requirements

The words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are normative.

### 4.1 Transport and Incoming Token Handling

1. The MCP ingress layer MUST capture the incoming user token from an authenticated transport boundary.
2. The server MUST validate token issuer, audience, signature, and expiry before any tool/resource execution.
3. The server MUST bind validated user identity to a per-session security context.
4. The server MUST NOT store raw user tokens in global mutable state.
5. The server MUST reject requests with missing or unverifiable user identity.

### 4.2 Session Isolation

1. Each MCP session MUST have an isolated auth context.
2. Tool handlers MUST resolve identity from active request/session context, not process-level variables.
3. Concurrent sessions MUST be safe by construction (no shared per-user token slots).
4. Session teardown MUST clear in-memory auth artifacts associated with that session.

### 4.3 OBO Token Exchange

1. The server MUST perform delegated token exchange using the identity provider token endpoint.
2. The exchange request MUST include explicit subject token and requested downstream scopes.
3. The server MUST request only scopes required for the specific tool action.
4. The token audience/resource MUST match the downstream API being called.
5. Exchange failures MUST fail the tool request with a sanitized auth error.

### 4.4 Token Cache and Lifetime Management

1. Downstream tokens MAY be cached in memory for performance.
2. Cache keys MUST be derived from user identity plus downstream audience/scope tuple.
3. Cache keys SHOULD be non-reversible representations (for example, keyed hash), not raw tokens.
4. Cached tokens MUST honor expiry with a safety buffer of 30-60 seconds.
5. Expired or near-expiry tokens MUST be refreshed before downstream invocation.
6. Tokens MUST NOT be written to disk unless explicitly encrypted and policy-approved.

### 4.5 Tool Execution Path

1. Every downstream call MUST attach bearer token from the active session exchange result.
2. Tool handlers MUST NOT accept caller-supplied downstream tokens directly.
3. The server SHOULD perform preflight auth checks before expensive operations.
4. Partial execution paths SHOULD be idempotent or compensatable when auth fails mid-run.

### 4.6 Error Handling

1. Auth failures MUST be returned with actionable but non-sensitive error messages.
2. Errors MUST NOT include raw tokens, secrets, full JWT payloads, or private key material.
3. The server SHOULD distinguish among:
   - invalid incoming token
   - exchange failure
   - downstream authorization denied
   - downstream transient failure
4. Retries MUST be bounded and only applied to safe failure classes.

### 4.7 Observability and Audit

1. The server MUST emit structured logs with correlation IDs.
2. Logs MUST include user/session identifiers that are non-sensitive and auditable.
3. Logs MUST include token exchange outcome metadata (success/failure, latency, audience/scope).
4. Logs MUST NOT include raw tokens or secrets.
5. Audit records SHOULD map tool invocation to delegated user identity and downstream resource.

### 4.8 Secret and Key Management

1. Client credentials MUST be loaded from secure secret stores or protected environment configuration.
2. Secrets MUST rotate on a defined schedule and on compromise.
3. Certificates SHOULD be preferred over static client secrets for production confidential clients.
4. Build pipelines MUST scan for accidental secret disclosure.

### 4.9 Network and Gateway Controls

1. A gateway SHOULD validate incoming JWTs before traffic reaches MCP runtime.
2. The runtime MUST still validate token claims (defense in depth).
3. TLS MUST be enforced for ingress, token exchange, and downstream APIs.
4. Egress SHOULD be restricted to approved identity and downstream endpoints.

## 5. Reference Flow (Logical)

1. Client sends MCP request with user token.
2. Ingress validates token and establishes session auth context.
3. Tool call requests downstream capability.
4. OBO engine checks cache for valid delegated token.
5. If needed, OBO engine performs token exchange.
6. Tool executes downstream call with delegated bearer token.
7. Response and audit metadata are returned.

## 6. Conformance Checklist

An implementation is considered compliant when all items below pass.

### 6.1 Identity and Session

1. Incoming token validation enforces issuer/audience/signature/exp.
2. Session context is per-connection and isolated.
3. No cross-session token reuse is possible.

### 6.2 Token Exchange and Scope Control

1. OBO exchange uses delegated grant semantics.
2. Audience/scope are explicitly constrained per downstream API.
3. Over-broad scopes are rejected by policy.

### 6.3 Operational Security

1. Secrets never appear in logs.
2. Correlation IDs are end-to-end.
3. Exchange latency and failures are observable.

### 6.4 Failure Safety

1. Invalid token requests fail closed.
2. Exchange failures do not fall back to app-wide superuser credentials.
3. Mid-run expiry path refreshes safely or aborts deterministically.

## 7. Validation Test Plan

### 7.1 Functional Tests

1. Valid user token yields successful delegated downstream read.
2. Same user with insufficient role receives downstream authorization failure.
3. Distinct users see only their authorized data boundaries.

### 7.2 Isolation Tests

1. Parallel sessions for different users do not leak identity.
2. Cache hits for one user are never reused for another user.

### 7.3 Negative Security Tests

1. Expired incoming token is rejected.
2. Tampered token signature is rejected.
3. Wrong audience token is rejected.
4. Missing scope is rejected.

### 7.4 Reliability Tests

1. Exchange endpoint transient failure triggers bounded retry.
2. Exchange timeout degrades gracefully with explicit error.
3. Token refresh near expiry succeeds under load.

### 7.5 Auditability Tests

1. Tool call and downstream call share the same correlation ID.
2. Audit stream shows delegated user identity (non-sensitive form).
3. No token or secret material appears in logs.

## 8. Deployment Readiness Gates

Before production rollout, all gates MUST pass:

1. Security review: passed.
2. Conformance checklist: 100% complete.
3. Negative test suite: passed.
4. Secret rotation runbook: documented and tested.
5. Incident response for auth failures: documented.

## 9. Implementation Notes for Teams

1. Treat this document as the source-of-truth spec.
2. Create an implementation matrix mapping each MUST/SHOULD to code locations and tests.
3. Reject pull requests that add authentication shortcuts violating this spec.
4. Re-run conformance and negative tests on every release candidate.
