"""
Configuración central del Proyecto CENAM.
Define rutas, países, columnas y parámetros del sistema.
"""
from pathlib import Path

# ============================================================
# RUTAS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CONSOLIDATED_DIR = DATA_DIR / "consolidated"
OUTPUT_DIR = DATA_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# ============================================================
# PAÍSES
# ============================================================
PAISES = ["GUATEMALA", "EL SALVADOR", "HONDURAS", "NICARAGUA", "COSTA RICA"]
PAISES_CODIGO = {
    "GUATEMALA": "GT",
    "EL SALVADOR": "SV",
    "HONDURAS": "HN",
    "NICARAGUA": "NI",
    "COSTA RICA": "CR",
}

# ============================================================
# COLUMNAS SAP - SOLPED / PEDIDOS
# ============================================================
COLUMNAS_SOLPED = [
    "PosPre", "Soc.", "NºDoc.fin.", "Nºdoc.ref.", "Pos.", "Nº preced.",
    "Pos.doc.pr", "Ce.gestor", "Presup.", "Mon.", "Presup. MonT",
    "Cl.impte.", "Tp.valor", "Nombre", "Período", "Texto", "CeGe",
    "CódT", "Tp.cambio", "Año", "ref.CP", "Año Ej.", "Referencia",
    "Oper.ref.", "Doc.ref.CP", "Nº doc.FI", "Nºdoc.pag.", "Día cont.",
    "Acreedor", "Operación",
]

COLUMNAS_PEDIDO = [
    "Sol.pedido", "Pos.", "B", "Lib", "Fe.solic.", "Modif.el",
    "Cantidad", "Mon.", "Valor tot. Solicit.", "GCp", "Material",
    "Texto breve", "Pedido", "Pos. I", "P", "Ce. Autor", "Pos.presup.",
    "Ce.gestor", "Fondo", "Ctd.conf.", "DscrGrCmpr", "OrgC",
]

# ============================================================
# COLUMNAS CONSOLIDADO FINAL
# ============================================================
COLUMNAS_CONSOLIDADO = [
    "PEDIDOPOS2", "SOLP", "POS", "AUTORIZADO", "TECNOLOGIA",
    "POSPRE", "PAÍS", "ID", "PROYECTO", "STATUS",
    "STATUS DE PROYECTO", "STATUS CAPEX", "PLAN", "IMPUESTOS",
    "PLANIFICACIÓN", "OFERTA VALIDADA", "TRAMITE ASIGNADO",
    "SOLP EN LIBERACIÓN", "COMPRAS", "COMPROMETIDO",
    "REAL/RECIBIDO", "IMPUESTO", "RETORNO",
    "GTOS. IMPORT. Desglosado", "DISPONIBLE", "REAL",
    "CODIGO I&O", "OFERTA", "TIPO DE CAPEX", "TIPO DE COMPRA",
    "GERENTE", "SUB GERENTE", "UT", "SITIO", "PEP", "GRAFO",
    "OPERACIÓN", "CENTRO", "SOL/PEDIDO", "POS PEDIDO", "POS2",
    "INCOTERM", "PROVEEDOR", "TASA MON/ SOLPED", "MONTO SOLPED",
    "MONTOS SOLPES USD", "MON. PEDIDO", "MONTO PEDIDO",
    "MONTO PEDIDO USD", "CANTIDAD", "CANT/ RECIBIDA",
    "Material", "Texto breve", "EJECUTIVO",
    "FECHA_PLANIFICACIÓN_PIDE_REVISIÓN", "FECHA_OFERTA_APROBADA_SOPORTE",
    "FECHA_OFERTA_ENVIADA_A_CARGA", "FECHA_INICIO_CUTEFLOW",
    "FECHA_LIBERACIÓN_CF_JUAN_DIEGO", "FECHA_LIBERACIÓN_CUTEFLOW",
    "FECHA DE SOLICITUD SISTEMA", "FECHA REAL SOLICITUD",
    "FECHA EN COMPRAS", "FECHA ENTREGA DE PEDIDO", "FECHA FIN",
    "CATEGORÍA", "COMPROMETIDO", "C/O/", "RECIBIDO / DICIEMBRE",
    "CODIGO I&O ORIGINAL", "REASIGNAR", "CORRECCIÓN DE OFERTA",
    "OFERTA VALIDA SIN DOCUMENTOS", "TIEMPO DE CUTEFLOW",
    "TIEMPO VALIDACIÓN CUTEFLOW", "CUTEFLOW EN PROCESO (SOPORTE)",
    "CONTEO DÍAS EN PROCESO DE CARGA", "TIEMPO LIBERACIÓN SOLPED",
    "TIEMPO EN COMPRAS", "TEC", "PORYECTO",
    "DEUDA", "ACEPTACIÓN DE DEUDA", "DEUDA PENDIENTE",
    "CORRELATIVO", "RESPONSABLE DE IMPLEMENTACION", "SUSTENTABILIDAD",
]

# ============================================================
# COLUMNAS OFERTA (para cruces)
# ============================================================
COLUMNAS_OFERTA = [
    "OF", "ID", "IO", "CORRELATIVO", "NOTA", "PDF", "F", "CARGA",
    "ALANCE", "SYS ENV / COMP", "STATUS", "CENAM", "PAIS",
    "ID NOMBRE DE PROYECTO", "OFERTA/ CARGA", "ETAPA",
    "CÓDIGO I&O", "TIPO CAPEX", "CATEGORIA", "TEC", "AÑO CARGA",
    "SUBGERENTE", "PLANIFICACIÓN", "PROVEEDOR", "MONTO OFERTA",
    "TIPO DE COMPRA", "INCOTERM", "FECHA PLANIFICACIÓN PIDE REVISIÓN",
    "FECHA OFERTA APROBADA SOPORTE", "FECHA OFERTA ENVIADA A CARGA",
]

# ============================================================
# MAPEO DE COLUMNAS SAP A CONSOLIDADO
# ============================================================
MAPEO_SOLPED_CONSOLIDADO = {
    "Sol.pedido": "SOLP",
    "Pos.": "POS",
    "Mon.": "MON. PEDIDO",
    "Valor tot. Solicit.": "MONTO PEDIDO",
    "Material": "Material",
    "Texto breve": "Texto breve",
    "Pedido": "PEDIDO POS2",
    "Ce.gestor": "CENTRO",
    "Fe.solic.": "FECHA DE SOLICITUD SISTEMA",
    "Cantidad": "CANTIDAD",
}

# ============================================================
# CENTROS GESTORES POR PAÍS
# ============================================================
CENTROS_GESTORES = {
    "GUATEMALA": ["GT00CAPXRF", "GT02", "GT03"],
    "EL SALVADOR": ["SV01", "SV02"],
    "HONDURAS": ["HN01", "HN02"],
    "NICARAGUA": ["NI01", "NI02"],
    "COSTA RICA": ["CR01", "CR02"],
}

# ============================================================
# STREAMLIT CONFIG
# ============================================================
APP_TITLE = "Sistema de Seguimiento de Proyectos CENAM"
APP_ICON = "📊"
PAGE_LAYOUT = "wide"
