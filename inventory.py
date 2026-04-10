import datetime
import db
import logger

def update_stock(warehouse_id: str, sku_id: str, product_name: str, qty_change: int, threshold: int):
    """
    Path A — Stock update
    Shipment event → Inventory service → Redis HINCRBY (instant) → Cassandra UPDATE (async)
    """
    r = db.get_redis_client()
    session = db.get_cassandra_session()
    
    # 1. Update Redis (Instant)
    redis_key = f"stock:{warehouse_id}:{sku_id}"
    new_qty = r.hincrby(redis_key, "qty", qty_change)
    
    # Set static fields in hash if not present or to ensure they are up to date
    r.hset(redis_key, mapping={
        "threshold": threshold,
        "product_name": product_name
    })
    
    # TTL auto-expires stale cache
    r.expire(redis_key, 3600)
    
    print(f"[Inventory] Updated {sku_id} in Redis. New qty: {new_qty}")
    
    # 2. Update Cassandra (Async)
    # Using execute_async so this doesn't block the instant Redis response conceptually
    query = """
        INSERT INTO supply_chain.inventory_by_warehouse 
        (warehouse_id, sku_id, product_name, quantity, reorder_threshold, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    # Note: Cassandra's UPDATE and INSERT are functionally the same (upserts).
    
    now = datetime.datetime.now()
    session.execute_async(query, (warehouse_id, sku_id, product_name, int(new_qty), threshold, now))
    
    print(f"[Inventory] Cassandra update dispatched async for {sku_id}.")
    logger.log_event("STOCK_UPDATE", f"Decremented/Updated {sku_id} by {qty_change}. New total: {new_qty}")
    
    return int(new_qty)

if __name__ == "__main__":
    # Test
    update_stock("WH001", "SKU-999", "Test Widget", 50, 10)
