import db
import logger

def get_stock(warehouse_id: str, sku_id: str):
    """
    Path D — Dashboard read
    UI requests stock → Redis HGETALL (cache hit, <1ms)
    → on miss: Cassandra SELECT → repopulate Redis cache → return
    """
    r = db.get_redis_client()
    redis_key = f"stock:{warehouse_id}:{sku_id}"
    
    # 1. Try Redis cache first
    stock_data = r.hgetall(redis_key)
    
    if stock_data and 'qty' in stock_data:
        print(f"[Dashboard] Cache HIT for {sku_id}.")
        logger.log_event("DASHBOARD_READ", f"Cache HIT for {sku_id} from faster Redis.")
        return stock_data
        
    print(f"[Dashboard] Cache MISS for {sku_id}. Reading from Cassandra...")
    
    # 2. Cache miss -> Read from Cassandra
    session = db.get_cassandra_session()
    query = """
        SELECT product_name, quantity, reorder_threshold 
        FROM supply_chain.inventory_by_warehouse 
        WHERE warehouse_id = %s AND sku_id = %s
    """
    
    rows = session.execute(query, (warehouse_id, sku_id))
    rows_list = list(rows)
    
    if not rows_list:
        print(f"[Dashboard] Item {sku_id} not found in database.")
        return None
        
    row = rows_list[0]
    
    # 3. Repopulate Cache
    mapping = {
        "qty": row.quantity,
        "threshold": row.reorder_threshold,
        "product_name": row.product_name
    }
    r.hset(redis_key, mapping=mapping)
    r.expire(redis_key, 3600)  # TTL
    
    print(f"[Dashboard] Repopulated cache for {sku_id}.")
    logger.log_event("DASHBOARD_READ", f"Cache MISS for {sku_id}. Queried Cassandra directly and repopulated Redis.")
    
    # Return stringified values for consistency with redis HGETALL format
    return {k: str(v) for k, v in mapping.items()}

if __name__ == "__main__":
    print(get_stock("WH001", "SKU-100"))
