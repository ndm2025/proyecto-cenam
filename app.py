"""
Sistema de Seguimiento de Proyectos CENAM
Aplicación principal Streamlit
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd

from config.settings import APP_TITLE, APP_ICON, PAGE_LAYOUT, PAISES, RAW_DIR, PROCESSED_DIR
from src.modules.sap_processor import read_sap_file, detect_file_type, clean_solped, clean_pedido, clean_oferta
from src.modules.consolidator import (
    consolidate_countries, compare_with_planning,
    save_consolidated, load_consolidated, get_summary_by_country
)
from src.modules.kpis import (
    calculate_budget_kpis, calculate_status_kpis,
    calculate_budget_comparison, generate_weekly_kpis
)
from src.utils.helpers import format_currency, format_percentage


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout=PAGE_LAYOUT,
)


st.sidebar.title("Navegación")
page = st.sidebar.radio(
    "Ir a:",
    ["Inicio", "Carga de Archivos", "Consolidación", "KPIs", "Reportes"],
)


if page == "Inicio":
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.markdown("---")
    
    st.subheader("Bienvenido al Sistema de Seguimiento de Proyectos")
    st.markdown("""
    Este sistema automatiza la gestión de información de proyectos de la red fija y móvil
    de Claro en Centroamérica (Guatemala, El Salvador, Honduras, Nicaragua y Costa Rica).
    
    **Funcionalidades:**
    - 📥 Carga de archivos SAP (.txt)
    - 🔄 Procesamiento y limpieza de datos
    - 📊 Consolidación de 5 bases en una sola
    - 📈 Generación de KPIs por país y semana
    - 📋 Comparación con planificación
    
    **Países:** Guatemala | El Salvador | Honduras | Nicaragua | Costa Rica
    """)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Países", "5")
    with col2:
        st.metric("Estado", "Operativo")
    with col3:
        st.metric("Versión", "1.0")


elif page == "Carga de Archivos":
    st.title("📥 Carga de Archivos SAP")
    st.markdown("---")
    
    pais_seleccionado = st.selectbox("Seleccionar país:", PAISES)
    
    uploaded_files = st.file_uploader(
        "Subir archivos .txt de SAP",
        type=["txt", "csv"],
        accept_multiple_files=True,
        key=f"uploader_{pais_seleccionado}",
    )
    
    if uploaded_files:
        st.success(f"Archivos cargados: {len(uploaded_files)}")
        
        for file in uploaded_files:
            with st.expander(f"📄 {file.name}"):
                df = read_sap_file(file)
                
                file_type = detect_file_type(file)
                st.info(f"Tipo detectado: **{file_type.upper()}**")
                
                st.dataframe(df.head(20), use_container_width=True)
                
                st.write(f"Filas: {len(df)} | Columnas: {len(df.columns)}")
                
                if file_type == "solped":
                    df_clean = clean_solped(df, pais_seleccionado)
                elif file_type == "pedido":
                    df_clean = clean_pedido(df, pais_seleccionado)
                elif file_type == "oferta":
                    df_clean = clean_oferta(df, pais_seleccionado)
                else:
                    df_clean = df
                
                save_path = PROCESSED_DIR / f"{pais_seleccionado}_{file_type}_{file.name}"
                df_clean.to_csv(save_path, index=False, encoding="utf-8-sig")
                st.success(f"Guardado: {save_path.name}")


elif page == "Consolidación":
    st.title("🔄 Consolidación de Datos")
    st.markdown("---")
    
    if st.button("Consolidar todos los países"):
        with st.spinner("Consolidando..."):
            dfs_by_country = {}
            for pais in PAISES:
                files = list(PROCESSED_DIR.glob(f"{pais}_*.csv"))
                if files:
                    dfs = [pd.read_csv(f, dtype=str) for f in files]
                    dfs_by_country[pais] = pd.concat(dfs, ignore_index=True)
            
            if dfs_by_country:
                consolidated = consolidate_countries(dfs_by_country)
                save_path = save_consolidated(consolidated)
                st.success(f"Consolidado guardado: {save_path}")
                
                summary = get_summary_by_country(consolidated)
                st.subheader("Resumen por País")
                st.dataframe(summary, use_container_width=True)
            else:
                st.warning("No hay archivos procesados para consolidar.")
    
    existing = load_consolidated()
    if existing is not None:
        st.subheader("Consolidado Actual")
        st.dataframe(existing.head(50), use_container_width=True)
        st.write(f"Total: {len(existing)} filas")


elif page == "KPIs":
    st.title("📈 KPIs de Proyectos")
    st.markdown("---")
    
    consolidated = load_consolidated()
    
    if consolidated is not None:
        tab1, tab2, tab3, tab4 = st.tabs(["Presupuesto", "Estatus", "Comparativa", "Semanal"])
        
        with tab1:
            st.subheader("KPIs de Presupuesto")
            budget_kpis = calculate_budget_kpis(consolidated)
            st.dataframe(budget_kpis, use_container_width=True)
        
        with tab2:
            st.subheader("KPIs de Estatus")
            status_kpis = calculate_status_kpis(consolidated)
            st.dataframe(status_kpis, use_container_width=True)
        
        with tab3:
            st.subheader("Comparativa Presupuesto Real vs Planificado")
            comparison = calculate_budget_comparison(consolidated)
            st.dataframe(comparison, use_container_width=True)
        
        with tab4:
            st.subheader("KPIs Semanales")
            weekly = generate_weekly_kpis(consolidated)
            if not weekly.empty:
                st.dataframe(weekly, use_container_width=True)
            else:
                st.info("No hay datos con fechas para generar KPIs semanales.")
    else:
        st.warning("No hay consolidado disponible. Ejecute la consolidación primero.")


elif page == "Reportes":
    st.title("📋 Reportes")
    st.markdown("---")
    
    consolidated = load_consolidated()
    
    if consolidated is not None:
        st.subheader("Filtros")
        
        col1, col2 = st.columns(2)
        with col1:
            pais_filtro = st.multiselect("País:", PAISES, default=PAISES)
        with col2:
            if "STATUS" in consolidated.columns:
                status_filtro = st.multiselect(
                    "Estatus:",
                    consolidated["STATUS"].unique().tolist()
                )
            else:
                status_filtro = []
        
        filtered = consolidated.copy()
        if pais_filtro:
            filtered = filtered[filtered["PAÍS"].isin(pais_filtro)]
        if status_filtro:
            filtered = filtered[filtered["STATUS"].isin(status_filtro)]
        
        st.write(f"Mostrando {len(filtered)} de {len(consolidated)} registros")
        st.dataframe(filtered, use_container_width=True)
        
        csv = filtered.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "Descargar CSV",
            csv,
            "reporte_filtrado.csv",
            "text/csv",
        )
    else:
        st.warning("No hay datos disponibles para generar reportes.")
