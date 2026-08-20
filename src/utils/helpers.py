"""
Utilidades generales del sistema.
"""
import logging
from datetime import datetime
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configura el sistema de logging.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
        log_file: Ruta al archivo de log (opcional)
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers = [logging.StreamHandler()]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=handlers,
    )


def format_currency(value: float, currency: str = "USD") -> str:
    """
    Formatea un valor numérico como moneda.
    
    Args:
        value: Valor numérico
        currency: Código de moneda
    
    Returns:
        String formateado (ej: "$1,234.56")
    """
    if currency == "USD":
        return f"${value:,.2f}"
    return f"{value:,.2f} {currency}"


def format_percentage(value: float) -> str:
    """
    Formatea un valor como porcentaje.
    
    Args:
        value: Valor numérico
    
    Returns:
        String formateado (ej: "85.5%")
    """
    return f"{value:.1f}%"


def get_week_label(year: int, week: int) -> str:
    """
    Retorna label de semana (ej: "2026-S03").
    
    Args:
        year: Año
        week: Número de semana
    
    Returns:
        String con formato semana
    """
    return f"{year}-S{week:02d}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    División segura que retorna default si el denominador es 0.
    
    Args:
        numerator: Numerador
        denominator: Denominador
        default: Valor por defecto si división es 0
    
    Returns:
        Resultado de la división o default
    """
    if denominator == 0:
        return default
    return numerator / denominator
