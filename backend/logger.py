"""
Logging estructurado — Forecast DCIC
Formato JSON para producción, formato legible para desarrollo.
Correlation ID propagado via ContextVar a todas las líneas de log de un request.
"""
import logging
import json
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# ContextVar que el middleware de FastAPI setea al inicio de cada request
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def get_correlation_id() -> str:
    return _correlation_id.get()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        cid = _correlation_id.get()
        if cid:
            payload["req_id"] = cid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            payload.update(record.extra)
        return json.dumps(payload, ensure_ascii=False)


class _DevFormatter(logging.Formatter):
    COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        base = f"{color}[{ts}] {record.levelname:<8}{self.RESET} {record.name} — {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def get_logger(name: str) -> logging.Logger:
    """Retorna un logger configurado. Usar al tope de cada módulo."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # ya configurado

    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    json_mode = os.getenv("LOG_FORMAT", "dev").lower() == "json"
    handler.setFormatter(_JsonFormatter() if json_mode else _DevFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# Logger raíz de la aplicación
log = get_logger("forecast_dcic")
