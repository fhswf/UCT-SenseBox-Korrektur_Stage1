import os
from time import time
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from schemas import MeasurementInput, PredictionResponse
from services.prediction_service import service
from utils.common_utils import setup_logger

load_dotenv()

CONFIG_PATH = r"assets/config.yaml"
MODEL_PATH = r"assets/models/model__2026-02-26__SL_78437d3eb37c4703aaa5d481a108b73b.weights.h5"
SCALER_PATH = r"assets/models/scaler__2026-02-26__SL_78437d3eb37c4703aaa5d481a108b73b.pkl"

PORT = 8000
IP = "0.0.0.0"
logger = setup_logger(logfile="logs/Stage1.log", logname="UCT_KI_Microservice", level=20) #20 = INFO, 10 = DEBUG

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"📖 Read the docs at http://{IP}:{PORT}/docs")
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {CONFIG_PATH}")
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Modell-Datei nicht gefunden: {MODEL_PATH}")
    
    try:
        service.load_resources(CONFIG_PATH, MODEL_PATH, SCALER_PATH)
        logger.info("Ressourcen erfolgreich geladen.")
    except Exception as e:
        logger.exception("Fehler beim Laden der Ressourcen")
        raise e
    yield

app = FastAPI(lifespan=lifespan, title="UCT KI-Microservice Stage 1")

# api endpoint
@app.post("/predict", response_model=PredictionResponse)
async def predict(input_data: MeasurementInput):
    try:
        #start = time()
        logger.info("Eingehende Vorhersageanfrage")
        logger.debug("Input data: %s", input_data)

        result_temp = await service.predict(input_data.model_dump())

        logger.info(f"Vorhersageergebnis: {result_temp:.2f} °C")
        #end = time()
        #dauer = end - start
        #print(f"Vorhersagedauer: {dauer}")  
        return {
            "corrected_temperature": result_temp,
            "success": True,
        }
        

    except Exception as e:
        logger.exception("Fehler bei der Vorhersage")
        return {
            "corrected_temperature": -999.0,
            "success": False,
        }

if __name__ == "__main__":
    logger.info(f"Starting Uvicorn on {IP}:{PORT}")
    uvicorn.run(app, host=IP, port=PORT)