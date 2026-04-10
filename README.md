# Supply Chain Inventory Management System

A comprehensive supply chain and inventory management simulation built with Python, FastApi, Apache Cassandra, and Redis. This system demonstrates real-time inventory tracking, automatic reordering when stock drops below thresholds, and real-time event logging.

## Features

- **Real-Time Inventory Tracking**: View current stock levels for products across warehouses.
- **Automated Reordering System**: Automatically triggers purchase orders when stock volume drops below a specific threshold (e.g., 20%).
- **Dashboard & Simulation UI**: A web interface built with FastAPI, HTML, CSS, and JS to visualize inventory adjustments, critical queues, and detailed simulation logs.
- **Distributed Database Architecture**: Uses **Apache Cassandra** for persistent storage (inventory, order history, and logs) and **Redis** for in-memory caching and real-time processing (priority queuing).
- **Docker Integration**: Uses Docker Compose to effortlessly spin up the Cassandra database and Redis cache dependencies.

## Architecture

1. **Database (Cassandra)**
   - `inventory_by_warehouse`: Stores the current state of products for a warehouse.
   - `orders_by_supplier`: Keeps a persistent record of all purchase orders.
   - `simulation_logs`: Tracks all background and user-driven events for auditing.
2. **Cache / PubSub (Redis)**
   - Acts as a high-performance priority queue for reorder alerts.
   - Real-time cache for rapid dashboard queries.
3. **Backend API (FastAPI)**
   - Exposes REST endpoints to query state, start simulated order processing, and manipulate inventory items.
4. **Interactive Dashboard UI**
   - Available via the `/static/` path on the API server. Provides a visual presentation of backend states.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) or Docker Compose installed.
- Python 3.8+

## Installation & Setup

1. **Start the Infrastructure**
   ```bash
   docker-compose up -d
   ```
   Wait a moment for both Cassandra and Redis containers to spin up and report healthy.
   
2. **Setup a Python Virtual Environment (Optional but Recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or venv\Scripts\activate on Windows
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Running the Project

You can run the simulation logic directly or spin up the API to use the Dashboard UI.

### Option 1: Run the Visual Dashboard (Recommended)

1. Start the FastAPI server using Uvicorn:
   ```bash
   uvicorn api:app --reload
   ```
2. Navigate your web browser to the dashboard:
   ```
   http://127.0.0.1:8000/static/index.html
   ```

### Option 2: Run the CLI Simulation

Execute the `main.py` script to run through the pre-programmed simulation steps directly in the console.

```bash
python main.py
```

## System Breakdown

- **`main.py`**: Executes a predefined terminal simulation of inventory depletion and automatic reordering.
- **`api.py`**: FastApi backend configuring web endpoints and asynchronous simulation progression.
- **`db.py`**: Database connection management and initial table seeding for Cassandra / Redis.
- **`inventory.py`**: Business logic regarding stock adjustments and checks.
- **`reorder.py`**: Logic for checking and enqueuing items that have fallen below required thresholds.
- **`orders.py`**: A mocked subscription service processing those incoming purchase orders dynamically.
- **`logger.py`**: Helper utility to push event tracking rows into Cassandra. 

## License

This project is open-source and created for educational purposes. Feel free to modify and adapt.
