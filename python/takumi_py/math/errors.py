"""Exceptions raised by the optional math rendering layer."""

from __future__ import annotations

from takumi_py.exceptions import TakumiError

__all__ = [
    "MathBatchError",
    "MathError",
    "MathLimitError",
    "MathRuntimeError",
    "MathRuntimeUnavailableError",
    "MathSyntaxError",
    "MathValidationError",
]


class MathError(TakumiError):
    """Base class for errors raised by :mod:`takumi_py.math`."""


class MathRuntimeUnavailableError(MathError):
    """The optional JavaScript runtime or packaged MathJax asset is unavailable."""


class MathSyntaxError(MathError):
    """TeX input was rejected by MathJax."""


class MathLimitError(MathError):
    """A configured execution, memory, input, or output limit was exceeded."""


class MathRuntimeError(MathError):
    """The embedded runtime failed while converting a formula."""


class MathValidationError(MathError, ValueError):
    """A math option or generated SVG failed strict validation."""


class MathBatchError(MathError):
    """One expression in a batch failed.

    Attributes:
        index: Zero-based position of the failing expression.
    """

    def __init__(self, index: int, cause: MathError) -> None:
        super().__init__(f"math expression at index {index} failed: {cause}")
        self.index = index
        self.__cause__ = cause
