# COMMUNICATION AUTHORIZATION POLICY

Status: Canonical
Applies to: All agents, all models, all execution contexts in OpenClaw

## Principle
Agents do not communicate externally unless explicitly authorized by the user for a specific purpose.

External communication includes (non-exhaustive):
- Sending messages (Telegram/SMS/Email/Slack/Discord)
- Posting to webhooks or HTTP APIs
- Opening public network listeners (HTTP/WS servers)
- Accepting inbound commands from the network

## Default posture (deny by default)
1) No public listeners.
   - Services must bind to localhost (127.0.0.1 / ::1) unless explicitly required.
2) No outbound messages.
   - Agents may draft content, but do not send without explicit approval.
3) No inbound command acceptance.
   - Any webhook/bot must enforce an allowlist (e.g., chat_id/user_id).
4) No credential disclosure.
   - Never print secrets/tokens/keys. Store in runtime credentials only.

## Allowed external communication (only with explicit direction)
External actions are permitted only when:
- The user has requested the action explicitly, AND
- The mechanism is protected:
  - allowlist (chat_id/user_id/email allowlist), AND/OR
  - shared secret or token, AND
  - explicit apply/confirm gate for state-changing actions

## Required controls for any external action
- An explicit “apply” flag + confirmation phrase for irreversible or public actions.
- An allowlist check for inbound messages (unknown senders ignored).
- Logging to an append-only audit log (what was sent, when, by whom, where).

## Implementation note
Doctrine is read-only to agents. Agents may propose patches; humans apply them.

One-line rule:
**Draft freely. Send only on explicit user command, through gated and allowlisted channels.**
