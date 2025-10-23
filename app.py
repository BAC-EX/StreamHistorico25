import streamlit as st
import pandas as pd
import requests
import io
import datetime

# 🧭 Configuración de página
st.set_page_config(page_title="Ejemplo Pandas + Streamlit", page_icon="📊", layout="centered")
st.title("📈 Ejemplo con gestión de memoria optimizada")

# 🧠 Cargar datos una sola vez
@st.cache_data
def load_data():
    url = "https://drive.google.com/uc?export=download&id=1FFvdV6rr5tv2wVuXX4PzEwANx66NsK0O"
    response = requests.get(url)
    df = pd.read_parquet(io.BytesIO(response.content))
    return df

df = load_data()

# Asegurar que las columnas de fecha son datetime
df["Payment date"] = pd.to_datetime(df["Payment date"], errors="coerce")
df["Clearance date"] = pd.to_datetime(df["Clearance date"], errors="coerce")

# 🔹 Filtros (no fecha)
values_business = df["Business"].unique().tolist()
values_decl = df["Declaration number"].unique().tolist()
values_po = df["PO"].unique().tolist()
values_trade = df["Trade Flow"].unique().tolist()

# 🎛️ Selectores Streamlit (no fecha)
f_business = st.multiselect("Business", values_business)
f_decl = st.multiselect("Declaration Number", values_decl)
f_po = st.multiselect("PO", values_po)
f_trade = st.multiselect("Trade Flow", values_trade)

# --- Helpers para filtros de fecha ---
def date_filter_widget(label: str, series: pd.Series):
    """Muestra UI para filtrar una columna de fecha. Devuelve una máscara booleana."""
    series = pd.to_datetime(series, errors="coerce")
    min_date = series.min().date() if series.notna().any() else datetime.date.today()
    max_date = series.max().date() if series.notna().any() else datetime.date.today()

    mode = st.radio(
        f"Filtrar {label} por:",
        ["Multiselección", "Rango de fechas", "Mes", "Año"],
        horizontal=True,
        key=f"{label}_mode"
    )

    mask = pd.Series(True, index=df.index)
    start_date = end_date = None

    if mode == "Multiselección":
        # Mostrar las fechas disponibles como lista de fechas (date objects) para multiselect
        options = sorted(series.dropna().dt.date.unique().tolist())
        sel = st.multiselect(f"{label} (fechas)", options, key=f"{label}_multiselect")
        if sel:
            sel_ts = [pd.Timestamp(d) for d in sel]
            mask &= series.isin(sel_ts)

    elif mode == "Rango de fechas":
        # Mostrar siempre el selector de rango de fechas (sin checkbox)
        range_val = st.date_input(
            f"Selecciona rango de fechas para {label}",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key=f"{label}_range"
        )

        # Evitar ValueError cuando el widget devuelve una sola fecha (usuario aún no seleccionó la segunda)
        if isinstance(range_val, tuple) and len(range_val) == 2:
            start, end = range_val
            # normalizar orden
            if start > end:
                start, end = end, start
            start_date, end_date = start, end
            mask &= (series >= pd.Timestamp(start_date)) & (series <= pd.Timestamp(end_date))
        else:
            st.info("Cargando... termina de seleccionar la segunda fecha para aplicar el filtro")

    elif mode == "Mes":
        years = sorted(series.dropna().dt.year.unique().tolist())
        if not years:
            st.write(f"No hay fechas disponibles en {label}")
        else:
            year_start = st.selectbox("Año inicio", years, key=f"{label}_mes_ys")
            month_start = st.selectbox("Mes inicio", range(1, 13), format_func=lambda x: datetime.date(1900, x, 1).strftime("%B"), key=f"{label}_mes_ms")
            year_end = st.selectbox("Año fin", years, key=f"{label}_mes_ye")
            month_end = st.selectbox("Mes fin", range(1, 13), format_func=lambda x: datetime.date(1900, x, 1).strftime("%B"), key=f"{label}_mes_me")

            start_date = datetime.date(year_start, month_start, 1)
            if month_end == 12:
                end_date = datetime.date(year_end + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.date(year_end, month_end + 1, 1) - datetime.timedelta(days=1)

            mask &= (series >= pd.Timestamp(start_date)) & (series <= pd.Timestamp(end_date))

    elif mode == "Año":
        years = sorted(series.dropna().dt.year.unique().tolist())
        if not years:
            st.write(f"No hay fechas disponibles en {label}")
        else:
            year_start = st.selectbox("Año inicio", years, key=f"{label}_anio_ys")
            year_end = st.selectbox("Año fin", years, key=f"{label}_anio_ye")
            start_date = datetime.date(year_start, 1, 1)
            end_date = datetime.date(year_end, 12, 31)
            mask &= (series >= pd.Timestamp(start_date)) & (series <= pd.Timestamp(end_date))

    if start_date is not None and end_date is not None:
        st.write(f"📅 Rango aplicado en {label}: {start_date} → {end_date}")

    return mask

# 🗓️ Widgets de filtro para Payment date y Clearance date (mejora)
st.markdown("### Filtros por fecha")
mask_payment = date_filter_widget("Payment date", df["Payment date"])
mask_clearance = date_filter_widget("Clearance date", df["Clearance date"])

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

# aplicar máscaras de fecha calculadas por los widgets
mask &= mask_payment
mask &= mask_clearance

df_filtrado = df[mask]

# 📊 Mostrar resultados
st.write(f"Filas mostradas: {len(df_filtrado):,}")
st.dataframe(df_filtrado, use_container_width=True)

# ⚡ Conversión a Excel optimizada
@st.cache_data
def convertir_excel(df: pd.DataFrame) -> bytes:
    """Convierte un DataFrame a Excel de forma eficiente y cacheada."""
    buffer = io.BytesIO()
    # xlsxwriter suele usar menos memoria que openpyxl
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()

# 💾 Crear archivo Excel
excel_bytes = convertir_excel(df_filtrado)

# 📥 Botón de descarga (sin mantener buffer en memoria)
st.download_button(
    label="⬇️ Descargar Excel",
    data=excel_bytes,
    file_name="25historico_filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
del excel_bytes  # libera memoria inmediatamente
