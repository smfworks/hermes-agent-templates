---
name: bourne-incident-response
description: >-
  Use when the owner reports a live security incident: suspected account
  compromise, lost device, credential leak, or doxx attempt. Skip intake and
  act.
---
# Bourne Bot incident response

If something is happening now, skip scoping and act. State the first step in one line, then the checklist. Never ask for passwords or codes.

## Account compromise
1. Secure the primary email first; it resets everything else.
2. Revoke all active sessions and app passwords.
3. Change the password and re-enroll MFA, preferring passkeys or a hardware key.
4. Check forwarding rules, filters, recovery email and phone.
5. Rotate every reused password.
6. Warn contacts about messages sent in your name.

## Lost device
1. Locate, lock, or remote-erase from the platform's find-my-device service.
2. Revoke the device's sessions on key accounts.
3. Change passwords stored or open on it.
4. Call the carrier: suspend the line, confirm the account PIN.
5. Replace any hardware key that was with it.

## Credential leak
1. Rotate the leaked credential and every place it was reused.
2. Turn on phishing-resistant MFA there.
3. Expect targeted phishing that references the leak.

## Doxx attempt
1. Document: screenshots with URLs and timestamps.
2. Report to the platforms hosting it.
3. Lock social accounts; remove location and family details.
4. Run data-broker opt-outs.
5. Freeze credit at all three bureaus.
6. Alert family and anyone else exposed.
7. Involve police if there is any threat of harm.

## Financial exposure
Credit freezes, transaction alerts, virtual cards for low-trust merchants, and a call to the bank's fraud line.

Close with residual risk and one follow-up check the owner should do in 24 to 72 hours.

## Hermes (this template)

Tool names only. The checklists above do not change.

- Incident phrases are in `SOUL.md`. Skip intake. Say the first step from `SOUL.md` in one line. Do not wait on `skill_view` for that line. This skill is the checklist after that line.
- A non-secret follow-up note uses the `memory` tool. Never store a password, code, or account number.
- No terminal tool. No web tool. Do not log in to the owner's accounts.
- First run is when `memories/USER.md` has no intake record. These phrases skip that intake even when it has not been saved yet.
