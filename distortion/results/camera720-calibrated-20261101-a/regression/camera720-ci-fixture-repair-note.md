# Authorized test-only follow-up

The earlier read-only diagnosis has now been followed by an explicitly authorized local repair, without a push. Only `tests/test_camera720_output_prepare.py` and `tests/test_camera720_calibrated_preparation.py` changed.

Before editing, the current calibrated build, route reassessment, reset proof, system simulation and recursively referenced JSON input closures were searched: 85 JSON records, 12,915 hash references and 910 distinct local inputs. Neither test file was bound. The result and pre-edit test hashes are retained in `camera720-ci-fixture-binding-review-a.json`.

Both fixtures now create an inert private `pds_shell.exe` before their first inventory recipe and explicitly pass its path. No installed PDS is needed to assemble the CPU fixtures. For the two mocked native lifecycle tests, only the runner module's `os` reference is replaced by a local namespace while `Popen` remains mocked. A new negative test confirms that the actual non-Windows guard still rejects execution and launches no process. The production Windows-only guard and executable/canonical/hash checks are unchanged.

Windows validation: **30 tests passed, 25 subtests passed**, 89.07 seconds. JUnit is `camera720-ci-fixture-windows-a.xml`; exact hashes and command are in `camera720-ci-fixture-repair-result-a.json`. The targeted diff whitespace check also passed. No PDS, UART, JTAG, hardware operation or push occurred.

Pure POSIX path semantics were checked separately: the private POSIX fixture path is absolute and has the expected basename, while the Windows default string is relative on POSIX. This is not a Linux test run. The existing WSL executable returned `Wsl/EnumerateDistros/Service/E_ACCESSDENIED` when listing distributions; no permission escalation, download or installation was attempted. GitHub Actions and the entire expanded Linux wildcard suite remain unverified.
