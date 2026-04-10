from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import time
import uuid
import random

import db
import inventory
import reorder
import orders
import logger

simulation_state = {"status": "idle", "summary": {}}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the visualizer at root
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
def startup_event():
    db.setup_database()
    orders.start_subscriber_thread()
    time.sleep(1)

def decode_redis(item):
    if isinstance(item, bytes):
        return item.decode('utf-8')
    return item

class ItemModel(BaseModel):
    name: str
    quantity: int

@app.post("/api/item")
def add_item(item: ItemModel):
    sku = f"SKU-{str(uuid.uuid4())[:6].upper()}"
    threshold = int(item.quantity * 0.2)
    warehouse_id = "WH-ALPHA"
    inventory.update_stock(warehouse_id, sku, item.name, item.quantity, threshold)
    return {"status": "added", "sku": sku}

@app.delete("/api/item/{name}")
def delete_item(name: str):
    # 1. Delete from Redis
    r = db.get_redis_client()
    keys = r.keys("stock:*")
    for k in keys:
        try:
            data = r.hgetall(k)
            item_name = decode_redis(data.get(b"product_name", data.get("product_name", b"")))
            if item_name == name:
                r.delete(k)
                sku = decode_redis(k).split(":")[-1]
                r.zrem("reorder_queue:WH-ALPHA", sku)
        except Exception as e:
            pass

    # 2. Delete from Cassandra database
    try:
        session = db.get_cassandra_session()
        session.set_keyspace('supply_chain')
        rows = session.execute("SELECT warehouse_id, sku_id, product_name FROM inventory_by_warehouse")
        for row in rows:
            if row.product_name == name:
                session.execute(
                    "DELETE FROM inventory_by_warehouse WHERE warehouse_id=%s AND sku_id=%s",
                    (row.warehouse_id, row.sku_id)
                )
    except Exception as e:
        print("Error deleting from Cassandra:", e)

    return {"status": "deleted"}

@app.get("/api/database")
def get_database():
    session = db.get_cassandra_session()
    session.set_keyspace('supply_chain')
    
    inv_rows = session.execute("SELECT * FROM inventory_by_warehouse")
    inv_data = [{"warehouse_id": r.warehouse_id, "sku_id": r.sku_id, "product_name": r.product_name, "quantity": r.quantity, "reorder_threshold": r.reorder_threshold} for r in inv_rows]
    
    ord_rows = session.execute("SELECT * FROM orders_by_supplier")
    ord_data = [{"supplier_id": r.supplier_id, "order_date": str(r.order_date), "order_id": r.order_id, "sku_id": r.sku_id, "quantity_ordered": r.quantity_ordered, "status": r.status} for r in ord_rows]
    
    log_rows = session.execute("SELECT session_id, event_time, event_type, message FROM simulation_logs")
    log_data = [{"session_id": r.session_id, "event_time": str(r.event_time), "event_type": r.event_type, "message": r.message} for r in log_rows]
    
    return {
        "inventory": inv_data,
        "orders": ord_data,
        "logs": log_data
    }

@app.get("/api/state")
def get_state():
    r = db.get_redis_client()
    
    # 1. Get Inventory
    keys = r.keys("stock:*")
    stock_list = []
    for k in keys:
        try:
            data = r.hgetall(k)
            parsed_data = {
                "id": decode_redis(k),
                "qty": int(decode_redis(data.get(b"qty", data.get("qty", 0)))),
                "threshold": int(decode_redis(data.get(b"threshold", data.get("threshold", 0)))),
                "product_name": decode_redis(data.get(b"product_name", data.get("product_name", "")))
            }
            stock_list.append(parsed_data)
        except Exception as e:
            print("Error parsing stock", e)
        
    # 2. Get Queue
    queue = r.zrange("reorder_queue:WH-ALPHA", 0, -1, withscores=True)
    queue_list = [{"sku": decode_redis(q[0]), "score": q[1]} for q in queue]
    
    # 3. Get Logs
    try:
        logs_raw = logger.get_logs()
        logs_list = []
        for row in logs_raw:
            logs_list.append({
                "time": row.event_time.strftime('%H:%M:%S.%f')[:-3],
                "type": row.event_type,
                "message": row.message
            })
        # Sort logs chronologically because Cassandra select returned arbitrary order unless clustering key is used
        logs_list.sort(key=lambda x: x["time"])
    except Exception as e:
        print("Error getting logs", e)
        logs_list = []
        
    global simulation_state
    return {
        "inventory": stock_list,
        "queue": queue_list,
        "logs": logs_list,
        "simulation_status": simulation_state["status"],
        "simulation_summary": simulation_state.get("summary", {})
    }

