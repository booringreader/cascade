"""im2col + convolution via 3×3 systolic GEMM (matches conv_im2col.v flow)."""

from __future__ import annotations

import numpy as np

from systolic_model import SystolicArray3x3


def im2col_transform(image: np.ndarray, kh: int, kw: int) -> np.ndarray:
    """
    Extract sliding-window patches as columns.
    Returns shape [kh*kw, (H-kh+1)*(W-kw+1)].
    """
    image = np.asarray(image)
    H, W = image.shape
    out_h, out_w = H - kh + 1, W - kw + 1
    n_cols = out_h * out_w
    cols = np.zeros((kh * kw, n_cols), dtype=image.dtype)
    col = 0
    for oy in range(out_h):
        for ox in range(out_w):
            patch = image[oy : oy + kh, ox : ox + kw].reshape(-1)
            cols[:, col] = patch
            col += 1
    return cols


def _get_img_addr(out_px_idx: int, k_idx: int) -> int:
    """Same addressing as conv_im2col.v get_img_addr (4×4 image, 2×2 kernel)."""
    out_y, out_x = divmod(out_px_idx, 3)
    ker_y, ker_x = divmod(k_idx, 2)
    final_y, final_x = out_y + ker_y, out_x + ker_x
    return final_y * 4 + final_x


def conv_via_gemm(image: np.ndarray, filters: list[np.ndarray]) -> np.ndarray:
    """
    4×4 image, list of three 2×2 filters → output [3, 3, num_filters].
    Schedules three output-pixel rows per tile (matches conv_im2col FSM).
    """
    image = np.asarray(image, dtype=np.int8).reshape(4, 4)
    num_filters = len(filters)
    W_MEM = [np.asarray(f, dtype=np.int8).reshape(4) for f in filters]
    out = np.zeros((3, 3, num_filters), dtype=np.int16)

    core = SystolicArray3x3()
    img_flat = image.reshape(-1)

    for tile_idx in range(3):
        core.reset()
        core._cycle((0, 0, 0), (0, 0, 0), core_rst=True)
        core._cycle((0, 0, 0), (0, 0, 0), core_rst=False)

        for feed_counter in range(8):
            a = [0, 0, 0]
            b = [0, 0, 0]
            if 0 <= feed_counter < 4:
                a[0] = int(img_flat[_get_img_addr(tile_idx * 3 + 0, feed_counter)])
                b[0] = int(W_MEM[0][feed_counter])
            if 1 <= feed_counter < 5:
                a[1] = int(
                    img_flat[_get_img_addr(tile_idx * 3 + 1, feed_counter - 1)]
                )
                b[1] = int(W_MEM[1][feed_counter - 1])
            if 2 <= feed_counter < 6:
                a[2] = int(
                    img_flat[_get_img_addr(tile_idx * 3 + 2, feed_counter - 2)]
                )
                b[2] = int(W_MEM[2][feed_counter - 2])
            core._cycle((a[0], a[1], a[2]), (b[0], b[1], b[2]))

        for _ in range(6):
            core._cycle((0, 0, 0), (0, 0, 0))

        C = core.read_c()
        for px in range(3):
            oy, ox = divmod(tile_idx * 3 + px, 3)
            for f in range(num_filters):
                out[oy, ox, f] = C[px, f]

    return out
