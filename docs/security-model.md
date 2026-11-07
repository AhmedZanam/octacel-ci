# CI security model and limits

## Boundaries enforced by the workflows

- Every external action is pinned to a full commit SHA and every job/scanner image is pinned by digest.
- Jobs run on the `octacel-org-ci` organization label with per-job containers, timeouts, bounded runner capacity, and the runner's CPU/memory/PID limits. Workflows do not enable privileged mode, mount Docker/Podman sockets, or share a cache.
- Source checkout uses `persist-credentials: false`. Project-defined argv commands run without `FORGEJO_TOKEN`, `GITHUB_TOKEN`, or OIDC request variables in their child environment.
- Pull-request workflows do not map deployment, OpenBao, production database, or registry credentials into project commands. No OIDC job is enabled.
- Registry login happens in a separate step after the approved image has been built and scanned. The token is used for the package push only; the project build is already complete.
- Source scanners block leaked secrets, Semgrep ERROR findings, Trivy HIGH/CRITICAL findings, and OSV advisories with CVSS 7.0 or above. Unknown OSV severity fails closed. Checkov and TFLint findings are not suppressed. See `policies/severity-policy.json`.
- Semgrep and Trivy write JSON reports only to the temporary job workspace. Validators print aggregate counts and policy outcomes without paths, source excerpts, or secret matches. An `always()` cleanup step deletes both reports; they are not uploaded as artifacts.
- Temporary build archives and registry auth files are removed in an `always()` cleanup step. The runner's job container and workspace are discarded when the job ends.

## Forgejo token behavior

Forgejo v15 automatically exposes a repository-scoped `FORGEJO_TOKEN`/`GITHUB_TOKEN` to Actions steps. Forgejo v15 does not honor per-job `permissions` the way GitHub Actions does. Pull-request tokens are read-only; tokens for trusted pushes may have repository write access. The wrapper removes these variables before executing project commands, but pinned Actions themselves and the runner process can still see their job token. Therefore:

1. Keep the source repository private until its workflow and branch rules are reviewed, or require administrator approval before running fork workflows.
2. Protect `main` and `v*` tags, require review, and do not grant untrusted contributors direct push access.
3. Do not add deployment secrets or OIDC configuration to normal CI. Keep production deployment in a separate protected repository/workflow.
4. Treat any arbitrary job code as able to read the repository and contact the network. The current workflow does not restrict job egress.

Forgejo's own security guide warns that a new branch can introduce a workflow and run it on an available runner, and that containers do not mitigate host-kernel vulnerabilities. Branch protection alone does not stop a repository writer from creating a new branch. Only grant write access to trusted contributors and restrict runner assignment to the intended organization.

## Current VPS61 runner limitation

At discovery, Forgejo 15.0.11 reported the VPS61 organization runner online at runner v13.1.0. VPS61 also hosts Forgejo, OpenBao, Vaultwarden, and monitoring. Runner jobs use rootless Podman with `privileged: false`, no valid volume mounts, and no host socket. These are useful reductions in exposure, but they are not a security boundary against a container/runtime/kernel escape, a runner vulnerability, malicious workflow code, or network access from the host.

Consequently the requirement “CI jobs cannot compromise Forgejo/OpenBao/Vaultwarden on VPS61” cannot be guaranteed by this workflow repository alone. Run only reviewed trusted project changes there. Before accepting arbitrary public-fork workflows, move CI to a disposable isolated host or VM with network egress controls and no co-resident production services; then test the isolation separately. No production infrastructure was changed during this task.

## Security operations

- Review and update `versions.json` and image digests via a PR; do not move a consumer pin until the updated workflows pass in a disposable repository.
- Keep Gitleaks configuration and exception records reviewed; redact all secret scan output.
- Do not use `pull_request_target`, unsafe cache reuse, remote mutable actions, or production secret environments in this repository.
- Report every skipped required job as a failure in the summary. Do not convert tool/network errors to a pass.
