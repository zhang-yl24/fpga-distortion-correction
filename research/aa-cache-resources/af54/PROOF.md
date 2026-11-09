# Ordinal / raster contract

For the exact native AA macro-32, group-64 traversal, each accepted query has:

- raster[23:21] = 0 because 0 <= raster <= 1920 × 1080 - 1 < 2^21.
- raster[5:0] = {query_ordinal[8:6], query_ordinal[2:0]}.
- tag[24] is an independent geometry mask and is retained explicitly.

An 8 × 8 tile contributes 64 queries: ordinal[2:0] is the column within the tile; ordinal[5:3] is its row. Eight horizontal tiles form a width-64 group; ordinal[8:6] selects the tile. Each tile-row band has 512 queries. A full 32-row group has 2048 queries, and the final 24-row group has 1536 queries; both are multiples of 512. The image width 1920 and macro-column offsets are multiples of 64, so raster modulo 64 equals column modulo 64. All transitions preserve raster = row × 1920 + column.

The independent exact-transition model in check_traversal.py enumerates 2,073,600 unique raster positions and verifies the identity at every position, including 46,080 positions in the final 24 rows. It is a mathematical model of the native traversal, not a full RTL frame simulation.

The FIFO stores mask plus raster[20:6], a 16-bit representation. Coordinates use 38 bits, making actual FIFO width 54 rather than 63. The reduction is (63 - 54) × 4096 = 36,864 logical payload bits, with no physical-resource claim.

Reconstruction uses issued_count[8:0] + store_query_accept so replacement-head loading uses the next ordinal on the issue edge. The reconstructed full tag is latched into the existing head register and remains stable through stalls. Admitted-count checks reject high-bit or low-bit contract violations before query FIFO admission, including when FIFO/generation pressure blocks progress. The invalid token is rejected, but already valid traffic can advance on the detection edge.

The caller must preserve every query and its order, including masked coordinates. Arbitrary tags, raster-order scanning, dropped queries or skipping masked coordinates violate this contract. A matching image size alone is insufficient. The guard checks binary values; no X/Z hardware-protection claim is made. Reset/frame acceptance restarts ordinals; the model's post-last invalid coordinate is outside the accepted-frame domain.
