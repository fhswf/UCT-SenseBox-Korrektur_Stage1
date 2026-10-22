import os
import logging
import time
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


def create_db_engine(config, max_attempts=None, initial_wait=1.0, backoff=2.0, max_wait=60.0, blocking=True):
    db_config = config["data"]["db"]

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    dbname = db_config["dbname"]

    if not port:
        port = 5432

    db_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    attempt = 0
    wait = initial_wait
    logger = logging.getLogger("UCT_KI_Microservice")

    while True:
        attempt += 1
        try:
            engine = create_engine(db_url, pool_pre_ping=True)

            # sofort prüfen, ob die DB tatsächlich erreichbar ist
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("DB-Verbindung erfolgreich hergestellt.")
            return engine
        except OperationalError as e:
            logger.warning("DB-Verbindung fehlgeschlagen (Versuch %d): %s", attempt, e)
            if not blocking and max_attempts is not None and attempt >= max_attempts:
                logger.error("Maximale DB-Retry-Versuche erreicht.")
                raise
            if not blocking and max_attempts is None:
                # non-blocking but no max specified -> raise
                raise
            logger.info("Warte %.1fs vor nächstem Versuch...", wait)
            time.sleep(wait)
            wait = min(wait * backoff, max_wait)
        except Exception:
            logger.exception("Unerwarteter Fehler beim Erstellen der DB-Verbindung.")
            raise

def test_db_connection(engine):
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logging.getLogger("UCT_KI_Microservice").error("DB-Verbindungstest fehlgeschlagen: %s", e)
        return False
    
def reconnect_db_engine(engine, config, max_attempts=5, initial_wait=1.0, backoff=2.0, max_wait=60.0):
    logger = logging.getLogger("UCT_KI_Microservice")
    logger.info("Prüfe DB-Verbindung...")
    if test_db_connection(engine):
        logger.info("DB-Verbindung ist stabil.")
        return engine
    else:
        logger.warning("DB-Verbindung verloren. Versuche Reconnect...")
        return create_db_engine(config, max_attempts=max_attempts, initial_wait=initial_wait, backoff=backoff, max_wait=max_wait, blocking=False)
        
    