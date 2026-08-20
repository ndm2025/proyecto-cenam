"""
Módulo de generación de KPIs.
Calcula indicadores clave de desempeño por país y semana.
"""
import pandas as pd
import logging
from typing import Optional

from config.settings import PAISES

logger = logging.getLogger(__name__)


def calculate_budget_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula KPIs de presupuesto por país.
    
    Returns:
        DataFrame con KPIs presupuestarios
    """
    if df.empty:
        return pd.DataFrame()
    
    kpis = []
    
    for pais in PAISES:
        df_pais = df[df["PAÍS"] == pais] if "PAÍS" in df.columns else df
        
        monto_col = "MONTO PEDIDO" if "MONTO PEDIDO" in df_pais.columns else None
        monto_total = 0
        if monto_col:
            monto_total = pd.to_numeric(
                df_pais[monto_col].astype(str).str.replace(",", ""),
                errors="coerce"
            ).sum()
        
        kpis.append({
            "PAÍS": pais,
            "Total Solped": len(df_pais),
            "Monto Total": monto_total,
            "Proyectos": df_pais["PROYECTO"].nunique() if "PROYECTO" in df_pais.columns else 0,
        })
    
    return pd.DataFrame(kpis)


def calculate_status_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula KPIs de estatus de proyectos.
    
    Returns:
        DataFrame con KPIs de estatus
    """
    if df.empty or "STATUS" not in df.columns:
        return pd.DataFrame()
    
    status_counts = df.groupby(["PAÍS", "STATUS"]).size().reset_index(name="Cantidad")
    
    total_by_country = df.groupby("PAÍS").size().reset_index(name="Total")
    
    merged = pd.merge(status_counts, total_by_country, on="PAÍS")
    merged["Porcentaje"] = (merged["Cantidad"] / merged["Total"] * 100).round(1)
    
    return merged


def calculate_carry_over(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifica proyectos en carry over (atrasados).
    
    Returns:
        DataFrame con proyectos carry over
    """
    if df.empty:
        return pd.DataFrame()
    
    carry_over_col = "CARRY OVER" if "CARRY OVER" in df.columns else None
    
    if carry_over_col:
        df_co = df[df[carry_over_col].notna() & (df[carry_over_col] != "")]
    else:
        df_co = pd.DataFrame()
    
    return df_co


def calculate_purchase_timeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula tiempos de proceso de compras.
    
    Returns:
        DataFrame con tiempos de proceso
    """
    if df.empty:
        return pd.DataFrame()
    
    timeline_cols = {
        "TIEMPO DE CUTEFLOW": "Días Cuteflow",
        "TIEMPO LIBERACIÓN SOLPED": "Días Liberación",
        "TIEMPO EN COMPRAS": "Días Compras",
        "CONTEO DÍAS EN PROCESO DE CARGA": "Días Carga",
    }
    
    available = {k: v for k, v in timeline_cols.items() if k in df.columns}
    
    if not available:
        return pd.DataFrame()
    
    result = df[["PAÍS"] + list(available.keys())].copy() if "PAÍS" in df.columns else df[list(available.keys())].copy()
    result = result.rename(columns=available)
    
    for col in result.columns:
        if col != "PAÍS":
            result[col] = pd.to_numeric(result[col], errors="coerce")
    
    if "PAÍS" in result.columns:
        result = result.groupby("PAÍS").mean().reset_index()
    
    return result


def calculate_budget_comparison(
    df_consolidated: pd.DataFrame,
    df_planning: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Compara presupuesto real vs planificado por país.
    
    Returns:
        DataFrame con comparativa presupuestaria
    """
    if df_consolidated.empty:
        return pd.DataFrame()
    
    real = calculate_budget_kpis(df_consolidated)
    
    if df_planning is not None and not df_planning.empty:
        plan = calculate_budget_kpis(df_planning)
        plan = plan.rename(columns={"Monto Total": "Monto Planificado", "Total Solped": "Solped Planificados"})
        comparison = pd.merge(real, plan, on="PAÍS", how="outer")
        
        if "Monto Total" in comparison.columns and "Monto Planificado" in comparison.columns:
            comparison["Cumplimiento %"] = (
                comparison["Monto Total"] / comparison["Monto Planificado"] * 100
            ).round(1)
        
        return comparison
    
    return real


def generate_weekly_kpis(
    df: pd.DataFrame,
    date_column: str = "FECHA DE SOLICITUD SISTEMA"
) -> pd.DataFrame:
    """
    Genera KPIs semanales.
    
    Returns:
        DataFrame con KPIs por semana
    """
    if df.empty or date_column not in df.columns:
        return pd.DataFrame()
    
    df = df.copy()
    df["_fecha"] = pd.to_datetime(df[date_column], errors="coerce", dayfirst=True)
    df["_semana"] = df["_fecha"].dt.isocalendar().week
    df["_año"] = df["_fecha"].dt.year
    
    weekly = df.groupby(["PAÍS", "_año", "_semana"]).agg(
        Solped_Nuevos=("PEDIDOPOS2", "count") if "PEDIDOPOS2" in df.columns else ("PAÍS", "count"),
        Monto=("MONTO PEDIDO", lambda x: pd.to_numeric(
            x.astype(str).str.replace(",", ""), errors="coerce"
        ).sum()) if "MONTO PEDIDO" in df.columns else ("PAÍS", "count"),
    ).reset_index()
    
    weekly = weekly.rename(columns={"_año": "Año", "_semana": "Semana"})
    
    return weekly
