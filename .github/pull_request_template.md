## Task

T<N>: <topic> — report: `generated/analysis/t<N>/<REPORT>.md`

## Change

<!-- What changed and why. One logical change per PR. -->

## Evidence

- [ ] Focused test(s) for the change: <name> — result
- [ ] Relevant offline suite — result
- [ ] Findings labelled VERIFIED / PARTIAL / HYPOTHESIS / BLOCKED
- [ ] Game build/launch: not run / run with owner authorisation (date, run directory)
- [ ] Default behaviour unchanged, or the change is behind a runtime switch (name it)

## Safety

- [ ] `audit_public.py --staged` passed (ps3recomp: only the 25 inherited upstream items)
- [ ] `tools/github_preflight.py` passed for this branch
- [ ] No game data, firmware, decrypted or lifted game code, extracted SPU modules, captures, dumps, binaries
- [ ] No local user paths, credentials or personal e-mail addresses
- [ ] No other agent's branch or files modified
