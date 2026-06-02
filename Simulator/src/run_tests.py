#!/usr/bin/env python3
"""Run simulator validation suite (4 tests). Exit 0 only if all pass."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from PE import PE
from im2col import conv_via_gemm
from systolic_model import SystolicArray3x3, ref_matmul_int16


def test_pe() -> bool:
    pe = PE()
    pe.reset()
    a_out, b_out = pe.step(2, 3)
    if pe.acc != 6 or a_out != 2 or b_out != 3:
        return False
    a_out, b_out = pe.step(4, 5)
    if pe.acc != 26 or a_out != 4 or b_out != 5:
        return False
    a_out, b_out = pe.step(1, 1)
    if a_out != 1 or b_out != 1:
        return False
    return True


def test_systolic_3x3() -> bool:
    A = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=np.int8)
    I = np.eye(3, dtype=np.int8)
    arr = SystolicArray3x3()
    C = arr.multiply(A, I)
    if not np.array_equal(C, A.astype(np.int16)):
        return False

    rng = np.random.default_rng(42)
    for _ in range(20):
        A = rng.integers(-128, 128, size=(3, 3), dtype=np.int8)
        B = rng.integers(-128, 128, size=(3, 3), dtype=np.int8)
        C = SystolicArray3x3().multiply(A, B)
        gold = ref_matmul_int16(A, B)
        if not np.array_equal(C, gold):
            return False
    return True


def test_tiling_6x6() -> bool:
    rng = np.random.default_rng(7)
    A = rng.integers(-128, 128, size=(6, 6), dtype=np.int8)
    B = rng.integers(-128, 128, size=(6, 6), dtype=np.int8)
    C = SystolicArray3x3.multiply_6x6_tiled(A, B)
    gold = ref_matmul_int16(A, B)
    return np.array_equal(C, gold)


def test_convolution() -> bool:
    image = np.arange(16, dtype=np.int8).reshape(4, 4)
    f0 = np.ones((2, 2), dtype=np.int8)
    f1 = np.array([[2, 0], [0, 0]], dtype=np.int8)
    f2 = np.array([[0, 0], [0, 3]], dtype=np.int8)
    out = conv_via_gemm(image, [f0, f1, f2])

    if not np.array_equal(out[0, :, 0], [10, 14, 18]):
        return False
    if not np.array_equal(out[0, :, 1], [0, 2, 4]):
        return False
    if not np.array_equal(out[0, :, 2], [15, 18, 21]):
        return False

    for i in range(3):
        for j in range(3):
            win = image[i : i + 2, j : j + 2]
            exp0 = int(win.sum())
            exp1 = int(win[0, 0]) * 2
            exp2 = int(win[1, 1]) * 3
            if out[i, j, 0] != exp0 or out[i, j, 1] != exp1 or out[i, j, 2] != exp2:
                return False
    return True


def main() -> int:
    tests = [
        ("PE Model", test_pe),
        ("Systolic 3x3", test_systolic_3x3),
        ("Tiling 6x6", test_tiling_6x6),
        ("Convolution", test_convolution),
    ]
    all_ok = True
    for idx, (name, fn) in enumerate(tests, start=1):
        ok = fn()
        all_ok = all_ok and ok
        status = "PASS" if ok else "FAIL"
        print(f"[{idx}/4] {name:<18} : {status}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
