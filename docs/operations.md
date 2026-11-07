# CI operations and upgrades

## Shared framework updates

1. Create a feature branch in `octacel-ci` and add tests for script changes.
2. Run the local checks and exercise the new shared workflow in a disposable consumer repository.
3. Open PRs in Forgejo and the GitHub mirror. Forgejo is the authoritative CI source during repository migration.
4. After human review and merge, record a version tag and its full commit SHA. Update one consumer's `.forgejo/workflows/ci.yml` in a separate PR and run the fixture workflows before rolling out the pin.

The workflows and their referenced actions are pinned by commit SHA or image digest. `versions.json` is the human-readable inventory; `scripts/validate_workflow_pins.py` checks the workflow files.

## Local checks

From the framework repository:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
python3 scripts/validate_workflow_pins.py .forgejo/workflows
python3 scripts/validate_workflow_pins.py .github/workflows
actionlint .forgejo/workflows/*.yml
```

The self-check installs pinned actionlint after verifying its SHA-256, parses JSON/YAML, runs unit tests, checks shell syntax, and validates external action/image pins.

## Runner cleanup and limits

Jobs use no cache and do not mount a host runtime socket. Container builds use a job-local VFS store and remove the temporary OCI archive. The publisher removes its registry auth file immediately after the push and records the pushed digest and SBOM as a workflow artifact. The runner executes one job at a time on the currently available organization runner. The job timeout is 10–60 minutes by profile. Per-repository concurrency is non-cancelling so a new push cannot make required checks appear green while earlier checks are cancelled.

The runner's rootless job containers do not make a shared sensitive host safe for hostile code. See [security model](security-model.md) for the VPS61 limitation and required review policy.

## GitHub mirror

Keep a GitHub mirror while the subscription is active. Push the same source changes to both repositories and open a PR in each. Forgejo Actions is authoritative; the GitHub mirror does not run a competing pipeline. Keep mirror-push credentials outside repository content and use minimum write scope.
