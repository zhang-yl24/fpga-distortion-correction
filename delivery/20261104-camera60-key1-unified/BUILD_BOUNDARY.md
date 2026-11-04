# Public base and reconstruction boundary

Fixed public base: https://github.com/zhang-yl24/fpga-distortion-correction/tree/5d53319c4167596cd2f577c65a3b2d8dfd54494d

The existing public BUILD_REPRODUCTION.md describes an older 130-input / 49-import preparation flow. U uses a different 152-input / 66-import closure. That helper must not be represented as a U build entrypoint.

Read-only comparison against the fixed public tree found 121 exact Git-blob matches. Six additional firstparty inputs have checked public derivations: frame control, command parser and statistics normalize line endings/include paths; arbiter and store match the experimental opt-in branch after normalization; cache matches that branch byte-for-byte. The candidate has 17 remaining known changed exports/relocations and eight remaining legal native dependencies/constraints. These counts do not make this four-file package self-contained.

A lawful reconstruction requires the user's authorized F435 native dependency copy and matching local constraints, the public phase-contract patch and its guarded patch-base procedure, U's firstparty changes, and a separately reviewed build preparation procedure. Vendor-derived controller files are not included here. The already-public phase patch is referenced rather than repackaged:
https://github.com/zhang-yl24/fpga-distortion-correction/tree/5d53319c4167596cd2f577c65a3b2d8dfd54494d/delivery/20261104-op-camera-key1-phase-contract

The firstparty KEY module is already public in the same fixed tree under delivery/20261104-op-camera-key1-raw-corr. Its older bit is not the U bit and must not be relabelled.

Any future local preparation helper must require an existing authorized native copy and its locally supplied identity data; verify inputs before copying; reject unknown absolute includes; rewrite only bound includes in a new derived tree; preserve original bytes and record export/compile transformations; retain the candidate's import order; and stop before EDA. No complete private input inventory is published by this package. No vendor/IP files, license files, ADF or private logs are included.

The original F435_UNIFIED_REVIEW.patch contains local absolute paths and is not shipped. The four narrow exports are the review surface, not a turnkey full integration patch. Neither independent public reconstruction nor identical bit bytes are promised. Rebuilds require their own final timing and board validation.
