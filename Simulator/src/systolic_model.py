"""Cycle-accurate functional model of systolic_array_3x3 (matches pe.v wiring)."""

from __future__ import annotations

import numpy as np

from PE import PE, _i16


def _skew_inputs(t: int, A: np.ndarray, B: np.ndarray) -> tuple[list[int], list[int]]:
    """Diagonal skewing from tb_systolic_array.v / systolic_tiler.v."""
    a = [0, 0, 0]
    b = [0, 0, 0]
    if 0 <= t < 3:
        a[0] = int(A[0, t])
        b[0] = int(B[t, 0])
    if 1 <= t < 4:
        a[1] = int(A[1, t - 1])
        b[1] = int(B[t - 1, 1])
    if 2 <= t < 5:
        a[2] = int(A[2, t - 2])
        b[2] = int(B[t - 2, 2])
    return a, b


class SystolicArray3x3:
    """3×3 systolic array of PEs — behavior matches systolic_array.v."""

    def __init__(self) -> None:
        self.pes: list[list[PE]] = [[PE() for _ in range(3)] for _ in range(3)]

    def reset(self) -> None:
        for row in self.pes:
            for pe in row:
                pe.reset()

    def _cycle(
        self,
        a_ext: tuple[int, int, int],
        b_ext: tuple[int, int, int],
        *,
        core_rst: bool = False,
    ) -> None:
        if core_rst:
            self.reset()
            return

        a_in = [[0] * 3 for _ in range(3)]
        b_in = [[0] * 3 for _ in range(3)]
        for i in range(3):
            a_in[i][0] = a_ext[i]
        for j in range(3):
            b_in[0][j] = b_ext[j]
        for i in range(3):
            for j in range(1, 3):
                a_in[i][j] = self.pes[i][j - 1].a_reg
        for j in range(3):
            for i in range(1, 3):
                b_in[i][j] = self.pes[i - 1][j].b_reg

        for i in range(3):
            for j in range(3):
                self.pes[i][j].step(a_in[i][j], b_in[i][j])

    def read_c(self) -> np.ndarray:
        C = np.zeros((3, 3), dtype=np.int16)
        for i in range(3):
            for j in range(3):
                C[i, j] = np.int16(self.pes[i][j].acc)
        return C

    def multiply(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """
        Matrix multiply C = A @ B with diagonal skew (10 feed + 10 drain cycles).
        A, B: 3×3 int8; returns 3×3 int16 (bit-identical to RTL).
        """
        A = np.asarray(A, dtype=np.int8).reshape(3, 3)
        B = np.asarray(B, dtype=np.int8).reshape(3, 3)

        self.reset()
        self._cycle((0, 0, 0), (0, 0, 0), core_rst=True)
        self._cycle((0, 0, 0), (0, 0, 0), core_rst=False)

        for t in range(10):
            a, b = _skew_inputs(t, A, B)
            self._cycle((a[0], a[1], a[2]), (b[0], b[1], b[2]))

        for _ in range(10):
            self._cycle((0, 0, 0), (0, 0, 0))

        return self.read_c()

    def multiply_tile_accumulate(
        self,
        A_tile: np.ndarray,
        B_tile: np.ndarray,
        *,
        reset_core: bool,
    ) -> None:
        """One 3×3 tile MAC; optionally pulse core reset (k_blk == 0 in tiler)."""
        A_tile = np.asarray(A_tile, dtype=np.int8).reshape(3, 3)
        B_tile = np.asarray(B_tile, dtype=np.int8).reshape(3, 3)

        if reset_core:
            self.reset()
            self._cycle((0, 0, 0), (0, 0, 0), core_rst=True)
            self._cycle((0, 0, 0), (0, 0, 0), core_rst=False)

        for t in range(10):
            a, b = _skew_inputs(t, A_tile, B_tile)
            self._cycle((a[0], a[1], a[2]), (b[0], b[1], b[2]))

        for _ in range(7):
            self._cycle((0, 0, 0), (0, 0, 0))

    @staticmethod
    def multiply_6x6_tiled(A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """6×6 GEMM via 2×2 tiling and 2 K-blocks (matches systolic_tiler_6x6)."""
        A = np.asarray(A, dtype=np.int8).reshape(6, 6)
        B = np.asarray(B, dtype=np.int8).reshape(6, 6)
        C = np.zeros((6, 6), dtype=np.int16)
        core = SystolicArray3x3()

        for row_blk in range(2):
            for col_blk in range(2):
                for k_blk in range(2):
                    A_tile = A[row_blk * 3 : row_blk * 3 + 3, k_blk * 3 : k_blk * 3 + 3]
                    B_tile = B[k_blk * 3 : k_blk * 3 + 3, col_blk * 3 : col_blk * 3 + 3]
                    core.multiply_tile_accumulate(
                        A_tile, B_tile, reset_core=(k_blk == 0)
                    )
                block = core.read_c()
                C[
                    row_blk * 3 : row_blk * 3 + 3,
                    col_blk * 3 : col_blk * 3 + 3,
                ] = block
        return C


def ref_matmul_int16(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Reference C[i,j] = sum_k int16(A[i,k]*B[k,j]) — matches PE accumulator width."""
    A = np.asarray(A, dtype=np.int8)
    B = np.asarray(B, dtype=np.int8)
    n, m, kdim = A.shape[0], B.shape[1], A.shape[1]
    C = np.zeros((n, m), dtype=np.int16)
    for i in range(n):
        for j in range(m):
            acc = 0
            for k in range(kdim):
                prod = int(np.int8(A[i, k])) * int(np.int8(B[k, j]))
                acc = _i16(acc + prod)
            C[i, j] = np.int16(acc)
    return C
