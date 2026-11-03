"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore


class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return self._price_request(state, customer_type, items, fulfillment)

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        priced = self._price_request(state, customer_type, items, fulfillment)
        order = {
            "order_id": "ORD-" + str(state["next_order_number"]).zfill(4),
            "status": "placed",
            **priced,
        }
        for line in order["items"]:
            _find_product(state["catalog"], line["product_id"])["stock"] -= line["quantity"]
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        return _find_order(self.store.load()["orders"], order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = _find_order(state["orders"], order_id)
        for line in order["items"]:
            product = _find_product(state["catalog"], line["product_id"])
            if product is not None:
                product["stock"] += line["quantity"]
        order["status"] = "cancelled"
        self.store.save(state)
        return order

    def _price_request(self, state, customer_type, items, fulfillment):
        """Validate a request and price it. Shared by quote() and place_order()
        so both always use the same rules. Does not change state."""
        _validate_options(customer_type, fulfillment, items)
        lines = [_price_line(state["catalog"], item) for item in items]
        subtotal = sum(line["line_total_cents"] for line in lines)
        discount = _discount_for(customer_type, subtotal)
        delivery = _delivery_for(fulfillment, subtotal - discount)
        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }


def _validate_options(customer_type, fulfillment, items):
    if customer_type not in ("regular", "student"):
        raise ValueError("Customer type must be regular or student.")
    if fulfillment not in ("pickup", "delivery"):
        raise ValueError("Fulfillment must be pickup or delivery.")
    if not isinstance(items, list) or not items:
        raise ValueError("An order must contain at least one item.")


def _price_line(catalog, item):
    """Check one requested item against the catalog and return its line."""
    if not isinstance(item, dict):
        raise ValueError("Each item must contain a product_id and quantity.")
    product = _find_product(catalog, item.get("product_id"))
    if product is None:
        raise ValueError("Unknown product.")
    quantity = item.get("quantity")
    if type(quantity) is not int or quantity < 1 or quantity > 99:
        raise ValueError("Quantity must be an integer from 1 to 99.")
    if quantity > product["stock"]:
        raise ValueError("Not enough stock for " + product["product_id"] + ".")
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "unit_price_cents": product["unit_price_cents"],
        "quantity": quantity,
        "line_total_cents": product["unit_price_cents"] * quantity,
    }


def _discount_for(customer_type, subtotal):
    if customer_type == "student" and subtotal > 5000:
        return (subtotal * 10 + 50) // 100
    return 0


def _delivery_for(fulfillment, discounted_subtotal):
    if fulfillment == "delivery" and discounted_subtotal < 10000:
        return 600
    return 0


def _find_product(catalog, product_id):
    for product in catalog:
        if product["product_id"] == product_id:
            return product
    return None


def _find_order(orders, order_id):
    for order in orders:
        if order["order_id"] == order_id:
            return order
    raise ValueError("Unknown order: " + order_id)
