# 720p portable CPU regression evidence

Windows CPU tests recorded on 2026-11-02 (Asia/Shanghai). No EDA or hardware
execution occurred. `regression.json` binds the modified tests, workflow and
recorded fixture, and lists all skipped integration cases explicitly.

- Working repository: 1759 tests and 482 subtests passed.
- Updated vendor/final-C tests: 23 tests and 8 subtests passed.
- Independent source snapshot including tracked calibration evidence but no
  retained native `work/build`: 1752 tests and 490 subtests passed, 12 existing
  native-evidence integration cases skipped.

The source-snapshot run includes the final-C test added to CI. Its test count is
therefore not identical to the earlier working-repository run. These records do
not claim a Linux or remote GitHub Actions run.
