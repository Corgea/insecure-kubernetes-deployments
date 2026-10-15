"""Order store and status lifecycle for the orders service.

An order moves placed -> shipped -> delivered, and can be cancelled until it
ships. The web client (insecure-js/orders-client.js) places orders and polls
their status; the cat app's audit consumer reads status for its audit trail
and reports fulfilment events back through apply_status_event.

Orders are held in memory, so the service runs as a single replica until the
store moves to a database.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from models import OrderRequest, OrderStatusEvent

MAX_ORDERS = 10_000
MAX_HISTORY_ENTRIES = 50


class OrderNotFound(LookupError):
    pass


class OrderStoreFull(RuntimeError):
    pass


class InvalidTransition(ValueError):
    def __init__(self, current: str, requested: str):
        super().__init__(f"Cannot move order from '{current}' to '{requested}'")
        self.current = current
        self.requested = requested


@dataclass
class Order:
    id: str
    items: List[dict]
    currency: str
    status: str
    created_at: int
    updated_at: int
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    history: List[dict] = field(default_factory=list)


_orders: Dict[str, Order] = {}
_lock = threading.Lock()


def create_order(request: OrderRequest) -> Order:
    now = int(time.time())
    order = Order(
        id=uuid.uuid4().hex,
        items=[item.model_dump() for item in request.items],
        currency=request.currency,
        status="placed",
        created_at=now,
        updated_at=now,
    )
    with _lock:
        if len(_orders) >= MAX_ORDERS:
            raise OrderStoreFull()
        _orders[order.id] = order
    return order


def get_order(order_id: str) -> Order:
    with _lock:
        order = _orders.get(order_id)
    if order is None:
        raise OrderNotFound(order_id)
    return order


def order_status_payload(order: Order) -> dict:
    return {
        "order_id": order.id,
        "order_status": order.status,
        "updated_at": order.updated_at,
    }


def apply_status_event(order_id: str, event: OrderStatusEvent) -> Tuple[Order, bool]:
    """Apply a fulfilment event to an order.

    Returns the order and whether the event changed its status. Events the
    lifecycle does not model (scan types such as "packed") are recorded in the
    order history and leave the status as it is.
    """
    with _lock:
        order = _orders.get(order_id)
        if order is None:
            raise OrderNotFound(order_id)

        if event.status == "shipped":
            if order.status != "placed":
                raise InvalidTransition(order.status, "shipped")
            order.status = "shipped"
            order.carrier = event.carrier
            order.tracking_number = event.tracking_number
        elif event.status == "delivered":
            if order.status != "shipped":
                raise InvalidTransition(order.status, "delivered")
            order.status = "delivered"
        elif event.status == "cancelled":
            if order.status != "placed":
                raise InvalidTransition(order.status, "cancelled")
            order.status = "cancelled"
        else:
            _record(order, event, applied=False)
            return order, False

        order.updated_at = int(time.time())
        _record(order, event, applied=True)
        return order, True


def _record(order: Order, event: OrderStatusEvent, applied: bool) -> None:
    order.history.append(
        {
            "status": event.status,
            "source": event.source,
            "applied": applied,
            "at": int(time.time()),
        }
    )
    # Keep the newest entries; a chatty scanner should not grow an order forever.
    del order.history[:-MAX_HISTORY_ENTRIES]
