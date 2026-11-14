#!/usr/bin/env python3
"""Tests for calculator.py."""

import math
import unittest

from calculator import CalcError, evaluate, format_result


class TestArithmetic(unittest.TestCase):
    def test_basic_operators(self):
        self.assertEqual(evaluate("2 + 3"), 5)
        self.assertEqual(evaluate("10 - 4"), 6)
        self.assertEqual(evaluate("6 * 7"), 42)
        self.assertEqual(evaluate("20 / 4"), 5)
        self.assertEqual(evaluate("7 // 2"), 3)
        self.assertEqual(evaluate("7 % 2"), 1)
        self.assertEqual(evaluate("2 ** 10"), 1024)

    def test_precedence_and_associativity(self):
        self.assertEqual(evaluate("2 + 3 * 4"), 14)
        self.assertEqual(evaluate("(2 + 3) * 4"), 20)
        self.assertEqual(evaluate("2 ** 3 ** 2"), 512)  # right-associative
        self.assertEqual(evaluate("10 - 3 - 2"), 5)     # left-associative

    def test_unary(self):
        self.assertEqual(evaluate("-5"), -5)
        self.assertEqual(evaluate("+5"), 5)
        self.assertEqual(evaluate("-(2 + 3)"), -5)
        self.assertEqual(evaluate("-2 ** 2"), -4)

    def test_caret_is_power(self):
        self.assertEqual(evaluate("2 ^ 10"), 1024)

    def test_float_results(self):
        self.assertAlmostEqual(evaluate("1 / 3"), 0.3333333333333333)
        self.assertAlmostEqual(evaluate("sqrt(2)"), math.sqrt(2))

    def test_constants(self):
        self.assertEqual(evaluate("pi"), math.pi)
        self.assertEqual(evaluate("tau"), math.tau)
        self.assertAlmostEqual(evaluate("e"), math.e)

    def test_functions(self):
        self.assertEqual(evaluate("sqrt(16)"), 4)
        self.assertEqual(evaluate("abs(-9)"), 9)
        self.assertEqual(evaluate("floor(3.7)"), 3)
        self.assertEqual(evaluate("ceil(3.2)"), 4)
        self.assertAlmostEqual(evaluate("log(e)"), 1.0)
        self.assertAlmostEqual(evaluate("sin(0)"), 0.0)
        self.assertAlmostEqual(evaluate("degrees(pi)"), 180.0)
        self.assertEqual(evaluate("round(2.5)"), 2)  # banker's rounding


class TestFormatting(unittest.TestCase):
    def test_whole_floats_drop_the_decimal(self):
        self.assertEqual(format_result(5.0), "5")
        self.assertEqual(format_result(-0.0), "0")

    def test_fractions_keep_precision(self):
        self.assertEqual(format_result(1.5), "1.5")

    def test_ints_pass_through(self):
        self.assertEqual(format_result(1024), "1024")


class TestErrors(unittest.TestCase):
    def assert_error(self, expression):
        with self.assertRaises(CalcError):
            evaluate(expression)

    def test_empty(self):
        self.assert_error("")
        self.assert_error("   ")

    def test_division_by_zero(self):
        self.assert_error("1 / 0")
        self.assert_error("1 // 0")
        self.assert_error("1 % 0")

    def test_syntax_errors(self):
        self.assert_error("2 +")
        self.assert_error("(2 + 3")
        self.assert_error("2 3")

    def test_unknown_names(self):
        self.assert_error("foo")
        self.assert_error("os.system('true')")

    def test_no_attribute_access(self):
        self.assert_error("().__class__")

    def test_no_keyword_arguments(self):
        self.assert_error("log(10, base=10)")

    def test_unknown_function(self):
        self.assert_error("eval('1+1')")

    def test_domain_error(self):
        self.assert_error("sqrt(-1)")

    def test_overflow(self):
        self.assert_error("2 ** 2000000")     # 2M bits, over the 1M limit
        self.assert_error("10 ** 10 ** 10")   # would be a 10-billion-digit int

    def test_large_result_within_limit(self):
        value = evaluate("2 ** 100000")
        self.assertIsInstance(value, int)
        self.assertEqual(value.bit_length(), 100001)
        self.assertEqual(len(format_result(value)), 30103)


if __name__ == "__main__":
    unittest.main()
