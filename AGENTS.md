# Guest-oracle rules for Codex missions

- Read [the guest-oracle contract](docs/development/guest-oracles.md) before using an established guest oracle as evidence or a gate.
- State the exact proposition supported by an oracle PASS. PASS proves only its documented propositions; do not infer audio, timing, hardware, or hidden state from a visual or integration checkpoint.
- `fmp s` returns to the DOS prompt while Theme of FMP continues in the background. Prompt return marks command completion, not playback completion. Apply the phase rules in the guest-oracle contract when audio matters.
- Preserve established oracle semantics unless the owner explicitly authorizes a revision. When extending an oracle, document the new positive assertion and its non-claims.

# Multiplierless realtime policy

- Read [the normative realtime-target policy](docs/development/multiplierless-realtime-policy.md) before changing machine-time authority, realtime device advancement, stall/catch-up behavior, or deadline scheduling.
- Stop and escalate before treating Linux scheduler elapsed time as normative guest machine time, deriving a catch-up/freeze/clamp rule from Linux behavior alone, granting another device machine-time authority without its platform-time contract, or changing the ESP32-P4 deadline/service model.
- Before blocking a multiplierless migration solely for incomplete physical hardware authority, check whether the owner-approved `LEGACY_COMPATIBILITY_PROFILE` path in that policy applies. Keep any hardware-authority audit result distinct from a compatibility-profile pilot.
- Stop and escalate before inventing a profile without stable, testable existing behavior, presenting compatibility behavior as hardware truth, combining clock-source migration with an unrelated hardware correction, or overriding hardware-qualified semantics with a legacy quirk.
