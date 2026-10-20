# Firmware collection maintenance

This folder owns the current baseline firmware catalog. Preserve source-family separation, upstream commit provenance and the private repository boundary. Do not publish private PC source through the public Android repository. Application binaries/releases and stable channels are outside this catalog.

When developing firmware, update catalog.json and its source/ref/path/profile coverage in the same change. Keep source/toolchain versions explicit. New matching sketch entrypoints must fail coverage if uncatalogued. Move a tracked branch pointer deliberately when the active development line changes; nightly checks follow only declared sources. Do not silently merge experimental mission, manual runtime or dedicated motor protocols.

Run catalog/package regressions and every affected actual target with pinned dependencies. Complete collection packaging requires all 11 profiles, exact source generation, image CRC/hash verification, explicit flash offsets and copied guides. Never upload merged/NVS images, provisioning secrets or private generated profiles. Experimental mission and unused driver variants remain excluded; motor direction confirmation stays false. Compile success is not electrical/HIL qualification.

Keep firmware-collection a private draft. Publish LATEST.json only after a complete successful build; preserve prior bundles. Missing/failed profiles must not advance latest. The nightly workflow and workflow_dispatch run from default main, so install workflow/catalog changes there without merging unrelated application branches. Future firmware families require expanding the catalog count/manifest tests and docs deliberately.