async def simulate_delivery(warehouse_id, sku, product_name, reorder_qty, threshold):
    await asyncio.sleep(3) # Simulate supplier delay
    inventory.update_stock(warehouse_id, sku, product_name, reorder_qty, threshold)
    logger.log_event("ORDER_DELIVERED", f"Delivered {reorder_qty} units of {sku}")
    r = db.get_redis_client()
    r.zrem(f"reorder_queue:{warehouse_id}", sku)
    
    global simulation_state
    if "summary" in simulation_state and sku in simulation_state["summary"]:
        simulation_state["summary"][sku]["events"].append(f"✅ Delivered {reorder_qty} units.")

async def run_simulation_task():
    global simulation_state
    simulation_state["status"] = "running"
    simulation_state["summary"] = {}
    logger.log_event("SIM_START", "=== Simulation Started ===")
    
    warehouse_id = "WH-ALPHA"
    r = db.get_redis_client()
    
    # Load tracking data based on current dynamic values
    keys = r.keys("stock:*")
    for k in keys:
        try:
            data = r.hgetall(k)
            sku = decode_redis(k).split(":")[-1]
            qty = int(decode_redis(data.get(b"qty", data.get("qty", b"0"))))
            product_name = decode_redis(data.get(b"product_name", data.get("product_name", b"")))
            
            simulation_state["summary"][sku] = {
                "name": product_name,
                "initial": qty,
                "events": [],
                "final": qty
            }
        except Exception as e:
            pass
            
    await asyncio.sleep(1) # wait for updates to register
    
    reordered_skus = set()
    
    for _ in range(5): # Run 5 dynamic simulation steps
        keys = r.keys("stock:*")
        for k in keys:
            data = r.hgetall(k)
            sku = decode_redis(k).split(":")[-1]
            qty_bytes = data.get(b"qty", data.get("qty", b"0"))
            qty = int(decode_redis(qty_bytes))
            
            if sku in simulation_state["summary"]:
                drop = random.randint(5, max(15, int(qty/3))) if qty > 0 else 0
                product_name = decode_redis(data.get(b"product_name", data.get("product_name", b"")))
                threshold = int(decode_redis(data.get(b"threshold", data.get("threshold", b"20"))))
                
                new_qty = qty - drop
                
                if drop > 0:
                    inventory.update_stock(warehouse_id, sku, product_name, -drop, threshold)
                    simulation_state["summary"][sku]["events"].append(f"Shipped {drop} units. (Stock: {new_qty})")
                
                reorder.check_and_queue_reorder(warehouse_id, sku)
                
                if new_qty <= threshold and sku not in reordered_skus:
                    reordered_skus.add(sku)
                    simulation_state["summary"][sku]["events"].append(f"**ALERT TRIGGERED**: Stock dropped to {new_qty}. Reordering {threshold * 4} units...")
                    asyncio.create_task(simulate_delivery(warehouse_id, sku, product_name, threshold * 4, threshold))
                
        await asyncio.sleep(2)
        
    await asyncio.sleep(5)  # Wait for pending deliveries
    
    # Finalize summary calculations with exact final stock
    final_keys = r.keys("stock:*")
    for k in final_keys:
        try:
            data = r.hgetall(k)
            sku = decode_redis(k).split(":")[-1]
            qty_bytes = data.get(b"qty", data.get("qty", b"0"))
            qty = int(decode_redis(qty_bytes))
            if sku in simulation_state["summary"]:
                simulation_state["summary"][sku]["final"] = qty
        except Exception as e:
            pass
            
    logger.log_event("SIM_END", "=== Simulation Ended ===")
    simulation_state["status"] = "ended"

@app.post("/api/simulation/start")
def start_simulation(background_tasks: BackgroundTasks):
    global simulation_state
    if simulation_state["status"] == "running":
        return {"status": "already_running"}
    simulation_state["status"] = "running"
    background_tasks.add_task(run_simulation_task)
    return {"status": "started"}

@app.post("/api/simulation/reset")
def reset_simulation():
    global simulation_state
    simulation_state["status"] = "idle"
    return {"status": "reset"}

@app.post("/api/simulation/reset")
def reset_simulation():
    global simulation_state
    simulation_state["status"] = "idle"
    return {"status": "reset"}
