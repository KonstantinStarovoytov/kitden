# CPU and memory of Kitden

Written by `.github/workflows/use.yml` on `main`; how it measures is in `docs/development.md` (CPU and memory). Each cell is the median, then the lowest and highest run. Page series 1: numbers of another series are not shown.

## Releases

A backfill installs each release with the dependencies of its release day; a night installs the newest release with that night's newest dependencies. CPU seconds depend on the CPU, so compare rows of one CPU model.

| Version | Peak memory (MB) | CPU to ready (s) | Idle CPU in 30 s (s) | Growth (MB) | Sample (items, bytes) | CPU | Measured |
|---|---|---|---|---|---|---|---|
| 0.10.1 | 46.486 (46.404–46.58) | 0.25 (0.25–0.27) | 0.03 (0.02–0.03) | 0.0 (0.0–0.0) | 548, 348445 | AMD EPYC 9V45 96-Core Processor | night 2026-11-21 |

Charts of peak memory and CPU to ready by release: https://konstantinstarovoytov.github.io/kitden-sdlc/desk/#use

## The last 14 nights

A is the newest release, B is `main` that night, measured in turn in the same job.

| Night | A | B | Peak A | Peak B | CPU to ready A | CPU to ready B | Idle CPU B | Growth B | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-21 | 0.10.1 | main@e7e5e31 | 46.486 (46.404–46.58) | 46.35 (46.309–46.473) | 0.25 (0.25–0.27) | 0.25 (0.25–0.26) | 0.03 (0.03–0.04) | 0.0 (0.0–0.0) | — |
