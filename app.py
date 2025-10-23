import streamlit as st
import pandas as pd
import requests
import io
import datetime

# 🧭 Configuración de página
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
    "Actual": "https://drive.google.com/uc?export=download&id=15FKCKV4nblqnVY-vgYbO7HSPm8BqxMBt"  # <- reemplaza aquí
}

source_choice = st.sidebar.radio("Fuente de datos", list(DATA_SOURCES.keys()), index=0)

# 🧠 Cargar datos una sola vez, cacheada por URL
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

    # Intento 3: csv (intentar detectar encoding/sep de forma simple)
    try:
        text = content.decode("utf-8", errors="ignore")
        # prefer comma unless semicolon appears more often
        sep = "," if text.count(",") >= text.count(";") else ";"
        from io import StringIO

        return pd.read_csv(StringIO(text), sep=sep)
    except Exception:
        pass

    # Si ninguno funcionó, mostrar información útil
    ct = response.headers.get("content-type", "")
    raise ValueError(
        f"No se pudo parsear el contenido descargado desde {url}. "
        f"Content-Type: {ct}. Asegúrate de que el enlace apunte directamente a un archivo parquet/xlsx/csv "
        "o usar un enlace de descarga directa (Google Drive puede requerir confirmación de descarga para archivos grandes)."
    )

df = load_data(DATA_SOURCES[source_choice])

# Asegurar que las columnas de fecha son datetime
df["Payment date"] = pd.to_datetime(df["Payment date"], errors="coerce")
df["Clearance date"] = pd.to_datetime(df["Clearance date"], errors="coerce")

# 🔹 Filtros (no fecha) — en sidebar
values_business = df["Business"].unique().tolist()
values_decl = df["Declaration number"].unique().tolist()
values_po = df["PO"].unique().tolist()
values_trade = df["Trade Flow"].unique().tolist()

f_business = st.sidebar.multiselect("Business", values_business, key="business_multiselect")
f_decl = st.sidebar.multiselect("Declaration Number", values_decl, key="decl_multiselect")
f_po = st.sidebar.multiselect("PO", values_po, key="po_multiselect")
f_trade = st.sidebar.multiselect("Trade Flow", values_trade, key="trade_multiselect")

# --- Helpers para filtros de fecha ---
def date_filter_widget(label: str, series: pd.Series, container=st.sidebar):
    """Muestra UI para filtrar una columna de fecha en el container indicado (sidebar por defecto). Devuelve una máscara booleana."""
    series = pd.to_datetime(series, errors="coerce")
    min_date = series.min().date() if series.notna().any() else datetime.date.today()
    max_date = series.max().date() if series.notna().any() else datetime.date.today()

    mode = container.radio(
        f"Filtrar {label} por:",
        ["Multiselección", "Rango de fechas", "Mes", "Año"],
        horizontal=True,
        key=f"{label}_mode"
    )

    mask = pd.Series(True, index=series.index)
    start_date = end_date = None

    if mode == "Multiselección":
        options = sorted(series.dropna().dt.date.unique().tolist())
        sel = container.multiselect(f"{label} (fechas)", options, key=f"{label}_multiselect")
        if sel:
            sel_ts = [pd.Timestamp(d) for d in sel]
            mask &= series.isin(sel_ts)

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
            container.info("Cargando... termina de seleccionar la segunda fecha para aplicar el filtro")

    elif mode == "Mes":
        years = sorted(series.dropna().dt.year.unique().tolist())
        if not years:
            container.write(f"No hay fechas disponibles en {label}")
        else:
            year_start = container.selectbox("Año inicio", years, key=f"{label}_mes_ys")
            month_start = container.selectbox("Mes inicio", range(1, 13), format_func=lambda x: datetime.date(1900, x, 1).strftime("%B"), key=f"{label}_mes_ms")
            year_end = container.selectbox("Año fin", years, key=f"{label}_mes_ye")
            month_end = container.selectbox("Mes fin", range(1, 13), format_func=lambda x: datetime.date(1900, x, 1).strftime("%B"), key=f"{label}_mes_me")

            start_date = datetime.date(year_start, month_start, 1)
            if month_end == 12:
                end_date = datetime.date(year_end + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.date(year_end, month_end + 1, 1) - datetime.timedelta(days=1)

            mask &= (series >= pd.Timestamp(start_date)) & (series <= pd.Timestamp(end_date))

    elif mode == "Año":
        years = sorted(series.dropna().dt.year.unique().tolist())
        if not years:
            container.write(f"No hay fechas disponibles en {label}")
        else:
            year_start = container.selectbox("Año inicio", years, key=f"{label}_anio_ys")
            year_end = container.selectbox("Año fin", years, key=f"{label}_anio_ye")
            start_date = datetime.date(year_start, 1, 1)
            end_date = datetime.date(year_end, 12, 31)
            mask &= (series >= pd.Timestamp(start_date)) & (series <= pd.Timestamp(end_date))

    if start_date is not None and end_date is not None:
        container.write(f"📅 Rango aplicado en {label}: {start_date} → {end_date}")

    return mask

# 🗓️ Widgets de filtro para Payment date y Clearance date en sidebar
st.sidebar.markdown("### Filtros por fecha")
mask_payment = date_filter_widget("Payment date", df["Payment date"], container=st.sidebar)
mask_clearance = date_filter_widget("Clearance date", df["Clearance date"], container=st.sidebar)

# 🧮 Filtrado eficiente combinando todo
mask = pd.Series(True, index=df.index)
if f_business:
    mask &= df["Business"].isin(f_business)
if f_decl:
    mask &= df["Declaration number"].isin(f_decl)
if f_po:
    mask &= df["PO"].isin(f_po)
if f_trade:
    mask &= df["Trade Flow"].isin(f_trade)

mask &= mask_payment
mask &= mask_clearance

df_filtrado = df[mask]

# 📊 Mostrar resultados
st.write(f"Fuente: {source_choice}")
st.write(f"Filas mostradas: {len(df_filtrado):,}")
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

# 📥 Botón de descarga (en la página principal)
st.download_button(
    label="⬇️ Descargar Excel",
    data=excel_bytes,
    file_name="25historico_filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
del excel_bytes  # libera memoria inmediatamente
