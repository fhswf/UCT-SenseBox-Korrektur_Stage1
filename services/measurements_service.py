import pandas as pd
import logging
from core.database import reconnect_db_engine

def fetch_neighbor_measurements(engine, neighbor_ids, target_time_utc, config):
    if not neighbor_ids:
        return pd.DataFrame()

    try:
        timestamp = pd.to_datetime(target_time_utc, utc=True)
        start = (timestamp - pd.Timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')
        end = (timestamp + pd.Timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S')
        
        # format IDs
        ids_tuple = tuple(neighbor_ids)
        if len(ids_tuple) == 1:
            ids_sql = f"('{ids_tuple[0]}')"
        else:
            ids_sql = str(ids_tuple)

        engine = reconnect_db_engine(engine, config)

        query = f"""
            SELECT 
                quell_id, 
                messzeit_utc, 
                (measurement_data -> 'temperature' ->> 'value')::float AS temperature_value,
                (measurement_data -> 'humidity' ->> 'value')::float AS humidity_value,
                (measurement_data -> 'pressure' ->> 'value')::float AS pressure_value,
                (measurement_data -> 'lux' ->> 'value')::float AS lux_value,
                (measurement_data -> 'uv' ->> 'value')::float AS uv_value
            FROM messungen 
            WHERE quell_id IN {ids_sql}
            AND quell_typ = 'senseBox'
            AND messzeit_utc BETWEEN '{start}' AND '{end}'
        """
        df = pd.read_sql(query, engine)

        logging.getLogger("UCT_KI_Microservice").debug("SQL Result head:\n%s", df.head())
        
        if df.empty:
            return pd.DataFrame()

        df['messzeit_utc'] = pd.to_datetime(df['messzeit_utc'], utc=True)
        df['diff'] = (df['messzeit_utc'] - timestamp).abs()
        
        best_matches = df.sort_values('diff').groupby('quell_id').first().reset_index()
        logging.getLogger("UCT_KI_Microservice").debug("Best matches:\n%s", best_matches)
        return best_matches

    except Exception as e:
        logging.getLogger("UCT_KI_Microservice").exception("DB Fehler beim Laden der Messwerte: %s", e)
        # Fehler weiterreichen, damit der Aufrufer Retry-Logik auslösen kann
        raise