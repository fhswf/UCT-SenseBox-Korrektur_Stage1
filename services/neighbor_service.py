import pandas as pd
from shapely import wkb
import logging
from core.database import reconnect_db_engine

class NeighborService:
    def __init__(self):
        self.neighbor_map = {} 
    
    def update_neighbors(self, engine, config, measurement_time_utc=None):
        logger = logging.getLogger("UCT_KI_Microservice")
        logger.info("Aktualisiere Nachbartabelle...")

        try:

            engine = reconnect_db_engine(engine, config)
            if measurement_time_utc is None:
                measurement_time_utc = pd.Timestamp.utcnow()
            else:
                # datetime now
                measurement_time_utc = pd.to_datetime(measurement_time_utc, utc=True)

            query = """
                SELECT q.id AS quell_id, l.center as location
                FROM quelle q
                JOIN location l ON q.location_id = l.id
                WHERE l.until_date > %(timestamp)s
                AND q.until_date > %(timestamp)s
                AND l.typ = 'sensor'
                AND q.typ = 'senseBox';
            """
            
            # Use explicit connection
            with engine.connect() as conn:
                df = pd.read_sql(query, conn, params={"timestamp": measurement_time_utc})
            
            if df.empty:
                logger.warning("WARNUNG: Keine aktiven Sensoren gefunden.")
                return engine

            df.columns = [c.lower() for c in df.columns]

            df['geometry_utm'] = df['location'].apply(
                lambda x: wkb.loads(x, hex=True) if pd.notna(x) else None
            )
            
            # Entferne Zeilen mit ungültigen Geometrien oder fehlenden IDs
            df = df.dropna(subset=['geometry_utm', 'quell_id']).reset_index(drop=True)
            df['quell_id'] = df['quell_id'].astype(str)

            num_neighbors = config['preprocessing']['number_of_neighbors'][0]

            new_map = {}
            
            for _, row in df.iterrows():
                current_id = row['quell_id']
                current_geom = row['geometry_utm']

                distances = df['geometry_utm'].apply(lambda g: current_geom.distance(g))
                
                closest_indices = distances.sort_values().index
                neighor_ids = df.loc[closest_indices]
                
                final_neighbors = neighor_ids[neighor_ids['quell_id'] != current_id].head(num_neighbors)['quell_id'].tolist()
                new_map[current_id] = final_neighbors
            
            self.neighbor_map = new_map
            logger.info("Nachbartabelle aktualisiert: %d Sensoren verarbeitet.", len(new_map))
            return engine

        except Exception as e:
            logger.exception("Fehler beim Update der Nachbarn: %s", e)
            # Fehler weiterreichen, damit Aufrufer (z.B. beim Startup) Retry-Logik auslösen kann
            raise

    def get_neighbors(self, quell_id, limit=5):
        return self.neighbor_map.get(str(quell_id), [])[:limit]
    
    def get_all_neighbor_ids(self):
        all_ids = set()
        for neighbors in self.neighbor_map.values():
            all_ids.update(neighbors)
        return list(all_ids)