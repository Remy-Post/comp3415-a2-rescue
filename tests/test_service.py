"""Service tests added for A2 (safety net before refactoring).

Tests are grouped by the four categories from the assignment:
normal, boundary, invalid/exceptional, and behaviour to preserve.
Amounts are in integer cents, same as the service.
"""

import json
from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


def item(product_id, quantity):
    return {"product_id": product_id, "quantity": quantity}


def stock_of(service, product_id):
    for product in service.catalog():
        if product["product_id"] == product_id:
            return product["stock"]
    raise AssertionError("product not in catalog: " + product_id)


class ServiceTestCase(unittest.TestCase):
    """Gives every test its own temporary save file."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def write_state(self, catalog, orders=None, next_order_number=1):
        """Write a custom save file so tests can use prices/stock the
        default catalog can't produce (e.g. 99 units or odd prices)."""
        state = {
            "schema_version": 1,
            "next_order_number": next_order_number,
            "catalog": catalog,
            "orders": orders or [],
        }
        self.path.write_text(json.dumps(state), encoding="utf-8")

    def saved_text(self):
        return self.path.read_text(encoding="utf-8")


class NormalBehaviourTests(ServiceTestCase):
    def test_regular_delivery_over_100_has_free_delivery(self):
        # Third example from FUNCTIONAL_SPEC.md
        quote = self.service.quote("regular", [item("hoodie", 3)], "delivery")
        self.assertEqual(quote["subtotal_cents"], 12000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 12000)

    def test_multi_item_quote_lists_each_line(self):
        quote = self.service.quote("regular", [item("notebook", 2), item("mug", 1)])
        self.assertEqual(
            quote["items"],
            [
                {"product_id": "notebook", "name": "Notebook", "unit_price_cents": 500,
                 "quantity": 2, "line_total_cents": 1000},
                {"product_id": "mug", "name": "Campus mug", "unit_price_cents": 1500,
                 "quantity": 1, "line_total_cents": 1500},
            ],
        )
        self.assertEqual(quote["total_cents"], 2500)

    def test_place_order_deducts_stock_and_saves(self):
        order = self.service.place_order("student", [item("pen-pack", 3)], "delivery")
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(order["total_cents"], 2250 + 600)
        reopened = OrderService(self.path)
        self.assertEqual(stock_of(reopened, "pen-pack"), 7)
        self.assertEqual(reopened.get_order("ORD-0001"), order)


class BoundaryTests(ServiceTestCase):
    def test_student_discount_applies_at_exactly_5000(self):
        # Spec: discount when subtotal is "at least 5,000 cents".
        quote = self.service.quote("student", [item("bag", 2)])
        self.assertEqual(quote["subtotal_cents"], 5000)
        self.assertEqual(quote["discount_cents"], 500)
        self.assertEqual(quote["total_cents"], 4500)

    def test_student_discount_not_applied_below_5000(self):
        quote = self.service.quote("student", [item("hoodie", 1), item("pen-pack", 1)])
        self.assertEqual(quote["subtotal_cents"], 4750)
        self.assertEqual(quote["discount_cents"], 0)

    def test_delivery_free_at_exactly_10000(self):
        quote = self.service.quote(
            "regular", [item("hoodie", 2), item("mug", 1), item("notebook", 1)], "delivery")
        self.assertEqual(quote["subtotal_cents"], 10000)
        self.assertEqual(quote["delivery_cents"], 0)

    def test_delivery_threshold_uses_amount_after_discount(self):
        # 11,000 - 1,100 discount = 9,900, which is under 10,000, so delivery is charged.
        quote = self.service.quote(
            "student", [item("hoodie", 2), item("bag", 1), item("notebook", 1)], "delivery")
        self.assertEqual(quote["subtotal_cents"], 11000)
        self.assertEqual(quote["discount_cents"], 1100)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 10500)

    def test_half_cent_discount_rounds_up(self):
        self.write_state([{"product_id": "kit", "name": "Kit",
                           "unit_price_cents": 5005, "stock": 3}])
        quote = self.service.quote("student", [item("kit", 1)])
        self.assertEqual(quote["discount_cents"], 501)  # 500.5 rounds up

    def test_ordering_all_remaining_stock_is_allowed(self):
        order = self.service.place_order("regular", [item("bag", 4)])
        self.assertEqual(order["items"][0]["quantity"], 4)
        self.assertEqual(stock_of(self.service, "bag"), 0)

    def test_one_more_than_stock_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [item("bag", 5)])

    def test_quantity_limits_1_and_99(self):
        # Default catalog never has 99 in stock, so use a custom one.
        self.write_state([{"product_id": "pen", "name": "Pen",
                           "unit_price_cents": 100, "stock": 500}])
        self.assertEqual(self.service.quote("regular", [item("pen", 1)])["total_cents"], 100)
        self.assertEqual(self.service.quote("regular", [item("pen", 99)])["total_cents"], 9900)
        for bad in (0, 100):
            with self.subTest(quantity=bad), self.assertRaises(ValueError):
                self.service.quote("regular", [item("pen", bad)])

    def test_empty_item_list_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [])
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [])
        self.assertFalse(self.path.exists())


