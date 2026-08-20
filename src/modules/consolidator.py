"""
Módulo de consolidación de datos SAP.
Consolida las 5 bases de países en una sola base unificada.
"""
import pandas as pd
import logging
from pathlib import Path
from typing import Optional

from config.settings import (
    COLUMNAS_CONSOLIDADO, PAISES, MAPEO_SOLPED_CONSOLIDADO,
    CONSOLIDATED_DIR, PROCESSED_DIR
)

logger = logging.getLogger(__name__)


def consolidate_countries(
    dfs_by_country: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Consolida DataFrames de múltiples países en uno solo.
    
    Args:
        dfs_by_country: Dict {país: DataFrame}
    
    Returns:
        DataFrame consolidado con todos los países
    """
    frames = []
    for pais, df in dfs_by_country.items():
        if df is not None and not df.empty:
            df = df.copy()
            if "PAÍS" not in df.columns:
                df["PAÍS"] = pais
            frames.append(df)
    
    if not frames:
        logger.warning("No hay datos para consolidar")
        return pd.DataFrame()
    
    consolidated = pd.concat(frames, ignore_index=True)
    logger.info(f"Consolidado: {len(consolidated)} filas de {len(frames)} países")
    return consolidated


def map_to_consolidated_format(df: pd.DataFrame, mapping: dict = None) -> pd.DataFrame:
    """
    Mapea columnas de SAP al formato consolidado estándar.
    
    Args:
        df: DataFrame con columnas SAP
        mapping: Dict de mapeo {columna_sap: columna_consolidado}
    
    Returns:
        DataFrame con columnas renombradas
    """
    if mapping is None:
        mapping = MAPEO_SOLPED_CONSOLIDADO
    
    df = df.copy()
    
    existing_mappings = {k: v for k, v in mapping.items() if k in df.columns}
    df = df.rename(columns=existing_mappings)
    
    logger.info(f"Mapeo: {len(existing_mappings)} columnas renombradas")
    return df


def compare_with_planning(
    df_consolidated: pd.DataFrame,
    df_planning: pd.DataFrame,
    key_column: str = "PEDIDOPOS2"
) -> pd.DataFrame:
    """
    Compara el consolidado con el cuadro de planificación.
    Verifica que montos e IDs coincidan.
    
    Args:
        df_consolidated: DataFrame consolidado
        df_planning: DataFrame de planificación (Excel)
        key_column: Columna llave para cruce
    
    Returns:
        DataFrame con columnas de comparación
    """
    if key_column not in df_consolidated.columns:
        logger.error(f"Columna {key_column} no encontrada en consolidado")
        return df_consolidated
    
    df = df_consolidated.copy()
    
    planning_cols_to_merge = []
    if key_column in df_planning.columns:
        for col in df_planning.columns:
            if col != key_column:
                planning_cols_to_merge.append(col)
    
    if planning_cols_to_merge:
        df = pd.merge(
            df,
            df_planning[[key_column] + planning_cols_to_merge],
            on=key_column,
            how="left",
            suffixes=("_consolidado", "_planificacion"),
        )
    
    if "MONTO PEDIDO" in df.columns and "MONTO OFERTA" in df.columns:
        df["COINCIDE_MONTO"] = (
            pd.to_numeric(df["MONTO PEDIDO"].astype(str).str.replace(",", ""), errors="coerce")
            == pd.to_numeric(df["MONTO OFERTA"].astype(str).str.replace(",", ""), errors="coerce")
        )
    
    logger.info(f"Comparación con planificación: {len(df)} filas")
    return df


def save_consolidated(df: pd.DataFrame, filename: str = "consolidado.csv") -> Path:
    """
    Guarda el consolidado en disco.
    
    Args:
        df: DataFrame a guardar
        filename: Nombre del archivo
    
    Returns:
        Ruta del archivo guardado
    """
    CONSOLIDATED_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CONSOLIDATED_DIR / filename
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    logger.info(f"Consolidado guardado: {filepath}")
    return filepath


def load_consolidated(filename: str = "consolidado.csv") -> Optional[pd.DataFrame]:
    """
    Carga un consolidado previo desde disco.
    
    Args:
        filename: Nombre del archivo
    
    Returns:
        DataFrame o None si no existe
    """
    filepath = CONSOLIDATED_DIR / filename
    if filepath.exists():
        df = pd.read_csv(filepath, dtype=str, low_memory=False)
        logger.info(f"Consolidado cargado: {filepath.name} → {len(df)} filas")
        return df
    logger.warning(f"Consolidado no encontrado: {filepath}")
    return None


def get_summary_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera resumen de proyectos por país.
    
    Returns:
        DataFrame con estadísticas por país
    """
    if "PAÍS" not in df.columns:
        return pd.DataFrame()
    
    summary = df.groupby("PAÍS").agg(
        Total_Solped=("PEDIDOPOS2", "count"),
        Monto_Total=("MONTO PEDIDO", lambda x: pd.to_numeric(
            x.astype(str).str.replace(",", ""), errors="coerce"
        ).sum()),
        Proyectos=("PROYECTO", "nunique") if "PROYECTO" in df.columns else ("PEDIDOPOS2", "count"),
    ).reset_index()
    
    logger.info(f"Resumen por país: {len(summary)} países")
    return summary
