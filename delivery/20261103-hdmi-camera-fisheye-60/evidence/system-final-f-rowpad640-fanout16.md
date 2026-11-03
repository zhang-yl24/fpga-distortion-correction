# Implementation-f real system regression

The complete 64×64 system passed two reset epochs with the final f cache fill
address selection, lane launch stage, writer and display updates, and validated
completion pipeline. Source identity:
`0b38f355a21e7728e46e2b1f7d59fd4aad6e621e56a77a6091e8914b798a05db`.
Build ID is `11037003`; all overlay source hashes remained unchanged during the
simulation. This snapshot predates the subsequent native CDC-attribute overlays.

The actual mapper/cache/writer, three-slot capture DMA, DDR return register,
shared arbiters, asynchronous FIFOs and scanout are instantiated. Core and pixel
clocks are 125 MHz and 148.5 MHz. At 64×64 the rowpad profile uses linear index
fallback and a 32/32 row split; native row16/640+440 behavior is covered by the
separate full-resolution engine regression.

The test checked 34 source commits, 33 publications, 32 unique displayed frames
(12 raw, 20 corrected), five repeat displays, and 151,552 displayed pixels.
Source/result writes and memory contents also passed all independent pixel and
CRC comparisons. Both epochs exercised every source slot at least five times,
AR/AW/W stalls, return gaps, shared-service competition and active mode switches.
Underflows and mismatches were zero. Eight intentionally unreserved whole input
frames per epoch exercised source exhaustion; accepted malformed/drop counts
were zero. The busy-reset scenario retained DDR memory and changed input texture
before checking recovery and final drain.

The matching evidence directory contains exact XSim commands/logs, source
hashes, per-epoch counters and the read-only build/interface inventory. This is
functional ownership/CDC-protocol coverage at scaled raster timing; routed
metastability structure, electrical IO and board stability have separate evidence.
