from dataclasses import dataclass
from typing import Tuple

import numpy as np


def _i16(value: int) -> int:
    """Wrap to signed 16-bit (matches RTL c_result width)."""
    v = int(value) % 65536
    if v >= 32768:
        v -= 65536
    return v


@dataclass
class PE:
    a_reg: int = 0
    b_reg: int = 0
    acc: int = 0
    acc_width: int = 16  # match RTL: 16-bit accumulator
    frac_bits: int = 0  # integer mode to match RTL

    def step(self, a_in: int, b_in: int) -> Tuple[int, int]:
        """Forward inputs, accumulate MAC, return registered (a_out, b_out)."""
        a_in = int(np.int8(a_in))
        b_in = int(np.int8(b_in))
        self.acc = _i16(self.acc + a_in * b_in)
        self.a_reg = a_in
        self.b_reg = b_in
        return self.a_reg, self.b_reg

    def reset(self) -> None:
        """Zero all registers (matches active-high rst in RTL)."""
        self.a_reg = 0
        self.b_reg = 0
        self.acc = 0
