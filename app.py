import streamlit as st
import pandas as pd
import requests
import io
import datetime

# Configuración de página
st._config.set_option("theme.backgroundColor", "#FFFFFF")
logo_vesta = "https://greatplacetoworkcarca.com/wp-content/uploads/2023/11/Logo-Vesta-Customs-Honduras.png"
st.markdown(
    f"""
    <style>
        .top-right-image {{
            position: fixed;
            top: 62px;
            right: 20px;
            width: 120px;  /* Ajusta tamaño */
            z-index: 9999; /* Para que quede encima */
        }}
    </style>
    <img src="{logo_vesta}" class="top-right-image">
    """,
    unsafe_allow_html=True
)
st.set_page_config(page_title="25 + Historico y 25 + Actual", page_icon="📊", layout="centered")
st.title("📈 25 + Historico y 25 + Actual")
st.markdown(
    """
    <style>
    /* Fondo de la sidebar */
    [data-testid="stSidebar"] > div:first-child {
        background-color: #dce3e0 !important;
    }

    /* Texto dentro de la sidebar para asegurar contraste */
    [data-testid="stSidebar"] * {
        color: #000000 !important;
    }

    /* Opcional: ajustar color de inputs/selecciones si hace falta */
    [data-testid="stSidebar"] .stSelectbox, 
    [data-testid="stSidebar"] .stMultiselect,
    [data-testid="stSidebar"] .stDateInput,
    [data-testid="stSidebar"] .stRadio {
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f"""
    <div style="text-align:center;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/CargillLogo.svg/330px-CargillLogo.svg.png"
             width="180">
    </div>
    """,
    unsafe_allow_html=True
)

# ----------------------
# Fuentes de datos
# ----------------------
DATA_SOURCES = {
    "Histórico": "https://drive.google.com/uc?export=download&id=1FFvdV6rr5tv2wVuXX4PzEwANx66NsK0O",
    "Actual": "https://drive.google.com/uc?export=download&id=15FKCKV4nblqnVY-vgYbO7HSPm8BqxMBt"
}

source_choice = st.sidebar.radio("Fuente de datos", list(DATA_SOURCES.keys()), index=0)

# Cargar datos una sola vez, cacheada por URL
@st.cache_data
def load_data(url: str) -> pd.DataFrame:
    """Descarga y detecta automáticamente el formato del archivo (parquet, excel, csv)."""
    response = requests.get(url, stream=True)
    content = response.content
    bio = io.BytesIO(content)

    # Intento 1: parquet
    try:
        bio.seek(0)
        return pd.read_parquet(bio)
    except Exception:
        pass

    # Intento 2: excel
    try:
        bio.seek(0)
        return pd.read_excel(bio)
    except Exception:
        pass

    # Intento 3: csv
    try:
        bio.seek(0)
        return pd.read_csv(bio)
    except Exception:
        pass

    raise ValueError("No se pudo leer el archivo con pandas")

df = load_data(DATA_SOURCES[source_choice])

# Asegurar que las columnas de fecha son datetime (si existen)
if "Payment date" in df.columns:
    df["Payment date"] = pd.to_datetime(df["Payment date"], errors="coerce")
if "Clearance date" in df.columns:
    df["Clearance date"] = pd.to_datetime(df["Clearance date"], errors="coerce")

# Helper para detectar columnas alternativas si fuera necesario (lista de candidatos)
def first_existing_column(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def unique_values_for(df: pd.DataFrame, col_name):
    if col_name and col_name in df.columns:
        vals = df[col_name].dropna().unique().tolist()
        return sorted(vals)
    return []

# --- Helpers para filtros de fecha (misma implementación que en Histórico)
def date_filter_widget(label: str, series: pd.Series, container=st.sidebar):
    """Muestra UI para filtrar una columna de fecha con modos: Multiselección (meses/años) o Rango de fechas."""
    series = pd.to_datetime(series, errors="coerce")
    min_date = series.min().date() if series.notna().any() else datetime.date.today()
    max_date = series.max().date() if series.notna().any() else datetime.date.today()

    mode = container.radio(
        f"Filtrar {label} por:",
        ["Multiselección", "Rango de fechas"],
        horizontal=True,
        key=f"{label}_mode"
    )

    mask = pd.Series(True, index=series.index)
    start_date = end_date = None

    # -----------------------
    # 🔹 Modo 1: Multiselección (Meses y Años)
    # -----------------------
    if mode == "Multiselección":
        months_available = sorted(series.dropna().dt.month.unique().tolist())
        years_available = sorted(series.dropna().dt.year.unique().tolist())

        sel_months = container.multiselect(
            f"Selecciona meses para {label}",
            options=months_available,
            format_func=lambda x: datetime.date(1900, x, 1).strftime("%B"),
            key=f"{label}_multi_month"
        )

        sel_years = container.multiselect(
            f"Selecciona años para {label}",
            options=years_available,
            key=f"{label}_multi_year"
        )

        if sel_months:
            mask &= series.dt.month.isin(sel_months)
        if sel_years:
            mask &= series.dt.year.isin(sel_years)

        if sel_months or sel_years:
            meses_sel = [datetime.date(1900, m, 1).strftime("%B") for m in sel_months] if sel_months else []
            años_sel = [str(y) for y in sel_years] if sel_years else []
            texto = "📅 Filtro aplicado: "
            if meses_sel:
                texto += f"Meses ({', '.join(meses_sel)}) "
            if años_sel:
                texto += f"Años ({', '.join(años_sel)})"
            container.write(texto)
        else:
            container.info("Selecciona uno o varios meses o años para aplicar el filtro.")

    # -----------------------
    # 🔹 Modo 2: Rango de fechas
    # -----------------------
    elif mode == "Rango de fechas":
        range_val = container.date_input(
            f"Selecciona rango de fechas para {label}",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"{label}_range"
        )

        if isinstance(range_val, tuple) and len(range_val) == 2:
            start, end = range_val
            if start > end:
                start, end = end, start
            start_date, end_date = start, end
            mask &= (series >= pd.Timestamp(start_date)) & (series <= pd.Timestamp(end_date))
        else:
            container.info("Selecciona ambas fechas para aplicar el filtro.")

    # Mostrar rango aplicado si aplica
    if start_date is not None and end_date is not None:
        container.write(f"📅 Rango aplicado en {label}: {start_date} → {end_date}")

    return mask

# -------------------------
# Filtros en sidebar según fuente
# -------------------------
st.sidebar.markdown("### Filtros generales")

# Columna principal Business (intentar varias variantes si es necesario)
col_business = first_existing_column(df, ["Business", "business", "BUSINESS"])
values_business = unique_values_for(df, col_business)

# Columnas históricas (mantener para "Histórico")
col_decl = first_existing_column(df, ["Declaration number", "DeclarationNumber", "Declaration", "Declaration No", "Declaration no"])
col_po = first_existing_column(df, ["PO", "Po", "po"])
col_trade = first_existing_column(df, ["Trade Flow", "TradeFlow", "Trade_Flow", "trade flow"])

# Columnas específicas para "Actual"
col_numgestion = first_existing_column(df, ["NumeroGestion", "Numero Gestion", "NúmeroGestion", "Número Gestion", "Numero_gestion"])
col_hojaruta = first_existing_column(df, ["Numero Hoja Ruta", "NumeroHojaRuta", "Hoja Ruta", "HojaRuta", "Numero_Hoja_Ruta"])
col_gestor = first_existing_column(df, ["Gestor", "gestor", "Manager"])

# Mostrar y obtener selecciones según source_choice
# Inicializar todas las variables de filtro como listas vacías
f_business = f_decl = f_po = f_trade = f_numgestion = f_hojaruta = f_gestor = []

# Business siempre disponible (si existe)
if col_business:
    f_business = st.sidebar.multiselect("Business", values_business, key=f"{source_choice}_business")
else:
    st.sidebar.write("Business: columna no encontrada en los datos")

if source_choice == "Histórico":
    # Mantener filtros originales sin cambios
    if col_decl:
        values_decl = unique_values_for(df, col_decl)
        f_decl = st.sidebar.multiselect("Declaration Number", values_decl, key=f"{source_choice}_decl")
    else:
        st.sidebar.write("Declaration Number: columna no encontrada")

    if col_po:
        values_po = unique_values_for(df, col_po)
        f_po = st.sidebar.multiselect("PO", values_po, key=f"{source_choice}_po")
    else:
        st.sidebar.write("PO: columna no encontrada")

    if col_trade:
        values_trade = unique_values_for(df, col_trade)
        f_trade = st.sidebar.multiselect("Trade Flow", values_trade, key=f"{source_choice}_trade")
    else:
        st.sidebar.write("Trade Flow: columna no encontrada")

    # Fechas: Payment date y Clearance date (si existen) — uso el widget completo
    st.sidebar.markdown("### Filtros por fecha")
    mask_payment = date_filter_widget("Payment date", df["Payment date"], container=st.sidebar) if "Payment date" in df.columns else pd.Series(True, index=df.index)
    mask_clearance = date_filter_widget("Clearance date", df["Clearance date"], container=st.sidebar) if "Clearance date" in df.columns else pd.Series(True, index=df.index)

else:
    # Actual: agregar los nuevos filtros solicitados pero SIN filtros de fecha interactivos
    if col_numgestion:
        values_numgestion = unique_values_for(df, col_numgestion)
        f_numgestion = st.sidebar.multiselect("NumeroGestion", values_numgestion, key=f"{source_choice}_numgestion")
    else:
        st.sidebar.write("NumeroGestion: columna no encontrada")

    if col_hojaruta:
        values_hojaruta = unique_values_for(df, col_hojaruta)
        f_hojaruta = st.sidebar.multiselect("Numero Hoja Ruta", values_hojaruta, key=f"{source_choice}_hojaruta")
    else:
        st.sidebar.write("Numero Hoja Ruta: columna no encontrada")

    if col_po:
        values_po = unique_values_for(df, col_po)
        f_po = st.sidebar.multiselect("PO", values_po, key=f"{source_choice}_po")
    else:
        st.sidebar.write("PO: columna no encontrada")

    if col_decl:
        values_decl = unique_values_for(df, col_decl)
        f_decl = st.sidebar.multiselect("Declaration Number", values_decl, key=f"{source_choice}_decl")
    else:
        st.sidebar.write("Declaration Number: columna no encontrada")

    if col_trade:
        values_trade = unique_values_for(df, col_trade)
        f_trade = st.sidebar.multiselect("Trade Flow", values_trade, key=f"{source_choice}_trade")
    else:
        st.sidebar.write("Trade Flow: columna no encontrada")

    if col_gestor:
        values_gestor = unique_values_for(df, col_gestor)
        f_gestor = st.sidebar.multiselect("Especialista", values_gestor, key=f"{source_choice}_gestor")
    else:
        st.sidebar.write("Gestor: columna no encontrada")

    # NO colocar filtros de fecha interactivos en "Actual"
    mask_payment = pd.Series(True, index=df.index)
    mask_clearance = pd.Series(True, index=df.index)

    # Mostrar la última fecha disponible en los datos (para que quede "actualizado hasta")
    # Tomamos la máxima fecha entre todas las columnas datetime que existan
    date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if date_cols:
        overall_max = pd.to_datetime(df[date_cols].max(axis=1, skipna=True).max(), errors="coerce")
        if pd.notna(overall_max):
            pass
        else:
            st.sidebar.write("No se pudo determinar la última fecha disponible")
    else:
        st.sidebar.write("No hay columnas de fecha para determinar última carga")

# 🧮 Filtrado eficiente combinando todo
mask = pd.Series(True, index=df.index)

if f_business and col_business:
    mask &= df[col_business].isin(f_business)
if f_decl and col_decl:
    mask &= df[col_decl].isin(f_decl)
if f_po and col_po:
    mask &= df[col_po].isin(f_po)
if f_trade and col_trade:
    mask &= df[col_trade].isin(f_trade)

# Filtros adicionales para "Actual"
if source_choice == "Actual":
    if f_numgestion and col_numgestion:
        mask &= df[col_numgestion].isin(f_numgestion)
    if f_hojaruta and col_hojaruta:
        mask &= df[col_hojaruta].isin(f_hojaruta)
    if f_gestor and col_gestor:
        mask &= df[col_gestor].isin(f_gestor)

# Aplicar máscaras de fechas
mask &= mask_payment
mask &= mask_clearance

df_filtrado = df[mask]


# 📊 Mostrar resultados
st.write(f"Fuente: {source_choice}")
st.write(f"Filas mostradas: {len(df_filtrado):,}")

if source_choice == "Actual":
    # --- Mostrar última actualización desde la columna 'Actualización'
    if "Actualización" in df.columns:
        last = pd.to_datetime(df.loc[mask, "Actualización"], errors="coerce").max()
        if pd.notna(last):
            st.write(f"🕒 Última actualización: {last.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.write("⚠️ No hay fechas válidas en la columna 'Actualización' para el conjunto filtrado")
    else:
        st.write("⚠️ Columna 'Actualización' no encontrada en los datos")

elif source_choice == "Histórico":
    # --- Mostrar última fecha de pago ---
    if "Payment date" in df_filtrado.columns:
        last_payment = pd.to_datetime(df_filtrado["Payment date"], errors="coerce").max()
        if pd.notna(last_payment):
            st.write(f"🗓️ Última actualización Historico: {last_payment.strftime('%Y-%m-%d')}")
        else:
            st.write("⚠️ No se encontró una fecha válida en 'Payment date'")
    else:
        st.write("⚠️ Columna 'Payment date' no encontrada en los datos")

    # --- Mostrar fecha y hora actual como última actualización ---
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.write(f"🗓️ Última actualización Hoy: {ahora}")

else:
    # En caso de futuras fuentes
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.write(f"🗓️ Última actualización: {ahora}")

st.dataframe(df_filtrado, use_container_width=True)

# ⚡ Conversión a Excel optimizada
@st.cache_data
def convertir_excel(df: pd.DataFrame) -> bytes:
    """Convierte un DataFrame a Excel de forma eficiente y cacheada."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()

# 💾 Crear archivo Excel
excel_bytes = convertir_excel(df_filtrado)

safe_name = source_choice.replace(" ", "_").lower()
# 📥 Botón de descarga (en la página principal)
st.download_button(
    label="⬇️ Descargar Excel",
    data=excel_bytes,
    file_name=f"{safe_name}_filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
del excel_bytes  # libera memoria inmediatamente

