# Finite simulation cadence: required publication wording

The sustained bench explicitly limits accepted frames to four. It sends sixteen source frames but disables capture admission when the fourth DMA source is offered. The capture-admission edge is not recorded; it must not be assigned the later 133.333516 ms bank-accept timestamp.

The four accepted frames produce exactly three consecutive new-frame full-scan intervals of approximately 33.333333 ms. Three later scans repeat frame 4. This supports a finite four-frame cadence observation; it does not establish sustained 30 FPS throughout the sixteen-frame input window or uncapped long-run throughput. Dividing four accepted frames by the full input window likewise does not establish a steady 15 FPS bottleneck.

Use actual board unique-presented-frame rates, independent host arrival timing and the measured observation duration for any board throughput claim. Scan refresh rate must not substitute for unique-frame rate. If a shortened observation is necessary under the user's deadline, state its actual duration explicitly and do not call it a completed 600-second stability test.

Read-only source: output/new-next-probe-20261104/assoc2way256-fastpipe-a/sustained-four-frame-cadence-scope-a.json, SHA-256 7d918bf430746bffd9456ec0c7c892c17ef79a313f5e41a721db0a11affe53ca, and its companion Markdown explanation. Existing simulation receipts and frozen provider sources remain unchanged.
