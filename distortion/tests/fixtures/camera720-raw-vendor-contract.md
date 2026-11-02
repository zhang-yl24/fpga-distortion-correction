# Raw 720p recorded CPU fixture

`camera720-raw-vendor-contract.json` contains the reset-scope fields and compiler
diagnostic records used by `test_camera720_raw_vendor_diagnostics.py`. They were
extracted from the locally retained raw 720p build and vendor compile log; the
original input hashes are recorded in `OriginalInputSHA256`.

This fixture lets parser and rejection tests run from a clean checkout without
`distortion/work`. Source path separators are normalized to `/` for host-native
`Path.name`; the original source paths remain recorded in the frozen local
evidence. Only the nine relevant vendor zero-bit diagnostic rows are retained.

The fixture does not replace a native build receipt, prove compiled-source
identity, authorize reset exceptions, or grant hardware approval. Production
auditors do not import it. Tests which reject invalid bound claims do so before
reading any compiled source or full native log.
