# Project CI contract

`.octacel/project.json` is the project's explicit contract with shared CI. It describes real project commands, dependencies, deployment targets, resource requests, and OpenBao references. Do not replace missing tests or checks with `true`, empty scripts, skipped jobs, or placeholder success commands.

## Project profiles

Supported `projectType` values are `nextjs`, `node-backend`, `typescript-library`, `browser-extension`, `containerized-backend`, `saas`, `supabase-postgres`, `terraform-infrastructure`, `terraform-module`, and `podman-service`. The validator rejects unknown or incomplete profiles. The checked-in schema is `.octacel/project.schema.json`.

Node profiles require an exact Node version, package manager, and argument arrays for install, format, lint, typecheck, build, and unit test commands. A command is an argv array, never a shell string; `scripts/run_project_command.js` uses `spawnSync` with shell execution disabled. Optional Node integration tests run only when the contract supplies a real command.

Terraform profiles require an exact version, a repository-relative root, `fmt -check`, backend-free initialization, and `validate`. CI never runs `terraform apply` or `destroy` and never reads a remote backend.

## PostgreSQL and Supabase

The database profile requires existing, non-empty directories for migrations, pgTAP, RLS, and organization/tenant isolation SQL. It also requires separate migration, schema, RLS, tenant-isolation, and application-integration commands. All tests run against a disposable pinned PostgreSQL service. The workflow enables pgTAP, applies project migrations, checks existing migration files are append-only, and executes each SQL suite. It has no production database URL or service secret.

Each SQL test file must contain a pgTAP plan and the planned number of assertions. Assertion failures, missing plans, empty test directories, or migration failures block CI. The repository author remains responsible for making the SQL suites exercise the application's actual policies, roles, organizations, and tenant boundaries.

## Container profiles

`container.image` must be `git.octacel.com/octacel/<repository>`. `container.containerfile` is a repository-relative file. Architectures must match selected measured target profiles. The current runners are AMD64; ARM64 or mixed-architecture images fail until an isolated native ARM64 runner exists. The default builder rejects privileged host access, does not mount a host socket, and deletes its temporary archive and job-local image data.

Static Containerfile checks and a successful build do not prove production startup, filesystem permissions, network policy, health checks, or runtime service compatibility. Those require a protected infrastructure release workflow and an isolated runtime test.

## Targets and resources

Target IDs are `contabo-vps41-development`, `contabo-vps42-staging`, `contabo-vps61-shared-infra`, `oci-riyadh-amd64`, and `oci-riyadh-arm64`. CPU, memory, and storage are minimum project requests. Contabo comparisons use measured CPU count, installed memory, and root filesystem capacity; root filesystem size is not free space. OCI targets intentionally fail until capacity is measured. A static compatibility pass is not a runtime test.

## OpenBao references

The contract stores references, not values:

```json
{
  "environment": "staging",
  "path": "kv/biomedup/staging#DATABASE_URL",
  "rotation": {"owner": "platform-team", "reviewAfter": "2027-02-01"}
}
```

Use separate paths and policies for development, staging, production, and CI-only credentials. Never add secret values, tokens, recovery shares, live database URLs, or `.env` material to a template or project contract. Ordinary product CI has no OpenBao token and cannot write secrets or change infrastructure. OpenBao provisioning and deployment stay in protected `octaCEL-Infra` workflows.
