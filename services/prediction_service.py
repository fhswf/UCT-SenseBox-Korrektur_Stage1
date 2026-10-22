import yaml
import joblib
import pandas as pd
import numpy as np
import tensorflow as tf
import asyncio
import logging
import time

from core.build_model import Model
from core.database import create_db_engine
from services.neighbor_service import NeighborService
from services.measurements_service import fetch_neighbor_measurements
from services.preprocessing import messzeit_utc_handling
from services.measurements_buffer import MeasurementBuffer

class PredictionService:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.measurement_buffer = MeasurementBuffer()
        self.config = None
        self.db_engine = None
        self.neighbor_service = NeighborService()

        self.features_scale = [
            'temperature_value_neighbor_1', 
            'humidity_value_neighbor_1', 
            'pressure_value_neighbor_1', 
            'lux_value_neighbor_1', 
            'uv_value_neighbor_1', 
            'temperature_value_neighbor_2', 
            'humidity_value_neighbor_2', 
            'pressure_value_neighbor_2', 
            'lux_value_neighbor_2', 
            'uv_value_neighbor_2', 
            'temperature_value', 
            'humidity_value', 
            'pressure_value', 
            'lux_value', 
            'uv_value'
        ]

        self.features_pass = [
            'hour_sin', 
            'hour_cos', 
            'doy_cos'
        ]

    def load_resources(self, config_path, model_path, scaler_path):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.db_engine = create_db_engine(self.config)

        # Modell laden
        input_dim = len(self.features_scale) + len(self.features_pass)
        
        tf.keras.backend.clear_session()
        self.model = Model(input_dim=input_dim, hidden_units=self.config['model']['hidden_units'])
        self.model.build((None, input_dim))
        self.model.load_weights(model_path)

        # Scaler laden
        self.scaler = joblib.load(scaler_path)

        # Startup / Retry-Konfiguration
        startup_conf = self.config.get('startup', {})
        retry_interval = startup_conf.get('retry_interval_seconds', 10)
        max_retries = startup_conf.get('max_retries', 0)  # 0 = infinite

        logger = logging.getLogger("UCT_KI_Microservice")

        # Initiale Aktualisierung der Nachbartabelle (mit Retry), damit Nachbarn
        # geladen sind bevor der Messwerte-Puffer befüllt wird. Bei Fehlschlag
        # wird weiter versucht (Standard: unendlich), Service startet erst nach Erfolg.
        attempt = 0
        while True:
            try:
                self.neighbor_service.update_neighbors(self.db_engine, self.config)
                logger.info("Initiales Laden der Nachbarn erfolgreich")
                break
            except Exception as e:
                attempt += 1
                logger.warning("Initiales Laden der Nachbarn fehlgeschlagen (Versuch %d): %s", attempt, e)
                if max_retries and attempt >= max_retries:
                    logger.error("Maximale Anzahl an Versuchen erreicht. Service wird nicht gestartet.")
                    raise
                time.sleep(retry_interval)

        # Initialen Puffer mit aktuellen Messungen der Nachbarn füllen (mit Retry
        # und optionalem Reconnect der DB-Engine bei Fehlern)
        neighbor_ids = self.neighbor_service.get_all_neighbor_ids()
        attempt = 0
        while True:
            try:
                self.measurement_buffer.init_load(self.db_engine, neighbor_ids, config=self.config)
                logger.info("Initialer Messwerte-Puffer erfolgreich geladen")
                break
            except Exception as e:
                attempt += 1
                logger.warning("Initiales Laden des Messwerte-Puffers fehlgeschlagen (Versuch %d): %s", attempt, e)
                # Versuche, die DB-Verbindung neu aufzubauen bevor erneut versucht wird
                try:
                    self.db_engine = create_db_engine(self.config)
                    logger.info("Datenbankverbindung neu aufgebaut")
                except Exception as e_db:
                    logger.exception("Wiederaufbau der Datenbankverbindung fehlgeschlagen: %s", e_db)

                if max_retries and attempt >= max_retries:
                    logger.error("Maximale Anzahl an Versuchen erreicht. Service wird nicht gestartet.")
                    raise
                time.sleep(retry_interval)

        # Nachbartabelle regelmäßig im Hintergrund aktualisieren (erst nach erfolgreicher Initialisierung)
        asyncio.create_task(self.update_loop())

    def _filter_neighbors_by_median(self, measurements_df, num_out):
        if measurements_df.empty:
            return measurements_df

        # Filtern der Nachbarmesswerte
        temp_conf = self.config.get('preprocessing', {})
        boundaries = temp_conf.get('boundaries', {})
        specific_values = temp_conf.get('specific_values', {})

        df_valid = measurements_df.copy()
        for col in df_valid.columns:
            # Werte außerhalb physikalischer Grenzen
            for feature, limits in boundaries.items():
                if col.startswith(feature):
                    min_val, max_val = limits
                    df_valid[col] = df_valid[col].where((df_valid[col] >= min_val) & (df_valid[col] <= max_val), np.nan)
                # Spezifische Ausschlusswerte
            for feature, values in specific_values.items():
                if col.startswith(feature):
                    df_valid[col] = df_valid[col].where(~df_valid[col].isin(values), np.nan)
        # Entferne Zeilen, bei denen Temperatur NaN ist
        df_valid = df_valid[df_valid['temperature_value'].notna()]

        if df_valid.empty:
            return pd.DataFrame()

        if len(df_valid) <= num_out:
            return df_valid
        
        median_temp = df_valid['temperature_value'].median()

        # Berechnung der Abweichung zum Median
        df_valid['median_diff'] = (df_valid['temperature_value'] - median_temp).abs()

        # Nutze Nachbarn mit der geringsten Abweichung zum Median
        final_df = df_valid.sort_values('median_diff').head(num_out)

        logging.getLogger("UCT_KI_Microservice").debug(
            "Median-Filter: Median war %.2f. Gewählte Stationen: %s",
            median_temp,
            final_df['quell_id'].tolist()
        )
        
        return final_df

    async def update_loop(self):
        while True:
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, self.neighbor_service.update_neighbors, self.db_engine, self.config)
            except Exception as e:
                logging.getLogger("UCT_KI_Microservice").exception(
                    "Fehler in update_loop beim Aktualisieren der Nachbarn: %s", e
                )

            await asyncio.sleep(24 * 60 * 60)
        
    async def predict(self, input_data):
        df = pd.DataFrame([input_data])
        quell_id = input_data["quell_id"]
        messzeit_utc = input_data["messzeit_utc"]
        messzeit_utc = pd.to_datetime(messzeit_utc, utc=True)

        # messung in buffer aktualisieren
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.measurement_buffer.add_measurement, quell_id, df.iloc[0])

        # Nachbarn finden
        n_cons, n_out = self.config['preprocessing']['number_of_neighbors']
        neighbors_ids = self.neighbor_service.get_neighbors(quell_id, limit=n_cons)
        logging.getLogger("UCT_KI_Microservice").debug("Gefundene Nachbarn für %s: %s", quell_id, neighbors_ids)

        # Nachbarmesswerte aus DB holen
        neighbor_df = pd.DataFrame()
        if neighbors_ids:
            loop = asyncio.get_event_loop()
            neighbor_df = await loop.run_in_executor(None, self.measurement_buffer.get_time_valid, neighbors_ids, messzeit_utc)
            neighbor_df = pd.DataFrame(list(neighbor_df.values()))

        if neighbor_df.empty:
            raise ValueError("Keine gültigen Nachbarmessungen gefunden. Vorhersage nicht möglich.")

        # Median-Filterung
        final_neighbors_df = self._filter_neighbors_by_median(neighbor_df, n_out)
        logging.getLogger("UCT_KI_Microservice").debug("Nach der Median-Filterung verbleibende Nachbarmessungen: %d", len(final_neighbors_df))

        if len(final_neighbors_df) < n_out:
            raise ValueError(f"Nicht genügend valide Nachbarmessungen nach Filterung. Benötigt: {n_out}, Gefunden: {len(final_neighbors_df)}")

        val_mapping = {
            "temperature_value": "temperature_value",
            "humidity_value": "humidity_value",
            "pressure_value": "pressure_value",
            "lux_value": "lux_value",
            "uv_value": "uv_value"
        }

        # DF vorbereiten
        for feature in self.features_scale:
            if feature in df.columns:
                continue

            if "_neighbor_" in feature:
                parts = feature.split("_neighbor_")
                val_type = parts[0]
                idx = int(parts[1]) - 1
                
                if idx < len(final_neighbors_df):
                    neighbor_row = final_neighbors_df.iloc[idx]
                    db_col = val_mapping.get(val_type)

                    val = neighbor_row.get(db_col, np.nan)
                    df[feature] = val if pd.notna(val) else np.nan
                else:
                    df[feature] = np.nan

        # Zeitliche Features
        time_conf = self.config['preprocessing']['feature_engineering']['measurement_time_handling']
        df = messzeit_utc_handling(df, time_conf)

        expected_order = self.features_scale + self.features_pass
        logger = logging.getLogger("UCT_KI_Microservice")
        logger.debug("--- [DEBUG] Verifizierung der Eingabe-Features ---")
        for i, feat in enumerate(expected_order):
            status = "OK" if feat in df.columns else "MISSING!"
            val = df[feat].values[0] if feat in df.columns else "N/A"
            logger.debug("%02d. %s | Status: %s | Wert: %s", i+1, feat.ljust(30), status, val)
        logger.debug("-------------------------------------------------------")

        try:
            # Abbrechen bei NaN-Werten
            if df[self.features_scale + self.features_pass].isna().any().any():
                raise ValueError("NaN im Input gefunden – Vorhersage wird abgebrochen")
            
            X_scaled = self.scaler.transform(df[self.features_scale].values)
            X_pass = df[self.features_pass].values
    
            logging.getLogger("UCT_KI_Microservice").debug("Skalierter Input:\n%s", X_scaled)
            logging.getLogger("UCT_KI_Microservice").debug("Pass-Through Input:\n%s", X_pass)
            
            X_input = np.hstack([X_scaled, X_pass])

            y_pred = self.model(X_input, training=False)
            
            return float(y_pred[0][0])
        except Exception as e:
            logging.getLogger("UCT_KI_Microservice").exception("Fehler während der Vorhersage: %s", e)
            raise e
        
service = PredictionService()