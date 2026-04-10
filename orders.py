import json
import uuid
import datetime
import db
import threading
import logger

def _insert_purchase_order(alert_data):
    """Inserts a new purchase order into Cassandra based on the alert payload."""
    session = db.get_cassandra_session()
    
    supplier_id = "SUP-03"  # Simplified: assume a single generic supplier for demo
    order_id = str(uuid.uuid4())
    sku_id = alert_data['sku_id']
    
    # Suppose we always order 100 units to replenish
    qty_ordered = 100 
    now = datetime.datetime.now()
    
    query = """
        INSERT INTO supply_chain.orders_by_supplier
        (supplier_id, order_date, order_id, sku_id, quantity_ordered, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    # Requires synchronous execution to ensure absolute durability for the purchase order
    session.execute(query, (supplier_id, now, order_id, sku_id, qty_ordered, 'PENDING'))
    print(f"[Orders] Generated Purchase Order {order_id} for {sku_id} to {supplier_id}.")
    logger.log_event("PURCHASE_ORDER", f"Auto-generated PO {order_id} for {qty_ordered} units of {sku_id} from {supplier_id}.")

def listen_for_alerts():
    """
    Path C — Auto purchase order
    Order service SUBSCRIBES to reorder_alerts → receives JSON payload
    → INSERT into orders_by_supplier (Cassandra) → notify supplier
    """
    r = db.get_redis_client()
    pubsub = r.pubsub()
    pubsub.subscribe("reorder_alerts")
    print("[Orders] Listening for reorder alerts...")
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            print(f"[Orders] Received alert! Low stock for {data['sku_id']} ({data['current_qty']}/{data['threshold']})")
            _insert_purchase_order(data)

def start_subscriber_thread():
    """Helper to start the subscriber loop in the background for demo purposes."""
    t = threading.Thread(target=listen_for_alerts, daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    listen_for_alerts()
