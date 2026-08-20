"""
Módulo de procesamiento de archivos SAP.
Lee archivos .txt exportados de SAP, los limpia y transforma para consolidación.
"""
import pandas as pd
import logging
from pathlib import Path
from typing import Optional

from config.settings import (
    COLUMNAS_SOLPED, COLUMNAS_PEDIDO, COLUMNAS_OFERTA,
    PAISES_CODIGO, MAPEO_SOLPED_CONSOLIDADO
)

logger = logging.getLogger(__name__)


def read_sap_file(filepath: Path, delimiter: str = "\t", encoding: str = "latin-1") -> pd.DataFrame:
    """
    Lee un archivo .txt exportado de SAP y retorna un DataFrame.
    
    Args:
        filepath: Ruta al archivo .txt
        delimiter: Delimitador del archivo (default: tab)
        encoding: Codificación del archivo (default: latin-1)
    
    Returns:
        DataFrame con los datos del archivo
    """
    try:
        df = pd.read_csv(
            filepath,
            sep=delimiter,
            encoding=encoding,
            dtype=str,
            low_memory=False,
            on_bad_lines="skip",
        )
        df.columns = df.columns.str.strip()
        logger.info(f"Archivo leído: {filepath.name} → {len(df)} filas, {len(df.columns)} columnas")
        return df
    except Exception as e:
        logger.error(f"Error leyendo {filepath}: {e}")
        raise


def clean_solped(df: pd.DataFrame, pais: str) -> pd.DataFrame:
    """
    Limpia y transforma datos de solped de un país.
    
    Pasos:
    1. Eliminar filas completamente vacías
    2. Limpiar espacios en blanco
    3. Crear columna PEDIDOPOS2 = Sol.pedido + Pos.
    4. Agregar columna País
    """
    df = df.copy()
    
    df = df.dropna(how="all")
    
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
    
    if "Sol.pedido" in df.columns and "Pos." in df.columns:
        df["PEDIDOPOS2"] = df["Sol.pedido"].astype(str) + df["Pos."].astype(str)
    
    df["PAÍS"] = pais
    df["CÓDIGO PAÍS"] = PAISES_CODIGO.get(pais, "")
    
    logger.info(f"Solped {pais}: {len(df)} filas después de limpieza")
    return df


def clean_pedido(df: pd.DataFrame, pais: str) -> pd.DataFrame:
    """
    Limpia y transforma datos de pedidos de un país.
    
    Pasos:
    1. Eliminar filas vacías
    2. Limpiar espacios
    3. Crear PEDIDOPOS2
    4. Agregar país
    """
    df = df.copy()
    
    df = df.dropna(how="all")
    
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
    
    if "Sol.pedido" in df.columns and "Pos." in df.columns:
        df["PEDIDOPOS2"] = df["Sol.pedido"].astype(str) + df["Pos."].astype(str)
    
    df["PAÍS"] = pais
    df["CÓDIGO PAÍS"] = PAISES_CODIGO.get(pais, "")
    
    logger.info(f"Pedido {pais}: {len(df)} filas después de limpieza")
    return df


def clean_oferta(df: pd.DataFrame, pais: str) -> pd.DataFrame:
    """
    Limpia y transforma datos de ofertas.
    
    Pasos:
    1. Eliminar filas vacías
    2. Limpiar espacios
    3. Crear llave OF+ID+IO
    4. Agregar país
    """
    df = df.copy()
    
    df = df.dropna(how="all")
    
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
    
    if all(c in df.columns for c in ["OF", "ID", "IO"]):
        df["LLAVE_OFERTA"] = df["OF"].astype(str) + df["ID"].astype(str) + df["IO"].astype(str)
    
    df["PAÍS"] = pais
    df["CÓDIGO PAÍS"] = PAISES_CODIGO.get(pais, "")
    
    logger.info(f"Oferta {pais}: {len(df)} filas después de limpieza")
    return df


def build_pedido_pos2(df_solped: pd.DataFrame, df_pedido: pd.DataFrame) -> pd.DataFrame:
    """
    Construye el consolidado SOLP + PEDIDO usando PEDIDOPOS2 como llave.
    
    Args:
        df_solped: DataFrame de solped limpio
        df_pedido: DataFrame de pedidos limpio
    
    Returns:
        DataFrame consolidado
    """
    if "PEDIDOPOS2" not in df_solped.columns:
        logger.warning("No existe PEDIDOPOS2 en solped")
        return df_solped
    
    if "PEDIDOPOS2" not in df_pedido.columns:
        logger.warning("No existe PEDIDOPOS2 en pedido")
        return df_solped
    
    consolidated = pd.merge(
        df_solped,
        df_pedido,
        on="PEDIDOPOS2",
        how="left",
        suffixes=("_solped", "_pedido"),
    )
    
    logger.info(f"Consolidado SOLP+PEDIDO: {len(consolidated)} filas")
    return consolidated


def eliminate_duplicates(df: pd.DataFrame, key_column: str = "PEDIDOPOS2") -> pd.DataFrame:
    """
    Elimina duplicados basándose en una columna llave.
    
    Args:
        df: DataFrame de entrada
        key_column: Columna usada como llave única
    
    Returns:
        DataFrame sin duplicados
    """
    before = len(df)
    df = df.drop_duplicates(subset=[key_column], keep="first")
    after = len(df)
    eliminated = before - after
    logger.info(f"Duplicados eliminados: {eliminated} filas ({before} → {after})")
    return df


def validate_against_consolidated(
    df_new: pd.DataFrame,
    df_consolidated: pd.DataFrame,
    key_column: str = "PEDIDOPOS2"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Valida que las solped de un país no estén ya en el consolidado.
    Retorna (nuevos, duplicados).
    
    Args:
        df_new: DataFrame nuevo a validar
        df_consolidated: DataFrame consolidado existente
        key_column: Columna llave para comparar
    
    Returns:
        Tuple de (dataframe_nuevos, dataframe_duplicados)
    """
    if key_column not in df_consolidated.columns:
        logger.warning(f"Columna {key_column} no encontrada en consolidado")
        return df_new, pd.DataFrame()
    
    consolidated_keys = set(df_consolidated[key_column].astype(str))
    
    mask_new = ~df_new[key_column].astype(str).isin(consolidated_keys)
    mask_dup = df_new[key_column].astype(str).isin(consolidated_keys)
    
    df_nuevos = df_new[mask_new].copy()
    df_duplicados = df_new[mask_dup].copy()
    
    logger.info(f"Validación: {len(df_nuevos)} nuevos, {len(df_duplicados)} duplicados")
    return df_nuevos, df_duplicados


def detect_file_type(filepath: Path) -> str:
    """
    Detecta el tipo de archivo SAP por sus columnas.
    
    Returns:
        Tipo detectado: "solped", "pedido", "oferta", "desconocido"
    """
    try:
        df = pd.read_csv(filepath, sep="\t", encoding="latin-1", nrows=0, dtype=str)
        cols = set(col.strip() for col in df.columns)
        
        solped_cols = {"PosPre", "Ce.gestor", "Presup.", "Mon.", "Tp.valor"}
        pedido_cols = {"Sol.pedido", "Fe.solic.", "Valor tot. Solicit.", "GCp"}
        oferta_cols = {"OF", "ID", "IO", "CORRELATIVO"}
        
        if solped_cols.issubset(cols):
            return "solped"
        elif pedido_cols.issubset(cols):
            return "pedido"
        elif oferta_cols.issubset(cols):
            return "oferta"
        else:
            return "desconocido"
    except Exception as e:
        logger.error(f"Error detectando tipo de archivo: {e}")
        return "desconocido"
