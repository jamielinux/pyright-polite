# Show help
help:
  @just --list

current_version := `hatch version`

# Create changelog entry
changelog:
  mkdir -p .changelog.d
  scriv create --edit

# Tag and changelog
tag:
  #!/usr/bin/env bash
  set -euo pipefail
  if [[ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]]; then
      echo "Not on 'main' branch"
      exit 1
  fi
  entries="$(find .changelog.d -mindepth 1 -maxdepth 1 -type f -name '*.md' | wc -l)"
  if (( entries == 0 )); then
      echo "No changelog entries"
      exit 1
  fi
  echo "Current version: {{current_version}}"
  read -rep "    New version: " version
  sed -i -e "s|^__version__ =.*$|__version__ = \"$version\"|" ./src/*/__about__.py
  scriv collect --version v$version
  git add .changelog.d CHANGELOG.md src/*/__about__.py
  git commit -q -m v$version
  git tag -a v$version -m "Release $version"
  git show

# GitHub Release
release:
  #!/usr/bin/env bash
  set -euo pipefail
  read -rep "GITHUB_TOKEN: " token
  GITHUB_TOKEN="$token" scriv github-release
