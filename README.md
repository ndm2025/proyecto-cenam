# Proyecto CENAM - Sistema de Seguimiento de Proyectos

Sistema de automatización para el seguimiento de proyectos de la red fija y móvil de Claro en Centroamérica.

## Descripción

Este sistema automatiza la gestión de información de proyectos proveniente de SAP para los países de Guatemala, El Salvador, Honduras, Nicaragua y Costa Rica. Procesa archivos exportados de SAP, los consolida y genera KPIs de avance presupuestario y operativo.

## Tecnologías

| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python 3.10+ |
| Procesamiento | Pandas, openpyxl |
| Frontend | Streamlit |
| Base de datos | SQLite (evolución a PostgreSQL) |
| Nube | AWS S3 (futuro) |

## Estructura del Proyecto

```
PROYECTO CENAM/
├── app.py                    # Aplicación principal Streamlit
├── requirements.txt          # Dependencias
├── config/
│   ├── __init__.py
│   └── settings.py           # Configuración central
├── src/
│   ├── __init__.py
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── sap_processor.py  # Lectura y limpieza de archivos SAP
│   │   ├── consolidator.py   # Consolidación de datos
│   │   └── kpis.py           # Generación de KPIs
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py        # Utilidades generales
│   └── models/               # Modelos de datos (futuro)
├── data/
│   ├── raw/                  # Archivos .txt de SAP
│   ├── processed/            # Archivos procesados
│   ├── consolidated/         # Consolidado unificado
│   └── output/               # Reportes generados
├── tests/                    # Pruebas
├── docs/                     # Documentación
├── scripts/                  # Scripts auxiliares
└── logs/                     # Logs del sistema
```

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

La aplicación estará disponible en `http://localhost:8501`

## Flujo del Sistema

```
Archivos SAP (.txt) → Limpieza/Filtrado → Consolidación → 
Comparación con Planificación → KPIs por país/semana
```

## Países Soportados

- 🇬🇹 Guatemala (GT)
- 🇸🇻 El Salvador (SV)
- 🇭🇳 Honduras (HN)
- 🇳🇮 Nicaragua (NI)
- 🇨🇷 Costa Rica (CR)

## Módulos

### sap_processor.py
- Lectura de archivos .txt de SAP
- Detección automática de tipo de archivo
- Limpieza y transformación de datos
- Eliminación de duplicados

### consolidator.py
- Consolidación de 5 bases en una sola
- Mapeo de columnas SAP a formato estándar
- Comparación con planificación
- Generación de resúmenes

### kpis.py
- KPIs de presupuesto por país
- KPIs de estatus de proyectos
- Análisis de carry over
- Tiempos de proceso de compras
- KPIs semanales
