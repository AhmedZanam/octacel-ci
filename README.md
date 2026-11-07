# octaCEL shared CI

This repository holds versioned Forgejo Actions workflows and validation tools shared by octaCEL projects. Product repositories keep a small caller workflow and a project contract; the shared implementation stays here.

## Forgejo compatibility

The active Forgejo instance reported `15.0.11+gitea-1.22.0` on 2026-11-07. Forgejo v15 supports reusable workflows through `workflow_call`, cross-repository workflow references, input/output contracts, and job expansion. The canonical public framework repository is `https://git.octacel.com/ahmed.al-zanam/octacel-ci`. Its public user owner keeps the `octaCEL` organization private while allowing Forgejo to resolve cross-repository workflow calls. Consumer workflows and internal checkout steps must use this owner and pin a full commit SHA. The GitHub mirror remains at `https://github.com/octaCEL/octacel-ci`. The installed organization runner reports v13.1.0.

Every consumer pins the full commit SHA of this repository in its `.forgejo/workflows/ci.yml`; it must not call `main`, a release branch, or a mutable tag. The `versions.json` file records the pinned action and tool references. Review and test a shared framework upgrade in a consumer PR before changing that pin.

## What runs

The caller validates `.octacel/project.json` against the central JSON Schema and cross-field project contract, then selects only the applicable reusable jobs:

- Node.js quality: install, formatting, lint, type check, build, unit tests, and an optional integration command.
- Supabase/PostgreSQL: a disposable PostgreSQL service, migration-history check, migration and schema commands, pgTAP schema/RLS/tenant-isolation suites, and database-backed integration tests.
- Terraform: pinned Terraform version, formatting, backend-free initialization, validation, TFLint, Checkov, Trivy IaC, ShellCheck, workflow syntax checks, and systemd/Quadlet validation for infrastructure roots.
- Every project: Gitleaks, Semgrep, OSV-Scanner, Trivy, a source SBOM, measured target compatibility, release-ref validation, and a required-check summary.
- Container profiles: a rootless Buildah build, Trivy image scan, SPDX SBOM, and a separate publish workflow after all required checks pass. Images go to Forgejo’s OCI registry with immutable commit-SHA tags; semantic tags are added only for approved `vMAJOR.MINOR.PATCH` tags.

The workflow uses no shared cache or host container socket. The project command runner removes Forgejo/GitHub/OIDC tokens from child processes. Publishing authenticates only after the image has been built and scanned. Ordinary jobs do not deploy, apply Terraform, modify OpenBao, or write production secrets.

## Start a new project

1. Create a repository from `octaCEL/octacel-repo-template` in Forgejo.
2. Run `./scripts/init-project.sh` from the repository root. The tool discovers common conventions and prompts for missing values. It writes `.octacel/project.json` and reports any incomplete settings.
3. Review the generated project contract and fill any real commands or test paths that CI requires. Supabase profiles need non-empty migrations, pgTAP, RLS, and tenant-isolation SQL suites.
4. Choose and add the project license before distributing the project. The template includes license-selection guidance but does not select one for the project owner.
5. Open a pull request. CI runs on the organization runner. Merge only after the required summary and human review pass.
6. For container services, protect `main` and `v*` tags; a successful approved `main` commit publishes the immutable SHA image. A protected semantic tag publishes both SHA and version tags.

See [project contract](docs/project-contract.md), [security model](docs/security-model.md), [Forgejo settings](docs/forgejo-settings.md), and [operations](docs/operations.md).

## Current infrastructure limits

Measured VPS41, VPS42, and VPS61 CPU, memory, root-filesystem size, architecture, and placement are in `profiles/targets.json`. VPS61 is recorded as the shared runner host and is deliberately excluded from application deployment targets. These figures are static capacity inputs; they do not claim free disk, load headroom, or application runtime compatibility. OCI AMD64/ARM64 profiles remain unverified and intentionally fail compatibility checks until provisioned and measured.

Only VPS61’s organization runner was reported online during discovery; it shares a host with Forgejo, OpenBao, and other services. Rootless Podman, no host socket, per-job containers, timeouts, resource limits, and no cache reduce exposure, but they cannot protect sensitive host services against a runner/host-kernel vulnerability or network attack. Do not run unreviewed fork workflows until an administrator has enabled first-run approval and the runner has an independently isolated host/network. See the [security model](docs/security-model.md).

Forgejo and GitHub repositories are mirrored during the transition. Forgejo Actions is the source of CI results; the GitHub mirror does not run a second pipeline.
