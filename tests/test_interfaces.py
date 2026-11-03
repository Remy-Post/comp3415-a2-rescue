"""Tests for the menu and the individual commands (cli.py).

These use the real OrderService with a temporary save file. input() and
stdout/stderr are patched because menu.py talks to the terminal directly.
"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from supplydesk import cli
from supplydesk.menu import money, run_menu
from supplydesk.service import OrderService


class InterfaceTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = cli.main(["--data", str(self.path), *args])
        return status, out.getvalue(), err.getvalue()

    def run_menu_with(self, answers):
        out = io.StringIO()
        with mock.patch("builtins.input", side_effect=answers), contextlib.redirect_stdout(out):
            status = run_menu(OrderService(self.path))
        return status, out.getvalue()


class CliTests(InterfaceTestCase):
    def test_quote_command_prints_json_in_cents(self):
        status, out, _ = self.run_cli("quote", "--customer", "regular", "--item", "notebook:2")
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(out)["total_cents"], 1000)

    def test_rejected_command_exits_with_status_2(self):
        status, out, err = self.run_cli("place", "--item", "notebook:500")
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertIn("Error", err)
        self.assertFalse(self.path.exists())


class MenuTests(InterfaceTestCase):
    def test_money_formats_cents_as_dollars(self):
        self.assertEqual(money(1000), "$10.00")
        self.assertEqual(money(5), "$0.05")

    def test_declining_confirmation_does_not_place_order(self):
        # option 3, defaults, one notebook, finish, default pickup, answer "n", exit
        status, out = self.run_menu_with(["3", "", "notebook", "2", "", "", "n", "0"])
        self.assertEqual(status, 0)
        self.assertIn("Order not placed.", out)
        self.assertFalse(self.path.exists())

    def test_confirmed_order_is_saved(self):
        self.run_menu_with(["3", "student", "hoodie", "2", "", "delivery", "y", "0"])
        order = OrderService(self.path).get_order("ORD-0001")
        self.assertEqual(order["total_cents"], 7800)

    def test_bad_quantity_text_asks_again(self):
        _, out = self.run_menu_with(["2", "", "mug", "two", "mug", "1", "", "", "0"])
        self.assertIn("Re-enter this item", out)
        self.assertIn("Total: $15.00", out)

    def test_end_of_input_exits_cleanly(self):
        status, out = self.run_menu_with(EOFError)  # same as Ctrl+D / piped input ending
        self.assertEqual(status, 0)
        self.assertIn("Goodbye.", out)


if __name__ == "__main__":
    unittest.main()
