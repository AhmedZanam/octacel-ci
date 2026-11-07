# Forgejo repository and organization settings

Reusable workflows require Forgejo v15 or later and the called framework repository must be public. The installed server reported `15.0.11+gitea-1.22.0`. The active organization runner label is `octacel-org-ci`.

**Current administrator action:** although `octacel-ci` is public, its owning `octaCEL` organization is private. A live template workflow failed during reusable-workflow expansion with `user does not exist`. Forgejo v15’s cross-repository workflow resolver requires the target owner to be publicly resolvable. Either make the organization publicly visible or relocate the public workflow repository to a public owner, then rerun the template workflow. Public organization visibility may reveal membership metadata. This task did not change that setting.

## Apply to a product repository

1. Set the default branch to `main`.
2. In **Settings → Actions**, confirm the organization runner assigned to the `octaCEL` organization can execute workflows from this repository. Do not give unrelated repositories the same runner assignment.
3. In **Settings → Branches**, protect `main`; require at least one approval, dismiss stale approvals, block outdated branches, and require the final CI summary status. Disable direct pushes and force pushes for ordinary contributors.
4. Protect `v*` tags so only release maintainers can create or move them. The release workflow checks semantic version syntax and the repository's version source; tag protection is a Forgejo administrator setting.
5. For a public repository, require human approval before workflows from first-time contributors or forks run. Do not use `pull_request_target`.
6. Confirm the OCI package is associated with the source repository. A package-write token is only used by the post-validation image publisher.
7. Keep secrets and environment approvals out of normal CI. Template repository creation does not copy runner assignments, branch rules, tokens, environment approvals, or team permissions.

The exact status context may differ between Forgejo versions and workflow names. Open **Actions** after the first successful test, inspect the reported status, and require that context in branch protection. Do not guess a context or make branch protection depend on a missing job.

## Template repository setting

After the template implementation PR is merged to `main`, an administrator must open the repository's **Settings → General** page and enable **Template repository**. Do not enable it while the default branch still contains only the initial README. Generated repositories receive files and caller workflows; they do not automatically inherit runner assignments, secrets, branch protection, teams, or organization permissions.

An optional authenticated repository-bootstrap script is included in the template. It only configures branch protection when the operator supplies a Forgejo token and explicit required status context. It does not create tokens or assign runners.
