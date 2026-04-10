import datetime
import db

def log_event(event_type: str, message: str):
    session = db.get_cassandra_session()
    now = datetime.datetime.now()
    session_id = 'sim_demo'  # Fixed partition for easy chronological sorting in demo
    
    query = """
        INSERT INTO supply_chain.simulation_logs 
        (session_id, event_time, event_type, message)
        VALUES (%s, %s, %s, %s)
    """
    # Async so it doesn't block the actual simulation flow too much
    session.execute_async(query, (session_id, now, event_type, message))

def get_logs():
    session = db.get_cassandra_session()
    query = """
        SELECT event_time, event_type, message 
        FROM supply_chain.simulation_logs 
        WHERE session_id = 'sim_demo'
    """
    # Synchronous for the final read
    return session.execute(query)
