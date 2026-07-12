"""Tests for the tools module."""

from scenaraist.tools import add, multiply


def test_multiply_positive() -> None:
    assert multiply.invoke({"a": 3, "b": 4}) == 12


def test_multiply_zero() -> None:
    assert multiply.invoke({"a": 0, "b": 5}) == 0


def test_multiply_negative() -> None:
    assert multiply.invoke({"a": -2, "b": 6}) == -12


def test_multiply_both_negative() -> None:
    assert multiply.invoke({"a": -3, "b": -4}) == 12


def test_add_positive() -> None:
    assert add.invoke({"a": 3, "b": 4}) == 7


def test_add_zero() -> None:
    assert add.invoke({"a": 0, "b": 5}) == 5


def test_add_negative() -> None:
    assert add.invoke({"a": -2, "b": 6}) == 4


def test_add_both_negative() -> None:
    assert add.invoke({"a": -3, "b": -4}) == -7
