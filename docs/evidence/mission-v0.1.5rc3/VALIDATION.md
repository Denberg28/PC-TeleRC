# 0.1.5rc3 qualification

- Full application regression: **269 passed**. Includes the new private-profile, hash/path, incomplete/stale/wrong-version report gates and six AUTO takeover/disarm cases.
- Firmware Python/protocol-peer checks: **8 passed**; firmware source is byte-for-byte unchanged from 0.2.0rc1 in the rc2 candidate. The public firmware manifest is verified before packaging.
- Publish tooling: **13 passed**. Compileall and focused undefined-name/unused-import lint pass; workflow YAML parses successfully.
- All **65 public firmware files** retain exact manifest hashes after a Git checkout with `core.autocrlf=true`; root attributes prevent Windows newline conversion from invalidating firmware provenance.
- Source UI/media self-test: **23 checks pass**, version 0.1.5rc3.
- Native Linux PyInstaller build and frozen UI/media self-test: **23 checks pass**, version 0.1.5rc3. This verifies frozen module/assets/media availability on the available host; it is not a Windows build or Windows qualification.
- The prior rc2 actual ESP32S3 BASE/ROVER/NODE_1/NODE_2 builds, 13 native profiles, 13 ASan/UBSan profiles and ArduRover 4.6.3 SITL evidence are retained under the rc2 evidence and firmware validation folders. They were not rerun for this release-packaging/status-only continuation. The mission transaction client, plan generator and radio source remain unchanged.
- The Windows rc2 workflow rerun (run 39348194206, attempt 2) again failed before steps, with no assigned runner. The rc3 GitHub write was interrupted before updating the branch, so the new Windows workflow has not run. The distribution includes a source patch and a local Windows build command. No verified Windows executable is claimed.
- Physical RF, USB/wiring, power, RC takeover, loss timing, stopping distance and independent accessory cutoff remain unqualified. Candidate status is retained.

The Windows build now removes the old frozen report, waits for the actual GUI executable with a bounded timeout, validates every required boolean result and version, checks report freshness against the executable, and then stages only firmware files matching the public hash manifest. CI preserves portable packages and diagnostics before installer creation. No build gate is bypassed when a runner is unavailable.
