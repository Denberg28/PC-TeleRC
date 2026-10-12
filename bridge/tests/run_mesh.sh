#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
flags=()
if [[ "${SANITIZE:-0}" == 1 ]]; then flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie -no-pie); fi
g++ -std=c++17 -Wall -Wextra -Werror "${flags[@]}" -Ibridge/tests/stubs -Ibridge/TeleRCMesh bridge/tests/mesh_core_test.cpp -lcrypto -o "$build_dir/mesh"
"$build_dir/mesh"

g++ -std=c++17 -Wall -Wextra -Werror "${flags[@]}" -Ibridge/tests/stubs -Ibridge/TeleRCMesh bridge/tests/mesh_firmware_test.cpp -lcrypto -o "$build_dir/firmware"
"$build_dir/firmware"
