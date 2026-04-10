import time
import db
import inventory
import reorder
import orders
import dashboard
import logger

def run_simulation():
    print("=== Supply Chain Inventory Management Simulation ===\n")
    
    # 0. Start Orders Subscriber (Path C)
    print("Starting background order subscriber...")
    orders.start_subscriber_thread()
    time.sleep(1) # Give subscriber a moment to start
    
    warehouse_id = "WH-ALPHA"
    sku_id = "SKU-555"
    product_name = "Industrial Widget X"
    threshold = 50
    
    # Start with some stock
    print("\n--- Simulation Step 1: Initial Stock Load ---")
    inventory.update_stock(warehouse_id, sku_id, product_name, 200, threshold)
    
    # Let's perform a read
    print("\n--- Simulation Step 2: Dashboard Read (Path D) ---")
    dashboard.get_stock(warehouse_id, sku_id)
    
    print("\n--- Simulation Step 3: Stock decrements (Path A & B) ---")
    # Decrement by 100
    print("\n[Event] Shipment shipped: -100 units")
    inventory.update_stock(warehouse_id, sku_id, product_name, -100, threshold)
    reorder.check_and_queue_reorder(warehouse_id, sku_id)
    
    # Decrement by 80 - this brings stock to 20
    print("\n[Event] Shipment shipped: -80 units")
    inventory.update_stock(warehouse_id, sku_id, product_name, -80, threshold)
    reorder.check_and_queue_reorder(warehouse_id, sku_id)
    
    # Stock is now 20. 20/50 = 0.4. Need more drop to hit 0.2.
    print("\n[Event] Shipment shipped: -15 units")
    inventory.update_stock(warehouse_id, sku_id, product_name, -15, threshold)
    reorder.check_and_queue_reorder(warehouse_id, sku_id)
    
    # Stock is now 5. 5/50 = 0.1.
    # Alert should trigger! Purchase order in Path C should fire.
    
    sku_id2 = "SKU-999"
    product_name2 = "Commercial Gadget Y"
    threshold2 = 100
    
    print(f"\n--- Simulation Step 4: Second Product ({sku_id2}) ---")
    inventory.update_stock(warehouse_id, sku_id2, product_name2, 500, threshold2)
    
    print(f"\n[Event] Massive order for {sku_id2}: -490 units")
    inventory.update_stock(warehouse_id, sku_id2, product_name2, -490, threshold2)
    reorder.check_and_queue_reorder(warehouse_id, sku_id2)
    
    # Stock is now 10. 10/100 = 0.1. Alert triggers for SKU-999!
    
    # Wait for pub/sub to process
    time.sleep(2)
    
    print("\n--- Simulation Complete ---")
    
    print("\nChecking priority queue via Path B:")
    critical = reorder.get_critical_items(warehouse_id)
    print(f"Critical items in queue for {warehouse_id}: {critical}")
    
    print("\n=== Chronological Transaction Log ===")
    logs = logger.get_logs()
    # Cassandra timestamps are stored in UTC; format beautifully for presentation
    for row in logs:
        # Time string might have microseconds
        time_str = row.event_time.strftime('%H:%M:%S.%f')[:-3]
        print(f"[{time_str}] {row.event_type:<18} | {row.message}")

if __name__ == "__main__":
    db.setup_database()
    run_simulation()
