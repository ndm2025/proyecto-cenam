"""
Sistema de Seguimiento de Proyectos CENAM
Aplicación principal Streamlit
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd
import importlib
import io
import src.modules.sap_processor as sap_mod
importlib.reload(sap_mod)
from src.modules.sap_processor import read_sap_file, detect_file_type, clean_solped, clean_pedido, clean_oferta, read_me5a, build_pospre_map, filtrar_por_pospre, read_grafos, read_peps, read_sitios

from config.settings import APP_TITLE, APP_ICON, PAGE_LAYOUT, PAISES, RAW_DIR, PROCESSED_DIR
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

USUARIOS = {
    "norma": "claro2026",
    "admin": "cenam2026",
    "usuario1": "cenam123",
}

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = ""

if not st.session_state["autenticado"]:
    st.title("🔐 Acceso al Sistema")
    st.subheader("Seguimiento de Proyectos CENAM")
    st.markdown("---")
    
    with st.form("login"):
        usuario = st.text_input("Usuario")
        contrasena = st.text_input("Contraseña", type="password")
        enviado = st.form_submit_button("Ingresar")
        
        if enviado:
            if usuario in USUARIOS and USUARIOS[usuario] == contrasena:
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = usuario
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    
    st.stop()


def _pospre_cache_context() -> tuple:
    """Clave basada en los archivos .txt actuales para invalidar la caché de POSPRE."""
    if RAW_DIR.exists():
        infos = []
        for f in RAW_DIR.glob("*.txt"):
            try:
                infos.append((f.name, f.stat().st_size, f.stat().st_mtime_ns))
            except OSError:
                pass
        return tuple(infos)
    return ()


def _get_pospre_map(claves: set, quitar_pospre: list) -> dict:
    """Devuelve el mapa SOLP+POS → PosPre, cacheado en session_state.

    Se recalcula solo si cambian los archivos .txt o la lista de POSPRE a quitar.
    """
    ctx = (_pospre_cache_context(), tuple(sorted(quitar_pospre or [])))
    cache_claves = st.session_state.get("_pospre_cache_claves", None)
    cached = st.session_state.get("_pospre_cached_map", None)

    if cache_claves == ctx and cached is not None:
        # Reutilizar el mapa completo cacheado, solo filtrar por claves de interés
        return {k: cached[k] for k in set(claves).intersection(cached)}

    mapa = build_pospre_map(RAW_DIR, quitar_pospre)
    st.session_state["_pospre_cached_map"] = mapa
    st.session_state["_pospre_cache_claves"] = ctx
    return {k: mapa[k] for k in set(claves).intersection(mapa)}


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
    st.caption("Sube todos los archivos .txt de SAP (un archivo por país). "
               "El país se detecta automáticamente desde la columna Soc. de cada archivo.")
    
    quitar_pospre_input = st.text_area(
        "Quitar POSPRE de base",
        help="Escribe una o varias POSPRE (separadas por coma o salto de línea) "
             "que NO se tomarán en cuenta en ningún proceso. Cada una empieza con el "
             "código de su país (GT-, HN-, NI-, CR-, SV-). Las solp+pos con esas "
             "POSPRE se excluyen de toda la base, sin importar el país.",
        placeholder="Ej: GT-RM-TR-IPA\nSV-RM-TR-CORE\nHN-RM-RI-GRI",
        key="quitar_pospre_global",
    )
    quitar_pospre = [p.strip() for p in quitar_pospre_input.replace(",", "\n").splitlines() if p.strip()]
    
    uploaded_files = st.file_uploader(
        "Subir archivos .txt de SAP",
        type=["txt", "csv"],
        accept_multiple_files=True,
        key="uploader_sap_global",
    )
    
    all_clean = []
    if uploaded_files:
        st.success(f"Archivos cargados: {len(uploaded_files)}")
        st.caption(f"POSPRE a quitar: {', '.join(quitar_pospre) if quitar_pospre else 'Ninguna'}")
        
        for file in uploaded_files:
            temp_path = RAW_DIR / file.name
            with open(temp_path, "wb") as f:
                f.write(file.getbuffer())
            
            df = read_sap_file(temp_path)
            file_type = detect_file_type(df)
            
            if file_type == "solped":
                try:
                    df_clean, msg = clean_solped(df, "")
                except Exception as e:
                    st.error(f"Error en clean_solped: {type(e).__name__}: {e}")
                    st.stop()
                if df_clean.empty:
                    st.warning(msg)
                else:
                    if quitar_pospre:
                        df_clean = filtrar_por_pospre(df_clean, quitar_pospre)
                    st.success(msg)
                    pais_det = df_clean["PAÍS"].astype(str).str.strip().iloc[0] if "PAÍS" in df_clean.columns and not df_clean.empty else ""
                    save_path = PROCESSED_DIR / f"{pais_det}_{file.name.replace('.txt', '.csv')}"
                    df_clean.to_csv(save_path, index=False, encoding="utf-8-sig")
                    cols_mostrar = ["SOLP + POS", "Nºdoc.ref.", "Pos.", "PosPre", "Cl.impte.", "Tp.valor", "PAÍS"]
                    cols_show = [c for c in cols_mostrar if c in df_clean.columns]
                    st.dataframe(df_clean[cols_show], use_container_width=True)
                    all_clean.append(df_clean)
            else:
                st.info(f"Tipo detectado: {file_type.upper()} — se procesarán más adelante")
    
    if all_clean:
        st.session_state["solped_nuevas"] = pd.concat(all_clean, ignore_index=True)
    st.session_state["quitar_pospre"] = quitar_pospre
    st.session_state["quitar_pospre_input"] = quitar_pospre_input
    
    st.markdown("---")
    st.subheader("🔍 Comparar con Consolidado")
    
    uploaded_excel = st.file_uploader(
        "Subir consolidado Excel (.xlsb)",
        type=["xlsb"],
        key="uploader_consolidado",
    )
    
    if uploaded_excel and "solped_nuevas" in st.session_state:
        temp_excel = RAW_DIR / uploaded_excel.name
        with open(temp_excel, "wb") as f:
            f.write(uploaded_excel.getbuffer())
        
        try:
            df_consolidado = pd.read_excel(temp_excel, sheet_name="CENAM", engine="pyxlsb")
            col_key = "solp + pos"
            if col_key not in df_consolidado.columns:
                st.error(f"Columna '{col_key}' no encontrada en hoja CENAM. Columnas: {list(df_consolidado.columns[:5])}")
            else:
                consolidado_keys = set(df_consolidado[col_key].astype(str).str.strip())
                solped_nuevas = st.session_state["solped_nuevas"].copy()
                
                # Detectar y separar solp+pos duplicadas en las bases.
                # Si una solp+pos aparece 2+ veces, se conserva solo 1 original
                # y las demás (extras) se descartan para contar únicas.
                solp_col = "SOLP + POS"
                dup_mask = solped_nuevas[solp_col].duplicated(keep=False)
                solped_repetidas = solped_nuevas[dup_mask].copy()
                solped_duplicadas = solped_repetidas.drop_duplicates(subset=[solp_col], keep="first")
                # Conservar siempre una original de cada solp+pos
                solped_unicas = solped_nuevas.drop_duplicates(subset=[solp_col], keep="first").copy()
                
                # Contar únicas (como en Excel, sin duplicados)
                mask_en_consolidado = solped_unicas[solp_col].isin(consolidado_keys)
                nuevas = solped_unicas[~mask_en_consolidado]
                
                df_elim = pd.read_excel(temp_excel, sheet_name="Eliminadas", engine="pyxlsb")
                col_elim = df_elim.iloc[:, 1]
                eliminadas_vals = col_elim.dropna()
                eliminadas_vals = eliminadas_vals[pd.to_numeric(eliminadas_vals, errors="coerce").notna()]
                eliminadas_keys = set(eliminadas_vals.astype(int).astype(str))
                
                mask_en_elim = nuevas["Nºdoc.ref."].astype(str).str.strip().isin(eliminadas_keys)
                despues_elim = nuevas[~mask_en_elim]
                eliminadas_encontradas = nuevas[mask_en_elim]
                
                df_entrada = pd.read_excel(temp_excel, sheet_name="ENTRADA FINAL", engine="pyxlsb")
                col_entrada = df_entrada.iloc[:, 2]
                entrada_vals = col_entrada.dropna()
                entrada_vals = entrada_vals[pd.to_numeric(entrada_vals, errors="coerce").notna()]
                entrada_keys = set(entrada_vals.astype(int).astype(str))
                
                mask_en_entrada = despues_elim[solp_col].astype(str).str.strip().isin(entrada_keys)
                filtradas = despues_elim[~mask_en_entrada]
                entrada_encontradas = despues_elim[mask_en_entrada]
                
                st.markdown("### Resultado")
                col_a, col_b, col_c, col_d, col_e = st.columns(5)
                col_a.metric("Solped totales de Bases", len(solped_unicas))
                col_b.metric("Solped que estan cenam", int(mask_en_consolidado.sum()))
                col_c.metric("En Eliminadas", len(eliminadas_encontradas))
                col_d.metric("En Entrada Final", len(entrada_encontradas))
                col_e.metric("Solped que No estan en cenam", len(filtradas))
                
                if not solped_duplicadas.empty:
                    st.warning(f"Se encontraron {solped_duplicadas[solp_col].nunique()} solp+pos duplicadas en las bases (contadas como únicas).")
                    with st.expander("Ver solp+pos duplicadas en bases"):
                        st.dataframe(
                            solped_duplicadas[[c for c in ["SOLP + POS", "Nºdoc.ref.", "Pos.", "PAÍS"] if c in solped_duplicadas.columns]]
                            .drop_duplicates(subset=[solp_col]),
                            use_container_width=True,
                        )
                
                if not filtradas.empty:
                    st.success(f"Solped nuevas para agregar: {len(filtradas)}")
                    st.session_state["solped_no_cenam"] = filtradas[["SOLP + POS"]].copy()
                    cols_show = [c for c in ["SOLP + POS", "Nºdoc.ref.", "Pos.", "PAÍS"] if c in filtradas.columns]
                    st.dataframe(filtradas[cols_show], use_container_width=True)
                else:
                    st.info("No quedan solped nuevas")
        except Exception as e:
            st.error(f"Error leyendo consolidado: {type(e).__name__}: {e}")
    
    st.markdown("---")
    st.subheader("📋 Filtro ME5A")
    
    uploaded_me5a = st.file_uploader(
        "Subir base ME5A (.txt)",
        type=["txt"],
        key="uploader_me5a",
    )
    
    if uploaded_me5a and "solped_nuevas" in st.session_state:
        temp_me5a = RAW_DIR / uploaded_me5a.name
        with open(temp_me5a, "wb") as f:
            f.write(uploaded_me5a.getbuffer())
        
        try:
            df_me5a = read_me5a(temp_me5a)
            st.info(f"ME5A: {len(df_me5a)} solp+pos leídas")
            
            df_me5a_filtered = df_me5a[~df_me5a["eliminada"]]
            eliminadas_b = df_me5a[df_me5a["eliminada"]]
            total_me5a_filtered = len(df_me5a_filtered)
            
            # Si ya se calculó "Solped que No estan en cenam" en Comparar con
            # Consolidado, usar SOLO esas solp+pos y descartar el resto de la base.
            no_cenam_frame = st.session_state.get("solped_no_cenam")
            if no_cenam_frame is not None and not no_cenam_frame.empty:
                no_cenam_keys = set(no_cenam_frame["SOLP + POS"].astype(str).str.strip())
                descartadas = df_me5a_filtered[~df_me5a_filtered["SOLP + POS"].astype(str).str.strip().isin(no_cenam_keys)]
                df_me5a_filtered = df_me5a_filtered[df_me5a_filtered["SOLP + POS"].astype(str).str.strip().isin(no_cenam_keys)].copy()
                me5a_nuevas = df_me5a_filtered
                en_cenam = set()
            elif uploaded_excel:
                temp_excel = RAW_DIR / uploaded_excel.name
                df_cenam = pd.read_excel(temp_excel, sheet_name="CENAM", engine="pyxlsb")
                cenam_keys = set(df_cenam["solp + pos"].astype(str).str.strip())
                
                me5a_keys = set(df_me5a_filtered["SOLP + POS"])
                en_cenam = me5a_keys.intersection(cenam_keys)
                me5a_nuevas = df_me5a_filtered[~df_me5a_filtered["SOLP + POS"].isin(cenam_keys)]
            else:
                me5a_nuevas = df_me5a_filtered
                en_cenam = set()
            
            st.markdown("### Resultado ME5A")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total ME5A", len(df_me5a))
            col2.metric("Borradas (B=X)", len(eliminadas_b))
            if no_cenam_frame is not None and not no_cenam_frame.empty:
                col3.metric("Descarte (no en 'No estan cenam')", len(descartadas))
                col4.metric("ME5A que se usan", len(me5a_nuevas))
            else:
                col3.metric("En CENAM", len(en_cenam))
            
            if not me5a_nuevas.empty:
                quitar_pospre = st.session_state.get("quitar_pospre", [])
                claves_interes = set(me5a_nuevas["SOLP + POS"].astype(str).str.strip())
                pospre_map = _get_pospre_map(claves_interes, quitar_pospre)
                me5a_nuevas = me5a_nuevas.copy()
                me5a_nuevas["POSPRE"] = me5a_nuevas["SOLP + POS"].map(pospre_map).fillna("")
                if quitar_pospre:
                    me5a_nuevas = filtrar_por_pospre(me5a_nuevas, quitar_pospre)
                st.session_state["me5a_nuevas"] = me5a_nuevas
                
                cols_show = [c for c in ["SOLP + POS", "Sol.pedido", "Pos.", "B", "Mon.", "Valor total", "Material", "Texto breve", "TIPO DE COMPRA", "OrgC", "PAÍS", "POSPRE"] if c in me5a_nuevas.columns]
                st.dataframe(me5a_nuevas[cols_show], use_container_width=True)
            else:
                st.info("No quedan solp+pos nuevas en ME5A")
        except Exception as e:
            st.error(f"Error procesando ME5A: {type(e).__name__}: {e}")
    
    st.markdown("---")
    st.subheader("🌿 Líneas Verdes")
    
    col_g, col_p, col_s = st.columns(3)
    with col_g:
        up_grafos = st.file_uploader("GRAFOS (.txt)", type=["txt"], key="up_grafos")
    with col_p:
        up_peps = st.file_uploader("PEPs (.txt)", type=["txt"], key="up_peps")
    with col_s:
        up_sitios = st.file_uploader("SITIOS (.txt)", type=["txt"], key="up_sitios")
    
    if up_grafos and up_peps and up_sitios:
        try:
            p_grafos = RAW_DIR / up_grafos.name
            p_peps = RAW_DIR / up_peps.name
            p_sitios = RAW_DIR / up_sitios.name
            for up, p in [(up_grafos, p_grafos), (up_peps, p_peps), (up_sitios, p_sitios)]:
                with open(p, "wb") as f:
                    f.write(up.getbuffer())
            
            df_grafos = read_grafos(p_grafos)
            df_peps = read_peps(p_peps)
            df_sitios = read_sitios(p_sitios)
            
            st.info(f"Grafos: {len(df_grafos)} | PEPs: {len(df_peps)} | Sitios: {len(df_sitios)}")
            
            if "me5a_nuevas" in st.session_state:
                me5a_data = st.session_state["me5a_nuevas"].copy()
            else:
                st.warning("Primero carga la base ME5A para filtrar las solped nuevas")
                st.stop()
            
            quitar_pospre = st.session_state.get("quitar_pospre", [])
            if quitar_pospre:
                me5a_data = filtrar_por_pospre(me5a_data, quitar_pospre)
            
            # Encadenamiento progresivo partiendo de Resultados ME5A.
            # Paso 1: buscar en GRAFOS la OPERACION y GRAFO de cada solp de ME5A.
            # Los GRAFOS cuyas solp+pos no están en ME5A se descartan.
            me5a_solps = set(me5a_data["SOLP + POS"].astype(str).str.strip())
            grafos_con_solp = df_grafos[df_grafos["SOLP + POS"].astype(str).str.strip().isin(me5a_solps)]
            grafos_descartados = len(df_grafos) - len(grafos_con_solp)
            me5a_data = me5a_data.merge(grafos_con_solp[["SOLP + POS", "OPERACION", "GRAFO"]], on="SOLP + POS", how="left")
            
            # Paso 2: usar SOLO los GRAFO obtenidos para buscar el PEP en PEPS.
            grafos_encontrados = set(grafos_con_solp["GRAFO"].astype(str).str.strip())
            peps_con_grafo = df_peps[df_peps["GRAFO"].astype(str).str.strip().isin(grafos_encontrados)]
            peps_descartados = len(df_peps) - len(peps_con_grafo)
            me5a_data = me5a_data.merge(peps_con_grafo[["GRAFO", "PEP"]], on="GRAFO", how="left")
            
            # Paso 3: usar SOLO los PEP obtenidos para buscar IO e ID en SITIOS.
            peps_encontrados = set(peps_con_grafo["PEP"].astype(str).str.strip())
            sitios_con_pep = df_sitios[df_sitios["PEP"].astype(str).str.strip().isin(peps_encontrados)]
            sitios_descartados = len(df_sitios) - len(sitios_con_pep)
            me5a_data = me5a_data.merge(sitios_con_pep[["PEP", "IO", "ID"]], on="PEP", how="left")
            
            match_grafos = me5a_data["GRAFO"].notna().sum()
            match_peps = me5a_data["PEP"].notna().sum()
            match_io = me5a_data["IO"].notna().sum()
            
            st.markdown("### Resultado Líneas Verdes")
            st.caption("Partiendo de los Resultados ME5A, se encadena: GRAFOS → PEPS → SITIOS. Los registros de estas bases cuyo vínculo no esté en las solp+pos de ME5A se descartan.")
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("Grafos descartados", grafos_descartados, help="GRAFOS cuyas solp+pos no están en Resultados ME5A")
            col2.metric("PEPs descartados", peps_descartados, help="PEPS cuyos GRAFO no se obtuvieron de ME5A")
            col3.metric("Sitios descartados", sitios_descartados, help="SITIOS cuyos PEP no se obtuvieron de los GRAFO")
            col4.metric("Con GRAFO", f"{match_grafos}/{len(me5a_data)}")
            col5.metric("Con PEP", f"{match_peps}/{len(me5a_data)}")
            col6.metric("Con IO/ID", f"{match_io}/{len(me5a_data)}")
            
            cols_show = [c for c in ["SOLP + POS", "PAÍS", "ID", "IO", "PEP", "GRAFO", "OPERACION", "B", "Mon.", "Valor total", "Material", "Texto breve", "POSPRE"] if c in me5a_data.columns]
            st.dataframe(me5a_data[cols_show], use_container_width=True)
            
            FORMAT_COLUMNS = [
                "Sol.pedidoPos.", "PAÍS", "ID", "IO", "OFERTA", "UT", "SITIO", "PEP",
                "GRAFO", "OPERACIÓN", "CENTRO", "Sol.pedido", "Pos.", "B", "Lib",
                "Fe.solic.", "Modif.el", "Cantidad", "Mon.", "Valor total", "Solicit.",
                "GCp", "Material", "Texto breve", "Pedido", "Pos._2", "I", "P", "Ce.",
                "Autor", "Pos.presup.", "Ce.gestor", "Fondo", "Ctd.conf.", "DscrGrCmpr",
                "OrgC", "POSPRE", "CORRELATIVO", "TIPO DE COMPRA", "COMENTARIOS", "OFERTAIDIO",
            ]
            ME5A_TO_FORMAT = {
                "SOLP + POS": "Sol.pedidoPos.", "PAÍS": "PAÍS", "ID": "ID", "IO": "IO",
                "PEP": "PEP", "GRAFO": "GRAFO", "OPERACION": "OPERACIÓN",
                "B": "B", "Mon.": "Mon.", "Valor total": "Valor total",
                "Material": "Material", "Texto breve": "Texto breve",
                "Sol.pedido": "Sol.pedido", "Pos.": "Pos.", "Lib": "Lib",
                "Fe.solic.": "Fe.solic.", "Modif.el": "Modif.el", "Cantidad": "Cantidad",
                "Solicit.": "Solicit.", "GCp": "GCp", "Pedido": "Pedido",
                "Pos._2": "Pos._2", "I": "I", "P": "P", "Ce.": "Ce.",
                "Autor": "Autor", "Pos.presup.": "Pos.presup.", "Ce.gestor": "Ce.gestor",
                "Fondo": "Fondo", "Ctd.conf.": "Ctd.conf.", "DscrGrCmpr": "DscrGrCmpr",
                "OrgC": "OrgC", "POSPRE": "POSPRE", "TIPO DE COMPRA": "TIPO DE COMPRA",
            }
            
            st.markdown("---")
            if st.button("Descargar Excel Formato Líneas Nuevas"):
                export_df = pd.DataFrame(columns=FORMAT_COLUMNS)
                for _, row in me5a_data.iterrows():
                    new_row = {}
                    for src_col, fmt_col in ME5A_TO_FORMAT.items():
                        if src_col in row.index:
                            val = row[src_col]
                            new_row[fmt_col] = "" if pd.isna(val) else val
                    export_df = pd.concat([export_df, pd.DataFrame([new_row])], ignore_index=True)
                
                export_df = export_df.fillna("")
                
                PAIS_SHORT = {
                    "GUATEMALA": "GT", "EL SALVADOR": "SV", "HONDURAS": "HN",
                    "NICARAGUA": "NI", "COSTA RICA": "CR",
                }
                if "PAÍS" in export_df.columns:
                    export_df["PAÍS"] = export_df["PAÍS"].map(lambda x: PAIS_SHORT.get(str(x).upper(), x))
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    export_df.to_excel(writer, sheet_name="Hoja1", index=False)
                    ws = writer.sheets["Hoja1"]
                    for i, col in enumerate(export_df.columns):
                        col_data = export_df[col].astype(str)
                        max_len = max(col_data.map(len).max(), len(str(col))) + 2
                        ws.set_column(i, i, min(max_len, 30))
                
                st.download_button(
                    label="Descargar",
                    data=buffer.getvalue(),
                    file_name="lineas_nuevas.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except Exception as e:
            st.error(f"Error en Líneas Verdes: {type(e).__name__}: {e}")


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
