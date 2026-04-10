import json
import db
import logger

def check_and_queue_reorder(warehouse_id: str, sku_id: str):
    """
    Path B — Reorder check
    After every update → read Redis qty → compute score = qty/threshold
    → ZADD reorder_queue → if score < 0.2 → PUBLISH reorder_alerts
    """
    r = db.get_redis_client()
    redis_key = f"stock:{warehouse_id}:{sku_id}"
    
    # Get details
    stock_data = r.hgetall(redis_key)
    if not stock_data:
        print(f"[Reorder] No data found for {sku_id}")
        return
        
    qty = int(stock_data.get("qty", 0))
    threshold = int(stock_data.get("threshold", 1))
    
    # Compute score (lower = more urgent)
    score = qty / threshold if threshold > 0 else 0
    
    # ZADD reorder_queue
    queue_key = f"reorder_queue:{warehouse_id}"
    r.zadd(queue_key, {sku_id: score})
    print(f"[Reorder] Added {sku_id} to {queue_key} with score {score:.2f}")
    logger.log_event("REORDER_QUEUE", f"Updated {sku_id} in reorder priority queue to score {score:.2f}.")
    
    # If score < 0.2, publish alert
    if score < 0.2:
        alert_payload = {
            "warehouse_id": warehouse_id,
            "sku_id": sku_id,
            "product_name": stock_data.get("product_name"),
            "current_qty": qty,
            "threshold": threshold,
            "score": score
        }
        r.publish("reorder_alerts", json.dumps(alert_payload))
        print(f"[Reorder] 🚨 Published ALERT for {sku_id}! Score: {score:.2f} < 0.2")
        logger.log_event("ALERT_PUBLISHED", f"Published low stock alert for {sku_id}! Score {score:.2f} dropped below 0.2 threshold.")

def get_critical_items(warehouse_id: str):
    """
    Demonstrates O(log N) priority-based reorder scanning using ZRANGEBYSCORE.
    """
    r = db.get_redis_client()
    queue_key = f"reorder_queue:{warehouse_id}"
    critical_items = r.zrangebyscore(queue_key, 0, 0.2)
    return critical_items

if __name__ == "__main__":
    check_and_queue_reorder("WH001", "SKU-999")
