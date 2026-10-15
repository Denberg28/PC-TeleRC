#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT
for core in 2 3; do
  g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -g \
    -DESP_ARDUINO_VERSION_MAJOR="$core" -Istubs test_rover.cpp -o "$build_dir/test-$core"
  ASAN_OPTIONS=detect_leaks=0 "$build_dir/test-$core"
done
