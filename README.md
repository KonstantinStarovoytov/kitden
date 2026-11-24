# CPU and memory of Kitden

Written by `.github/workflows/use.yml` on `main`; how it measures is in `docs/development.md` (CPU and memory). Each cell is the median, then the lowest and highest run. Page series 1: numbers of another series are not shown. The gateway columns show the newest gateway series.

## Releases

A backfill installs each release with the dependencies of its release day; a night installs the newest release with that night's newest dependencies. CPU seconds depend on the CPU, so compare rows of one CPU model.

| Version | Peak memory (MB) | CPU to ready (s) | Idle CPU in 30 s (s) | Growth (MB) | Sample (items, bytes) | CPU | Measured |
|---|---|---|---|---|---|---|---|
| 0.3.0 | 45.437 (45.261–45.634) | 0.39 (0.39–0.39) | 0.07 (0.06–0.08) | 0.0 (0.0–0.0) | 548, 343345 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.4.0 | 46.465 (46.354–46.649) | 0.39 (0.39–0.4) | 0.07 (0.06–0.09) | 0.0 (0.0–0.0) | 548, 332385 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.5.0 | 46.129 (45.982–46.313) | 0.39 (0.39–0.39) | 0.07 (0.07–0.09) | 0.0 (0.0–0.0) | 548, 332005 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.6.0 | 46.285 (46.129–46.584) | 0.39 (0.38–0.4) | 0.07 (0.06–0.08) | 0.0 (0.0–0.0) | 548, 332005 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.6.1 | 46.375 (46.215–46.395) | 0.39 (0.39–0.39) | 0.07 (0.05–0.09) | 0.0 (0.0–0.0) | 548, 332005 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.6.5 | 46.502 (46.285–46.567) | 0.39 (0.38–0.42) | 0.07 (0.07–0.09) | 0.0 (0.0–0.0) | 548, 338033 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.7.0 | 46.875 (46.801–47.051) | 0.44 (0.44–0.48) | 0.07 (0.06–0.09) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.7.1 | 46.932 (46.834–47.067) | 0.44 (0.44–0.44) | 0.08 (0.05–0.09) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.7.2 | 46.883 (46.723–47.165) | 0.44 (0.44–0.48) | 0.07 (0.06–0.09) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.8.0 | 46.957 (46.797–47.01) | 0.45 (0.45–0.45) | 0.07 (0.06–0.09) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.9.0 | 47.088 (46.981–47.231) | 0.44 (0.44–0.45) | 0.07 (0.05–0.09) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.9.1 | 47.047 (47.006–47.268) | 0.45 (0.44–0.46) | 0.07 (0.05–0.09) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.9.2 | 47.022 (46.94–47.411) | 0.45 (0.44–0.46) | 0.06 (0.05–0.08) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.10.0 | 46.993 (46.78–47.12) | 0.44 (0.44–0.45) | 0.07 (0.06–0.08) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.10.1 | 46.862 (46.715–47.088) | 0.45 (0.44–0.46) | 0.07 (0.06–0.1) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 7763 64-Core Processor | backfill 2026-11-21 |
| 0.10.3 | 46.383 (46.227–46.51) | 0.3 (0.3–0.31) | 0.09 (0.07–0.1) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 9V45 96-Core Processor | night 2026-11-23 |
| 0.11.1 | 46.576 (46.404–46.78) | 0.25 (0.24–0.26) | 0.03 (0.02–0.04) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 9V45 96-Core Processor | night 2026-11-24 |

Charts of peak memory and CPU to ready by release: https://konstantinstarovoytov.github.io/kitden-sdlc/desk/#use

## The last 14 nights

A is the newest release, B is `main` that night, measured in turn in the same job.

| Night | A | B | Peak A | Peak B | CPU to ready A | CPU to ready B | Idle CPU B | Growth B | Gateway idle CPU B | Gateway growth B | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-24 | 0.11.1 | main@68fd56a | 46.576 (46.404–46.78) | 46.662 (46.35–46.748) | 0.25 (0.24–0.26) | 0.25 (0.24–0.26) | 0.03 (0.02–0.05) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) | 0.004 (0.0–0.008) | — |
| 2026-11-23 | 0.10.3 | main@9e5f6fd | 46.383 (46.227–46.51) | 46.428 (46.379–46.633) | 0.3 (0.3–0.31) | 0.31 (0.3–0.33) | 0.08 (0.08–0.11) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) | 0.016 (0.0–0.033) | — |
| 2026-11-22 | 0.10.1 | main@f38818b | 46.658 (46.588–46.768) | 46.678 (46.588–46.842) | 0.45 (0.45–0.46) | 0.45 (0.44–0.45) | 0.07 (0.06–0.08) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) | 0.012 (0.0–0.021) | — |
| 2026-11-21 | 0.10.1 | main@e7e5e31 | 46.486 (46.404–46.58) | 46.35 (46.309–46.473) | 0.25 (0.25–0.27) | 0.25 (0.25–0.26) | 0.03 (0.03–0.04) | 0.0 (0.0–0.0) | — | — | — |
