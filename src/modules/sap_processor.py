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
    PAISES_CODIGO, SOC_PAISES, MAPEO_SOLPED_CONSOLIDADO
)

logger = logging.getLogger(__name__)


def _find_header_row(filepath: Path, delimiter: str = "\t", encoding: str = "latin-1") -> int:
    """
    Encuentra la fila donde inician las columnas reales del archivo SAP.
    Los archivos SAP tienen metadata antes de los headers.
    Busca la fila que contiene los nombres de columnas conocidos.
    """
    known_headers = ["PosPre", "Sol.pedido", "Pos.", "OF", "Soc.", "NºDoc.fin."]
    with open(filepath, "r", encoding=encoding) as f:
        for i, line in enumerate(f):
            tabs = line.count("\t")
            if tabs >= 5:
                for header in known_headers:
                    if header in line:
                        return i
    return 0


def read_sap_file(filepath: Path, delimiter: str = "\t", encoding: str = "latin-1") -> pd.DataFrame:
    """
    Lee un archivo .txt exportado de SAP y retorna un DataFrame.
    Detecta automáticamente dónde empiezan los headers reales.
    Maneja columnas vacías, duplicadas y encoding especial.
    """
    try:
        header_row = _find_header_row(filepath, delimiter, encoding)
        
        encodings_to_try = [encoding, "utf-8", "cp1252", "iso-8859-1"]
        lines = None
        used_encoding = encoding
        
        for enc in encodings_to_try:
            try:
                with open(filepath, "r", encoding=enc, errors="strict") as f:
                    lines = f.readlines()
                used_encoding = enc
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if lines is None:
            with open(filepath, "r", encoding="latin-1", errors="replace") as f:
                lines = f.readlines()
            used_encoding = "latin-1 (fallback)"
        
        header_line = lines[header_row]
        raw_headers = header_line.split(delimiter)
        
        non_empty_headers = []
        non_empty_indices = []
        for i, h in enumerate(raw_headers):
            if h.strip():
                non_empty_headers.append(h.strip())
                non_empty_indices.append(i)
        
        seen = {}
        unique_headers = []
        for h in non_empty_headers:
            if h in seen:
                seen[h] += 1
                unique_headers.append(f"{h}_{seen[h]}")
            else:
                seen[h] = 0
                unique_headers.append(h)
        headers = unique_headers
        
        data_lines = lines[header_row + 1:]
        data = []
        for line in data_lines:
            if line.strip():
                row = line.split(delimiter)
                filtered_row = [row[i].strip() if i < len(row) else "" for i in non_empty_indices]
                data.append(filtered_row)
        
        df = pd.DataFrame(data, columns=headers)
        df = df.dropna(how="all")
        df = df[~df.apply(lambda row: all(v == "" or v is None for v in row), axis=1)]
        
        logger.info(f"Archivo leído: {filepath.name} → {len(df)} filas, {len(df.columns)} columnas (encoding: {used_encoding})")
        return df
    except Exception as e:
        logger.error(f"Error leyendo {filepath}: {e}")
        raise


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nombres de columnas que varían entre países.
    Presupuesto → Presup.
    Clase de importe → Cl.impte.
    """
    col_map = {}
    for col in df.columns:
        clean = col.strip()
        if clean == "Presupuesto":
            col_map[col] = "Presup."
        elif clean == "Clase de importe":
            col_map[col] = "Cl.impte."
    if col_map:
        df = df.rename(columns=col_map)
    return df


def clean_solped(df: pd.DataFrame, pais: str) -> tuple[pd.DataFrame, str]:
    """
    Limpia y transforma datos de solped de un país.
    
    Filtra:
    - Cl.impte. = "Original"
    - Tp.valor = "Solicitudes de pedidos"
    
    Crea:
    - SOLP + POS = Nºdoc.ref. + Pos. (o PosRf)
    
    Returns:
        Tuple (DataFrame limpio, mensaje de estado)
    """
    df = df.copy()
    
    df = _normalize_columns(df)
    
    df = df.dropna(how="all")
    
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
    
    df = df[df["Cl.impte."] == "Original"]
    
    solicitudes = df[df["Tp.valor"] == "Solicitudes de pedidos"]
    
    if solicitudes.empty:
        valores_unicos = df["Tp.valor"].unique().tolist() if "Tp.valor" in df.columns else []
        msg = f"No hay solicitud de pedido. Valores encontrados en Tp.valor: {valores_unicos}"
        logger.warning(msg)
        return pd.DataFrame(), msg
    
    df = solicitudes
    
    if "Soc." in df.columns:
        soc_val = df["Soc."].astype(str).str.strip().iloc[0][:2].upper()
        pais_detectado = SOC_PAISES.get(soc_val, pais)
    else:
        pais_detectado = pais
    
    pos_col = "PosRf" if "PosRf" in df.columns else "Pos." if "Pos." in df.columns else None
    
    if "Nºdoc.ref." in df.columns and pos_col:
        df["SOLP + POS"] = df["Nºdoc.ref."].astype(str).str.strip() + df[pos_col].astype(str).str.strip()
    
    df["PAÍS"] = pais_detectado
    df["CÓDIGO PAÍS"] = PAISES_CODIGO.get(pais_detectado, "")
    
    df = df.reset_index(drop=True)
    
    msg = f"Solped {pais_detectado}: {len(df)} solicitudes de pedido encontradas"
    logger.info(msg)
    return df, msg


ORGC_PAIS_MAP = {
    "GT02": "GUATEMALA",
    "SV02": "EL SALVADOR",
    "HN02": "HONDURAS",
    "NI02": "NICARAGUA",
    "CR02": "COSTA RICA",
}


def read_me5a(filepath: Path) -> pd.DataFrame:
    """
    Lee archivo ME5A (SAP) y extrae SOLP + POS, columna B, Material,
    Texto breve, OrgC (país), Mon., Valor total, y todas las columnas
    del formato lineas nuevas.
    
    Returns:
        DataFrame con columnas del formato lineas nuevas.
    """
    rows = []
    with open(filepath, "r", encoding="latin-1") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("*") or "Sol.pedido" in stripped:
                continue
            parts = line.split("\t")
            tabs = [p.strip() for p in parts]
            if len(tabs) < 14:
                continue

            def _g(idx):
                return tabs[idx] if len(tabs) > idx else ""

            solped = _g(2)
            pos = _g(3)
            if not (solped.isdigit() and len(solped) == 10 and pos.isdigit()):
                continue

            b_val = _g(4)
            material = _g(13)
            texto_breve = _g(14)
            orgc = _g(26)
            pais = ORGC_PAIS_MAP.get(orgc, orgc)
            tipo = _clasificar_tipo_compra(material, texto_breve)

            rows.append({
                "Sol.pedido": solped,
                "Pos.": pos,
                "SOLP + POS": solped + pos,
                "B": b_val,
                "eliminada": b_val == "X",
                "Lib": _g(5),
                "Fe.solic.": _g(6),
                "Modif.el": _g(7),
                "Cantidad": _g(8),
                "Mon.": _g(9),
                "Valor total": _g(10),
                "Solicit.": _g(11),
                "GCp": _g(12),
                "Material": material,
                "Texto breve": texto_breve,
                "Pedido": _g(15),
                "Pos._2": _g(16),
                "I": _g(17),
                "P": _g(18),
                "Ce.": _g(19),
                "Autor": _g(20),
                "Pos.presup.": _g(21),
                "Ce.gestor": _g(22),
                "Fondo": _g(23),
                "Ctd.conf.": _g(24),
                "DscrGrCmpr": _g(25),
                "OrgC": orgc,
                "TIPO DE COMPRA": tipo,
                "PAÍS": pais,
            })
    
    df = pd.DataFrame(rows)
    logger.info(f"ME5A leído: {filepath.name} → {len(df)} filas")
    return df


def _clasificar_tipo_compra(material: str, texto_breve: str) -> str:
    """
    Clasifica TIPO DE COMPRA según reglas:
    1. Sin material → SERVICIOS
    2. Texto breve inicia con LICENCIA/LIC/LIC. → LICENCIAS
    3. Texto breve contiene PQUETE + num + LICENCIAS → LICENCIAS
    4. Texto breve inicia con SOFTWARE → SOFTWARE
    5. Texto breve inicia con SOPORTE → SOPORTE
    6. Tiene material y no matchea → HARDWARE
    """
    mat = material.strip()
    txt = texto_breve.strip()
    
    if not mat:
        return "SERVICIOS"
    
    txt_upper = txt.upper()
    
    if txt_upper.startswith("LICENCIA ") or txt_upper.startswith("LIC "):
        return "LICENCIAS"
    
    if txt_upper.startswith("LIC.") and len(txt_upper) > 4 and txt_upper[4] != "":
        return "LICENCIAS"
    
    if "PQUETE" in txt_upper and "LICENCIA" in txt_upper:
        return "LICENCIAS"
    
    if txt_upper.startswith("SOFTWARE"):
        return "SOFTWARE"
    
    if txt_upper.startswith("SOPORTE"):
        return "SOPORTE"
    
    return "HARDWARE"


def build_pospre_map(raw_dir: Path, quitar_pospre: list[str] = None, claves_interes: set = None) -> dict[str, str]:
    """
    Lee los archivos .txt SAP originales y construye un mapa
    SOLP + POS → PosPre. Si se indican POSPRE a quitar, esas
    SOLP + POS no se incluyen en el mapa.
    
    Args:
        raw_dir: carpeta con archivos .txt SAP.
        quitar_pospre: lista de POSPRE a excluir (se elimina la
            SOLP + POS completa del mapa).
        claves_interes: conjunto opcional de SOLP + POS que nos interesan.
            Si se pasa, solo se buscan POSPRE para esas claves (mejor rendimiento).
    
    Returns:
        dict SOLP + POS → PosPre.
    """
    quitar = set(p.strip() for p in (quitar_pospre or []) if p and p.strip())
    pospre_map = {}
    for txt_file in raw_dir.glob("*.txt"):
        try:
            df = read_sap_file(txt_file)
            if "PosPre" not in df.columns or "Nºdoc.ref." not in df.columns:
                continue
            # Misma lógica de columna de posición que clean_solped:
            # priorizar PosRf si existe, si no Pos.
            pos_col = "PosRf" if "PosRf" in df.columns else "Pos." if "Pos." in df.columns else None
            if pos_col is None:
                continue
            ref_series = df["Nºdoc.ref."].astype(str).str.strip()
            pos_series = df[pos_col].astype(str).str.strip()
            pospre_series = df["PosPre"].astype(str).str.strip()
            if claves_interes is not None:
                # Solo construir claves que nos interesan (rendimiento)
                clave = ref_series + pos_series
                mask = clave.isin(claves_interes)
                if not mask.any():
                    continue
                ref_series, pos_series, pospre_series = ref_series[mask], pos_series[mask], pospre_series[mask]
            for r, p, pp in zip(ref_series, pos_series, pospre_series):
                solp_pos = r + p
                if pp in quitar:
                    continue
                pospre_map[solp_pos] = pp
        except Exception:
            continue
    return pospre_map


def filtrar_por_pospre(df: pd.DataFrame, quitar_pospre: list[str]) -> pd.DataFrame:
    """
    Elimina filas del DataFrame cuya POSPRE esté en la lista a quitar.
    
    Si el DataFrame tiene columna 'POSPRE', filtra por ella.
    Si tiene 'PosPre' (de la base SAP), filtra por esa columna.
    Retorna el DataFrame sin las filas cuyas POSPRE estén excluidas.
    """
    quitar = set(p.strip() for p in (quitar_pospre or []) if p and p.strip())
    if not quitar:
        return df
    
    df_out = df.copy()
    if "POSPRE" in df_out.columns:
        pospre_col = "POSPRE"
    elif "PosPre" in df_out.columns:
        pospre_col = "PosPre"
    else:
        pospre_col = None
    
    if pospre_col is not None:
        df_out = df_out[~df_out[pospre_col].astype(str).str.strip().isin(quitar)]
    
    df_out = df_out.reset_index(drop=True)
    logger.info(f"POSPRE quitar: {quitar} → quedan {len(df_out)} filas de {len(df)}")
    return df_out


def _find_header_row(filepath: Path, delimiter: str = "\t", encoding: str = "latin-1", extra_headers: list = None) -> int:
    """Generic header finder for SAP txt files."""
    known_headers = ["PosPre", "Sol.pedido", "Pos.", "OF", "Soc.", "NºDoc.fin.", "Network", "Def.proy."]
    if extra_headers:
        known_headers.extend(extra_headers)
    with open(filepath, "r", encoding=encoding) as f:
        for i, line in enumerate(f):
            tabs = line.count(delimiter)
            if tabs >= 5:
                for header in known_headers:
                    if header in line:
                        return i
    return 0


def _parse_sap_file(filepath: Path, required_cols: list[str]) -> tuple[dict, list[list[str]]]:
    """
    Parser genérico para archivos SAP .txt.
    Retorna (mapa_nombre->índice, filas_de_datos_raw).
    """
    header_found = False
    col_map = {}
    data_rows = []
    
    with open(filepath, "r", encoding="latin-1") as f:
        for line in f:
            stripped = line.strip()
            if not header_found:
                if any(col in stripped for col in required_cols):
                    parts = line.rstrip("\n").split("\t")
                    seen = {}
                    for i, p in enumerate(parts):
                        name = p.strip()
                        if name:
                            if name in seen:
                                seen[name] += 1
                                col_map[f"{name}_{seen[name]}"] = i
                            else:
                                seen[name] = 0
                                col_map[name] = i
                    header_found = True
                continue
            if not stripped or stripped.startswith("*"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) > 2:
                data_rows.append(parts)
    
    return col_map, data_rows


def read_grafos(filepath: Path) -> pd.DataFrame:
    """
    Lee archivo GRAFOS y extrae SOLP+POS, Operacion, Grafo.
    """
    col_map, data = _parse_sap_file(filepath, ["Sol.pedido", "Grafo"])
    
    rows = []
    for r in data:
        solped = r[col_map["Sol.pedido"]].strip() if col_map.get("Sol.pedido") is not None and col_map["Sol.pedido"] < len(r) else ""
        pos = r[col_map["Pos."]].strip() if col_map.get("Pos.") is not None and col_map["Pos."] < len(r) else ""
        operacion = r[col_map["Op."]].strip() if col_map.get("Op.") is not None and col_map["Op."] < len(r) else ""
        grafo = r[col_map["Grafo"]].strip() if col_map.get("Grafo") is not None and col_map["Grafo"] < len(r) else ""
        if solped.isdigit() and pos.isdigit():
            rows.append({
                "SOLP + POS": solped + pos,
                "OPERACION": operacion,
                "GRAFO": grafo,
            })
    
    df = pd.DataFrame(rows)
    logger.info(f"Grafos leído: {filepath.name} → {len(df)} filas")
    return df


def read_peps(filepath: Path) -> pd.DataFrame:
    """
    Lee archivo PEPs y extrae Network, WBS element.
    """
    col_map, data = _parse_sap_file(filepath, ["Network", "WBS element"])
    
    rows = []
    for r in data:
        network = r[col_map["Network"]].strip() if col_map.get("Network") is not None and col_map["Network"] < len(r) else ""
        wbs = r[col_map["WBS element"]].strip() if col_map.get("WBS element") is not None and col_map["WBS element"] < len(r) else ""
        if network.isdigit() and wbs:
            rows.append({
                "GRAFO": network,
                "PEP": wbs,
            })
    
    df = pd.DataFrame(rows)
    logger.info(f"PEPs leído: {filepath.name} → {len(df)} filas")
    return df


def read_sitios(filepath: Path) -> pd.DataFrame:
    """
    Lee archivo SITIOS y extrae WBS element, IO (Us.20car.2), ID (Us.10Car.1).
    """
    col_map, data = _parse_sap_file(filepath, ["WBS element", "Us.20car.2"])
    
    rows = []
    for r in data:
        wbs = r[col_map["WBS element"]].strip() if col_map.get("WBS element") is not None and col_map["WBS element"] < len(r) else ""
        io_val = r[col_map["Us.20car.2"]].strip() if col_map.get("Us.20car.2") is not None and col_map["Us.20car.2"] < len(r) else ""
        id_val = r[col_map["Us.10Car.1"]].strip() if col_map.get("Us.10Car.1") is not None and col_map["Us.10Car.1"] < len(r) else ""
        if wbs:
            rows.append({
                "PEP": wbs,
                "IO": io_val,
                "ID": id_val,
            })
    
    df = pd.DataFrame(rows)
    logger.info(f"Sitios leído: {filepath.name} → {len(df)} filas")
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


def detect_file_type(df: pd.DataFrame) -> str:
    """
    Detecta el tipo de archivo SAP por sus columnas.
    
    Returns:
        Tipo detectado: "solped", "pedido", "oferta", "desconocido"
    """
    cols = set(df.columns)
    
    solped_required = {"PosPre", "Ce.gestor", "Mon.", "Tp.valor"}
    solped_budget = {"Presup.", "Presupuesto"}
    pedido_cols = {"Sol.pedido", "Fe.solic.", "Valor tot. Solicit.", "GCp"}
    oferta_cols = {"OF", "ID", "IO", "CORRELATIVO"}
    
    if solped_required.issubset(cols) and solped_budget.intersection(cols):
        return "solped"
    elif pedido_cols.issubset(cols):
        return "pedido"
    elif oferta_cols.issubset(cols):
        return "oferta"
    else:
        return "desconocido"
