import time
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
import redis

# Redis connection
def get_redis_client():
    # In a real app, use environment variables. For this demo, hardcoded localhost.
    return redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Cassandra connection
def get_cassandra_session():
    cluster = Cluster(['127.0.0.1'], port=9042)
    # Retry mechanism since Cassandra takes time to start via Docker
    retries = 30
    delay = 5
    while retries > 0:
        try:
            session = cluster.connect()
            return session
        except Exception as e:
            print(f"Waiting for Cassandra to start... ({30 - retries + 1}/30)")
            time.sleep(delay)
            retries -= 1
    raise Exception("Could not connect to Cassandra")

def setup_database():
    session = get_cassandra_session()
    
    # Create keyspace
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS supply_chain
        WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};
    """)
    
    # Use keyspace
    session.set_keyspace('supply_chain')
    
    # Create inventory table (Query: Get all stock levels for warehouse WH001)
    session.execute("""
        CREATE TABLE IF NOT EXISTS inventory_by_warehouse (
            warehouse_id text,
            sku_id text,
            product_name text,
            quantity int,
            reorder_threshold int,
            last_updated timestamp,
            PRIMARY KEY ((warehouse_id), sku_id)
        );
    """)
    
    # Create orders table (Query: Get recent purchase orders for supplier SUP-03)
    # Need to store descending order
    session.execute("""
        CREATE TABLE IF NOT EXISTS orders_by_supplier (
            supplier_id text,
            order_date timestamp,
            order_id text,
            sku_id text,
            quantity_ordered int,
            status text,
            PRIMARY KEY ((supplier_id), order_date)
        ) WITH CLUSTERING ORDER BY (order_date DESC);
    """)
    
    # Create logs table (Query: Get all simulation logs chronologically for the demo)
    session.execute("""
        CREATE TABLE IF NOT EXISTS simulation_logs (
            session_id text,
            event_time timestamp,
            event_type text,
            message text,
            PRIMARY KEY ((session_id), event_time)
        ) WITH CLUSTERING ORDER BY (event_time ASC);
    """)
    
    print("Cassandra schema initialized.")

if __name__ == "__main__":
    setup_database()
    r = get_redis_client()
    if r.ping():
        print("Redis connected.")
