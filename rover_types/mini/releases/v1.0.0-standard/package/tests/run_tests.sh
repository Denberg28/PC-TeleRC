#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT
for core in 2 3; do
  for driver in 1 2 3 4 5; do
    for count in 2 4; do
      flags=(-DESP_ARDUINO_VERSION_MAJOR="$core" -DTELERC_DRIVER="$driver" -DTELERC_MOTOR_COUNT="$count")
      if [[ "$driver" == 4 ]]; then
        flags+=(-DTELERC_SUPPLY_MAX_MV=12000 -DTELERC_MOTOR_RATED_MV=12000 -DTELERC_BTS_LOGIC_VERIFIED=1)
      fi
      g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -g \
        "${flags[@]}" -Istubs test_rover.cpp -o "$build_dir/test"
      ASAN_OPTIONS=detect_leaks=0 "$build_dir/test"
    done
  done
done
# Invalid electrical declarations must fail at compile time.
for invalid in '-DTELERC_DRIVER=9' '-DTELERC_MOTOR_COUNT=6' '-DTELERC_PWM_HZ=30000' \
  '-DTELERC_SUPPLY_MAX_MV=9000' '-DTELERC_MOTOR_RATED_MV=3000' \
  '-DTELERC_DRIVER=4 -DTELERC_SUPPLY_MAX_MV=12000 -DTELERC_MOTOR_RATED_MV=12000'; do
  read -r -a args <<< "$invalid"
  if g++ -std=c++17 -x c++ -fsyntax-only "${args[@]}" ../TeleRC_MiniRover/HardwareProfile.h >"$build_dir/negative.log" 2>&1; then
    echo "FAIL: invalid configuration accepted: $invalid"; exit 1
  fi
  if ! grep -q 'static assertion failed' "$build_dir/negative.log"; then cat "$build_dir/negative.log"; exit 1; fi
done
echo 'PASS: six invalid hardware configurations rejected at compile time'
