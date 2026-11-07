#!/usr/bin/env bash
set -euo pipefail

root="${1:-.}"
if [[ ! -d "$root" ]]; then
  printf 'systemd validation root does not exist: %s\n' "$root" >&2
  exit 2
fi
root="$(cd "$root" && pwd -P)"
mapfile -d '' quadlet_files < <(
  find "$root" -type f \
    \( -name '*.build' -o -name '*.container' -o -name '*.image' -o -name '*.kube' \
       -o -name '*.network' -o -name '*.pod' -o -name '*.volume' \) \
    -not -path '*/.git/*' -not -path '*/.terraform/*' \
    -not -path '*/node_modules/*' -not -path '*/vendor/*' -print0
)
mapfile -d '' systemd_files < <(
  find "$root" -type f \
    \( -name '*.path' -o -name '*.service' -o -name '*.socket' -o -name '*.timer' \) \
    -not -path '*/.git/*' -not -path '*/.terraform/*' \
    -not -path '*/node_modules/*' -not -path '*/vendor/*' -print0
)

if ((${#quadlet_files[@]} == 0 && ${#systemd_files[@]} == 0)); then
  echo 'No Quadlet or systemd units found; this check is not applicable.'
  exit 0
fi

declare -A checked_directories=()
for unit in "${quadlet_files[@]}"; do
  directory="$(dirname "$unit")"
  if [[ -n "${checked_directories[$directory]:-}" ]]; then
    continue
  fi
  checked_directories[$directory]=1
  echo "Validating Quadlet files in ${directory#"$root"/}"
  QUADLET_UNIT_DIRS="$directory" \
    /usr/lib/systemd/system-generators/podman-system-generator --user --dryrun
done

for unit in "${systemd_files[@]}"; do
  echo "Verifying systemd unit ${unit#"$root"/}"
  systemd-analyze verify "$unit"
done

printf 'Validated %s Quadlet and %s systemd unit file(s).\n' \
  "${#quadlet_files[@]}" "${#systemd_files[@]}"
