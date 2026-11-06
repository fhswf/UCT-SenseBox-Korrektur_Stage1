# KI-Korrektur Stage 1 – Urban Climate Twin Soest

Dieser Microservice korrigiert die Temperatur eingehender SenseBox-Messungen mithilfe eines trainierten Machine-Learning-Modells. Er stellt die Vorhersage über eine HTTP-API bereit und kann beispielsweise von Node-RED aufgerufen werden.

## Urban Climate Twin Soest

[Urban Climate Twin (UCT) Soest](https://www.fh-swf.de/de/forschung___transfer_4/forschungsprojekte_1/forschungsprojekt_uct.php) ist ein digitaler Zwilling des Soester Stadtklimas. Er führt Messdaten, Geodaten und weitere Klimadaten zusammen und macht das Stadklima räumlich nachvollziehbar. Bürger und die Stadtverwaltung können so die Auswirkungen von Klimaveränderungen auf das Stadtgebiet besser verstehen und Maßnahmen zur Anpassung an den Klimawandel entwickeln.

## Funktionsweise

Beim Start lädt der Service seine Konfiguration, Modellgewichte und den zugehörigen Scaler. Außerdem verbindet er sich mit der PostgreSQL-Datenbank, ermittelt aktive SenseBox-Nachbarn und lädt deren aktuelle Messwerte. Eine Vorhersage verwendet die eingehende Messung, zeitlich passende Nachbarmessungen sowie daraus abgeleitete Zeitmerkmale.

Der Service wartet beim Start auf die Datenbank und die initialen Nachbardaten. Ohne erreichbare und passend befüllte Datenbank ist er daher nicht betriebsbereit.

## Voraussetzungen

- Docker und Docker Compose (für den empfohlenen Betrieb)
- Zugriff auf die PostgreSQL-Datenbank des UCT mit den benötigten Tabellen und Messdaten
- Die passende `.env`-Datei mit den Datenbank-Zugangsdaten

Für den lokalen Betrieb ohne Docker wird Python 3.12 benötigt; die Abhängigkeiten stehen in `requirements.txt`.

## Konfiguration

1. `.env.example` in `.env` umbenennen und die Datenbank-Zugangsdaten eintragen.

2. Prüfen, dass `assets/config.yaml` auf die gewünschte Datenbank und Vorverarbeitungseinstellungen zeigt. Die Modell- und Scaler-Dateien werden beim Start in `assets/models/` erwartet.

3. Für Docker die Beispieldatei `docker-compose.yml.example` in `docker-compose.yml` umbenennen und anpassen:
   - Den Beispielpfad `/path/to/logs/` durch ein lokales Verzeichnis für Logs ersetzen.
   - `UID:GID` durch Benutzer- und Gruppen-ID des ausführenden Benutzers ersetzen, falls der Container mit einer bestimmten Benutzer-ID laufen soll.

   Die Compose-Datei bindet `.env` ein.

## Projektstruktur

```text
.
├── assets/
│   ├── config.yaml             # Datenbankname und Modell-/Vorverarbeitungseinstellungen
│   └── models/                 # Modellgewichte und Scaler
├── core/
│   ├── build_model.py          # Definition der Modellarchitektur
│   └── database.py             # Datenbankverbindung
├── services/
│   ├── measurements_buffer.py  # Zwischenspeicher für Nachbarmessungen
│   ├── measurements_service.py # Abruf der Messwerte
│   ├── neighbor_service.py     # Ermittlung der SenseBox-Nachbarn
│   ├── prediction_service.py   # Vorverarbeitung und Temperaturvorhersage
│   └── preprocessing.py        # Zeitmerkmale und Feature-Konfiguration
├── utils/
│   └── common_utils.py         # Logging
├── main.py                     # FastAPI-Anwendung und /predict-Endpunkt
├── schemas.py                  # Request- und Response-Schemas
├── Dockerfile
├── docker-compose.yml.example
├── .env.example
└── requirements.txt
```

## Lizenz

Copyright 2026 Urban Climate Twin, Fachhochschule Südwestfalen

Lizenziert unter der [Apache License 2.0](LICENSE.md).
