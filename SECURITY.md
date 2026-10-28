# Security policy

## Scope

This private repository holds source code, tools and documentation for a native recompilation of a PlayStation 3
game. Security here means two things: no secrets or credentials in the repository, and no proprietary or
personal data leaving the developer's machine.

## Reporting

Report a suspected leak or vulnerability privately to the repository owner (GitHub private vulnerability
reporting, or a direct message). Do not open a public issue, and do not paste the leaked value into the report:
give the path, commit and type of data.

## If something sensitive was committed

1. Stop: do not push further, and do not try to "fix" history yourself.
2. Revoke or rotate any credential first; deleting a commit does not un-leak it.
3. Report the path and commit hashes to the owner. History rewriting (`git filter-repo`) is done only by the
   owner, with every collaborator re-cloning afterwards.

## Rules

- No tokens, passwords, cookies or keys in files, commit messages, logs or CI configuration. Use GitHub Actions
  secrets only if a workflow truly needs one; the current workflows need none.
- Local configuration with credentials (for example an RPCN account file) stays in Git-ignored paths.
- CI never receives game data, lifted code, binaries, dumps or traces, and uploads no artifacts.
- Enable GitHub secret scanning and push protection where the plan allows.
