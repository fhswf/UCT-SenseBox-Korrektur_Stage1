from typing import Any, Dict, List, Optional
import threading
import pandas as pd
import logging

from services.measurements_service import fetch_neighbor_measurements

class MeasurementBuffer:
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._last_ts: Dict[str, pd.Timestamp] = {}

    def init_load(self, engine, ids: List[str], config):
        if not ids:
            return

        df = fetch_neighbor_measurements(engine, ids, pd.Timestamp.utcnow(), config)
        if df.empty:
            # Wenn IDs erwartet wurden, aber keine Daten zurückkamen,
            # ist das ein Fehler (z.B. DB-Problem) und sollte retries auslösen.
            raise RuntimeError("Keine Messwerte für die angefragten Nachbarn gefunden.")

        with self._lock:
            for _, row in df.iterrows():
                qid = str(row['quell_id'])
                self._store[qid] = row
                self._last_ts[qid] = row.get('messzeit_utc')
        logging.getLogger("UCT_KI_Microservice").info("MeasurementBuffer initialisiert mit %d Einträgen.", len(self._store))
        logging.getLogger("UCT_KI_Microservice").debug("Erste Einträge: %s", list(self._store.keys())[:5])

    def add_measurement(self, quell_id: str, row: Any):
        qid = str(quell_id)
        with self._lock:
            self._store[qid] = row
            ts = row.get('messzeit_utc') if hasattr(row, 'get') else None
            if ts is not None:
                self._last_ts[qid] = ts
        logging.getLogger("UCT_KI_Microservice").debug("MeasurementBuffer aktualisiert für ID %s mit Timestamp %s", qid, ts)
        logging.getLogger("UCT_KI_Microservice").debug("aktuelle werte im buffer für die eingefügte ID: %s", self._store[qid])

    def get_time_valid(self, ids: List[str], messzeit_utc: pd.Timestamp) -> Dict[str, Optional[Any]]:
        # Stelle sicher, dass messzeit_utc ein Timestamp ist
        if not isinstance(messzeit_utc, pd.Timestamp):
            messzeit_utc = pd.to_datetime(messzeit_utc, utc=True)

        start = messzeit_utc - pd.Timedelta(minutes=20)
        end = messzeit_utc + pd.Timedelta(minutes=20)

        out: Dict[str, Optional[Any]] = {}
        with self._lock:
            for q in ids:
                row = self._store.get(str(q))
                if row is not None:
                    ts = row.get('messzeit_utc')
                    if ts is None:
                        continue
                    ts = pd.to_datetime(ts, utc=True)
                    if start <= ts <= end:
                        out[str(q)] = row
        logging.getLogger("UCT_KI_Microservice").debug("get_time_valid: Gefundene gültige Messungen für IDs %s: %s", ids, list(out.keys()))
        logging.getLogger("UCT_KI_Microservice").debug("Gefundene Datensätze: %s", list(out.values())[:5])
        return out

    def all_ids(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())