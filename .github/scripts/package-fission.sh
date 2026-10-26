#!/usr/bin/env bash
# Package an automation module as zip archives deployable on fission.
#
# The Python versions supported on fission are listed in the module's
# manifest.json, under `fission.python-version`. One archive is built for each
# of them, named {slug}-{version}-py{python-version}.zip. Each archive contains
# the module sources and its runtime dependencies, installed for that Python
# version on the fission Python environment (dhi.io/python:<version>-dev, Debian
# 13 on x86_64 with glibc 2.41). When the list is missing or empty, the module
# does not support fission and no archive is built.
#
# Usage: package-fission.sh <module-dir> <output-dir>

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <module-dir> <output-dir>" >&2
  exit 1
fi

module_dir=$(cd "$1" && pwd)
output_dir=$(realpath -m "$2")
manifest="$module_dir/manifest.json"

python_versions=$(
  jq -r '
    (.fission // {})["python-version"] // []
    | if type == "array" then .[] else error("fission.python-version must be a list") end
    | if type == "string" and test("^[0-9]+\\.[0-9]+$") then .
      else error("invalid Python version \(tojson) in fission.python-version, expected X.Y") end
  ' "$manifest"
)
if [ -z "$python_versions" ]; then
  echo "$module_dir does not support fission (no fission.python-version in manifest.json), nothing to package"
  exit 0
fi

if [ ! -f "$module_dir/uv.lock" ]; then
  echo "error: $module_dir has no uv.lock, only uv modules can be packaged" >&2
  exit 1
fi

# Wheels of the fission environment: glibc 2.41, of which manylinux_2_40 is the
# most recent tag supported by uv
python_platform="x86_64-manylinux_2_40"

slug=$(jq -r '.slug' "$manifest")
version=$(jq -r '.version' "$manifest")

umask 022
mkdir -p "$output_dir"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT
sources="$work_dir/sources"
mkdir "$sources"

# Copy the module sources, without tests, documentation, build files and caches
tar -C "$module_dir" \
  --no-wildcards-match-slash \
  --exclude='./tests' \
  --exclude='./docs' \
  --exclude='./dist' \
  --exclude='./.venv' \
  --exclude='./Dockerfile' \
  --exclude='./.dockerignore' \
  --exclude='./*.md' \
  --exclude='./logo.*' \
  --exclude='./mise.toml' \
  --exclude='./poetry.toml' \
  --exclude='./*.zip' \
  --exclude='./coverage.xml' \
  --exclude='./junit.xml' \
  --exclude='./.coverage' \
  --exclude='.*_cache' \
  --exclude='__pycache__' \
  --exclude='*~' \
  -cf - . | tar -C "$sources" -xf -

uv export --project "$sources" --frozen --no-default-groups --no-emit-project --format pylock.toml > "$sources/pylock.toml"

for python_version in $python_versions; do
  echo "Packaging $module_dir for Python $python_version"

  dist="$work_dir/dist-$python_version"
  cp -a "$sources" "$dist"
  uv pip sync --python "$python_version" "$dist/pylock.toml" --target "$dist" --python-platform "$python_platform"

  # Packages without wheels are built from sources. This is fine for pure Python
  # packages (tagged py3-none-any), but compiled ones (tagged linux_x86_64)
  # target the build machine instead of the fission environment
  native_builds=$(grep -l -E '^Tag: .*-linux_' "$dist"/*.dist-info/WHEEL || true)
  if [ -n "$native_builds" ]; then
    echo "error: no wheel compatible with $python_platform for Python $python_version, these packages were compiled on the build machine:" >&2
    for wheel in $native_builds; do
      echo "  - $(basename "$(dirname "$wheel")" .dist-info)" >&2
    done
    exit 1
  fi
  rm -rf "${dist:?}/bin" "${dist:?}/.lock"
  chmod -R a+rX "$dist"

  output="$output_dir/$slug-$version-py$python_version.zip"
  rm -f "$output"
  (cd "$dist" && zip -qr "$output" .)
  echo "Created $output"
done