class InvalidInputTests(ServiceTestCase):
    def test_invalid_customer_and_fulfillment(self):
        for args in (("member", [item("mug", 1)], "pickup"),
                     ("Regular", [item("mug", 1)], "pickup"),
                     ("regular", [item("mug", 1)], "shipping")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.service.quote(*args)

    def test_unknown_product(self):
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [item("laptop", 1)])
        self.assertFalse(self.path.exists())

    def test_non_integer_quantities_rejected(self):
        for bad in (True, 2.0, 1.5, "2", None):
            with self.subTest(quantity=bad), self.assertRaises(ValueError):
                self.service.quote("regular", [item("notebook", bad)])

    def test_rejected_order_does_not_change_saved_data(self):
        self.service.place_order("regular", [item("mug", 1)])
        before = self.saved_text()
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [item("mug", 1), item("bag", 50)])
        self.assertEqual(self.saved_text(), before)
        # next order number was not used up by the failed attempt
        self.assertEqual(self.service.place_order("regular", [item("mug", 1)])["order_id"],
                         "ORD-0002")

    def test_duplicate_lines_cannot_exceed_combined_stock(self):
        # Spec: combined quantity across lines must not exceed stock (hoodie stock is 5).
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [item("hoodie", 3), item("hoodie", 3)])
        self.assertEqual(stock_of(self.service, "hoodie"), 5)

    def test_unknown_order_lookup_and_cancel(self):
        self.service.place_order("regular", [item("mug", 1)])
        before = self.saved_text()
        with self.assertRaises(ValueError):
            self.service.get_order("ORD-9999")
        with self.assertRaises(ValueError):
            self.service.cancel_order("ORD-9999")
        self.assertEqual(self.saved_text(), before)

    def test_malformed_save_file_raises_instead_of_resetting(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.service.list_orders()
        self.assertEqual(self.saved_text(), "{ this is not json")


class PreservedBehaviourTests(ServiceTestCase):
    """Behaviour the refactoring of quote()/place_order() could break."""

    def test_quote_matches_placed_order(self):
        request = ("student", [item("hoodie", 1), item("mug", 1), item("hoodie", 1)], "delivery")
        quote = self.service.quote(*request)
        order = self.service.place_order(*request)
        for key in ("customer_type", "fulfillment", "items", "subtotal_cents",
                    "discount_cents", "delivery_cents", "total_cents"):
            self.assertEqual(order[key], quote[key], key)
        self.assertEqual(len(order["items"]), 3)  # duplicate lines stay separate

    def test_quote_does_not_create_or_change_save_file(self):
        self.service.quote("regular", [item("notebook", 2)])
        self.assertFalse(self.path.exists())
        self.service.place_order("regular", [item("notebook", 2)])
        before = self.saved_text()
        self.service.quote("student", [item("hoodie", 2)], "delivery")
        self.assertEqual(self.saved_text(), before)

    def test_order_ids_are_sequential_and_not_reused(self):
        first = self.service.place_order("regular", [item("mug", 1)])
        self.service.cancel_order(first["order_id"])
        second = self.service.place_order("regular", [item("mug", 1)])
        self.assertEqual([first["order_id"], second["order_id"]], ["ORD-0001", "ORD-0002"])
        history = self.service.list_orders()
        self.assertEqual([o["order_id"] for o in history], ["ORD-0001", "ORD-0002"])
        self.assertEqual([o["status"] for o in history], ["cancelled", "placed"])

    def test_cancel_keeps_original_totals(self):
        order = self.service.place_order("student", [item("hoodie", 2)], "delivery")
        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["total_cents"], 7800)
        self.assertEqual(cancelled["items"], order["items"])
        self.assertEqual(stock_of(self.service, "hoodie"), 5)

    def test_cancelling_twice_does_not_restore_stock_again(self):
        order = self.service.place_order("regular", [item("mug", 2)])
        self.service.cancel_order(order["order_id"])
        again = self.service.cancel_order(order["order_id"])
        self.assertEqual(again["status"], "cancelled")
        self.assertEqual(stock_of(self.service, "mug"), 8)

    def test_history_keeps_prices_from_when_order_was_placed(self):
        order = self.service.place_order("regular", [item("mug", 1)])
        state = json.loads(self.saved_text())
        state["catalog"][3]["unit_price_cents"] = 9999  # mug price changes later
        self.path.write_text(json.dumps(state), encoding="utf-8")
        reopened = OrderService(self.path)
        self.assertEqual(reopened.get_order(order["order_id"])["total_cents"], 1500)


if __name__ == "__main__":
    unittest.main()
