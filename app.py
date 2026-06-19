import io
from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Torre de Control COPEC", page_icon="🚦", layout="wide", initial_sidebar_state="expanded")

FECHA_MINIMA_DEFAULT = pd.Timestamp("2026-01-01")
CUMPL_COL = "Conductor se detine mínimo 15 minutos"

COLOR_SEQUENCE=["#2563EB","#0EA5E9","#16A34A","#D97706","#DC2626","#7C3AED","#0891B2","#475569"]

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:linear-gradient(135deg,#020617,#0f172a);}
[data-testid="stHeader"]{background:rgba(2,6,23,0);}
.block-container{padding-top:1.8rem;padding-bottom:2rem;}
[data-testid="stSidebar"]{background:#F1F5F9!important;}
[data-testid="stSidebar"] *{color:#0F172A!important;}
h1,h2,h3,h4,p,label,span,div{color:#f8fafc;}
.metric-card{background:rgba(17,24,39,.95);border:1px solid #334155;border-radius:18px;padding:18px;min-height:105px;box-shadow:0 12px 30px rgba(0,0,0,.22);}
.metric-label{color:#94a3b8;font-size:13px;margin-bottom:8px;}
.metric-value{font-size:28px;font-weight:800;color:#f8fafc;}
.metric-note{color:#94a3b8;font-size:12px;margin-top:4px;}
.risk-alto,.risk-medio,.risk-bajo{padding:8px 12px;border-radius:999px;font-weight:800;display:inline-block;}
.risk-alto{background:rgba(239,68,68,.18);border:1px solid rgba(239,68,68,.45);color:#fecaca;}
.risk-medio{background:rgba(245,158,11,.18);border:1px solid rgba(245,158,11,.45);color:#fde68a;}
.risk-bajo{background:rgba(34,197,94,.18);border:1px solid rgba(34,197,94,.45);color:#bbf7d0;}
.period-card{background:rgba(14,165,233,.12);border:1px solid rgba(14,165,233,.45);border-radius:14px;padding:12px 16px;margin:10px 0 16px 0;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300, show_spinner=False)
def load_google_sheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(credentials)
    spreadsheet_id = st.secrets["google_sheet"]["spreadsheet_id"]
    guardian_ws = st.secrets["google_sheet"].get("guardian_worksheet_name", "GUARDIAN")
    flotago_ws = st.secrets["google_sheet"].get("flotago_worksheet_name", "FLOTAGO")
    sheet = client.open_by_key(spreadsheet_id)
    dfs = []
    for platform, ws_name in [("Guardian", guardian_ws), ("FlotaGo", flotago_ws)]:
        try:
            ws = sheet.worksheet(ws_name)
            temp = pd.DataFrame(ws.get_all_records())
            if not temp.empty:
                temp["Plataforma"] = platform
                dfs.append(temp)
        except Exception as exc:
            st.warning(f"No pude leer la hoja '{ws_name}'. Revisa el nombre en Secrets. Detalle: {exc}")
    if not dfs:
        st.error("No se pudo cargar GUARDIAN ni FLOTAGO/FlotaGo.")
        st.stop()
    return pd.concat(dfs, ignore_index=True, sort=False)

def normalize_data(df):
    df = df.copy()
    if "Fecha" not in df.columns:
        st.error("La base no contiene la columna 'Fecha'.")
        st.stop()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
    df = df[df["Fecha"].notna()].copy()
    df = df[df["Fecha"] >= FECHA_MINIMA_DEFAULT].copy()
    for col in ["Plataforma", "Transportista", "Conductor", "Incidente", "Planta", "Patente"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["Plataforma"] = df["Plataforma"].replace("", "SIN PLATAFORMA")
    df["Transportista"] = df["Transportista"].replace("", "SIN TRANSPORTISTA IDENTIFICADO")
    df["Conductor"] = df["Conductor"].replace("", "SIN CONDUCTOR")
    df["Incidente"] = df["Incidente"].replace("", "SIN CLASIFICAR")
    df["Planta"] = df["Planta"].replace("", "SIN PLANTA")
    df["Patente"] = df["Patente"].replace("", "SIN PATENTE")
    if CUMPL_COL not in df.columns:
        df[CUMPL_COL] = ""
    df[CUMPL_COL] = df[CUMPL_COL].fillna("").astype(str).str.strip().str.upper().replace({"SÍ":"SI","SI.":"SI","NO.":"NO"})
    df["EsFatiga"] = df["Incidente"].str.contains("fatiga|cansancio|somnolencia", case=False, na=False)
    df["FechaDia"] = df["Fecha"].dt.date
    return df

def risk_score(data):
    if data.empty:
        return 0
    fatigue = data[data["EsFatiga"]]
    no_cumple = int((fatigue[CUMPL_COL] == "NO").sum())
    total = len(data)
    fatigue_events = len(fatigue)
    unique_drivers = data["Conductor"].replace("", pd.NA).dropna().nunique()
    total_component = min(total / 300, 1) * 25
    fatigue_component = min(fatigue_events / 15, 1) * 25
    non_compliance_component = min(no_cumple / 8, 1) * 35
    concentration_component = 0
    if unique_drivers > 0:
        concentration_component = min(data["Conductor"].value_counts(normalize=True).iloc[0] / 0.35, 1) * 15
    return round(total_component + fatigue_component + non_compliance_component + concentration_component)

def risk_level(score):
    if score >= 70:
        return "ALTO", "risk-alto"
    if score >= 40:
        return "MEDIO", "risk-medio"
    return "BAJO", "risk-bajo"

def metric_card(label, value, note=""):
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      <div class="metric-note">{note}</div>
    </div>
    """, unsafe_allow_html=True)

def driver_ranking(data, top=15):
    rows = []
    for idx, (driver, total) in enumerate(data["Conductor"].value_counts().head(top).items(), 1):
        ddf = data[data["Conductor"] == driver]
        fat = ddf[ddf["EsFatiga"]]
        rows.append({
            "Rank": idx,
            "Conductor": driver,
            "Total alertas": int(total),
            "Principal plataforma": ddf["Plataforma"].value_counts().index[0] if not ddf.empty else "-",
            "Principal alerta": ddf["Incidente"].value_counts().index[0] if not ddf.empty else "-",
            "Eventos fatiga": len(fat),
            "Cumple": int((fat[CUMPL_COL] == "SI").sum()),
            "No cumple": int((fat[CUMPL_COL] == "NO").sum()),
        })
    return pd.DataFrame(rows)

def transportista_ranking(data):
    rows = []
    for idx, (transportista, total) in enumerate(data["Transportista"].value_counts().items(), 1):
        tdf = data[data["Transportista"] == transportista]
        fat = tdf[tdf["EsFatiga"]]
        score = risk_score(tdf)
        level, _ = risk_level(score)
        rows.append({
            "Rank": idx,
            "Transportista": transportista,
            "Alertas": int(total),
            "Principal plataforma": tdf["Plataforma"].value_counts().index[0] if not tdf.empty else "-",
            "Eventos fatiga": len(fat),
            "No cumple fatiga": int((fat[CUMPL_COL] == "NO").sum()),
            "Score riesgo": score,
            "Nivel": level,
        })
    return pd.DataFrame(rows)

def executive_insight(data):
    if data.empty:
        return "No hay datos para los filtros seleccionados."
    top_platform = data["Plataforma"].value_counts().index[0]
    top_alert = data["Incidente"].value_counts().index[0]
    top_alert_count = int(data["Incidente"].value_counts().iloc[0])
    top_driver = data["Conductor"].value_counts().index[0]
    fat = data[data["EsFatiga"]]
    score = risk_score(data)
    level, _ = risk_level(score)
    return (
        f"Nivel de riesgo **{level}** con score **{score}/100**. "
        f"La plataforma con mayor volumen es **{top_platform}**. "
        f"El principal foco es **{top_alert}** con **{top_alert_count} eventos**. "
        f"El conductor con mayor recurrencia es **{top_driver}**. "
        f"Fatiga: **{len(fat)} eventos**, **{int((fat[CUMPL_COL]=='SI').sum())} cumple** y **{int((fat[CUMPL_COL]=='NO').sum())} no cumple**."
    )

def to_excel_bytes(dfs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, dataframe in dfs.items():
            dataframe.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    output.seek(0)
    return output

st.title("🚦 Torre de Control COPEC")
st.caption("Dashboard operativo de alertas Guardian y FlotaGo · Fuente: Google Sheets · Datos desde 01-01-2026 · Refresco cada 5 minutos.")

with st.sidebar:
    st.header("Fuente de datos")
    if st.button("🔄 Actualizar ahora"):
        st.cache_data.clear()
        st.rerun()

try:
    raw = load_google_sheets()
except Exception as exc:
    st.error("No pude conectar a Google Sheets.")
    st.write("Revisa que el Sheet esté compartido con la cuenta de servicio, los Secrets y los nombres de hojas.")
    st.code(str(exc))
    st.stop()

df = normalize_data(raw)
if df.empty:
    st.warning("No hay datos desde el 1 de enero de 2026.")
    st.stop()

st.sidebar.header("Filtros")
min_available = max(df["Fecha"].min().date(), date(2026, 1, 1))
max_available = df["Fecha"].max().date()
date_range = st.sidebar.date_input("📅 Rango de fechas", value=(min_available, max_available), min_value=min_available, max_value=max_available)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_available, max_available
if start_date > end_date:
    st.sidebar.error("La fecha inicial no puede ser mayor que la fecha final.")
    st.stop()

base_filtered = df[(df["FechaDia"] >= start_date) & (df["FechaDia"] <= end_date)].copy()

selected_plataforma = st.sidebar.selectbox("Plataforma", ["Todas"] + sorted(base_filtered["Plataforma"].unique().tolist()))
selected_transportista = st.sidebar.selectbox("Transportista", ["Todos"] + sorted(base_filtered["Transportista"].unique().tolist()))
selected_incidente = st.sidebar.selectbox("Incidente", ["Todos"] + sorted(base_filtered["Incidente"].unique().tolist()))
selected_conductor = st.sidebar.selectbox("Conductor", ["Todos"] + sorted(base_filtered["Conductor"].unique().tolist()))
search = st.sidebar.text_input("Búsqueda general", placeholder="Patente, planta, texto...").strip().lower()

filtered = base_filtered.copy()
if selected_plataforma != "Todas":
    filtered = filtered[filtered["Plataforma"] == selected_plataforma]
if selected_transportista != "Todos":
    filtered = filtered[filtered["Transportista"] == selected_transportista]
if selected_incidente != "Todos":
    filtered = filtered[filtered["Incidente"] == selected_incidente]
if selected_conductor != "Todos":
    filtered = filtered[filtered["Conductor"] == selected_conductor]
if search:
    filtered = filtered[filtered.astype(str).apply(lambda row: search in " ".join(row).lower(), axis=1)]

st.markdown(f"""
<div class="period-card">
<b>Periodo activo:</b> {start_date.strftime("%d-%m-%Y")} al {end_date.strftime("%d-%m-%Y")}
&nbsp; | &nbsp; <b>Datos base:</b> desde 01-01-2026
&nbsp; | &nbsp; <b>Plataforma:</b> {selected_plataforma}
&nbsp; | &nbsp; <b>Registros filtrados:</b> {len(filtered)}
</div>
""", unsafe_allow_html=True)

fatigue = filtered[filtered["EsFatiga"]]
fatigue_valid = fatigue[fatigue[CUMPL_COL].isin(["SI","NO"])].copy()
cumple = int((fatigue_valid[CUMPL_COL] == "SI").sum())
no_cumple = int((fatigue_valid[CUMPL_COL] == "NO").sum())
score = risk_score(filtered)
level, css_class = risk_level(score)

c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
with c1: metric_card("Total alertas", f"{len(filtered):,}".replace(",", "."), "Eventos filtrados")
with c2: metric_card("Plataformas", filtered["Plataforma"].nunique(), "Con alertas")
with c3: metric_card("Transportistas", filtered["Transportista"].nunique(), "Con alertas")
with c4: metric_card("Conductores", filtered["Conductor"].nunique(), "Con alertas")
with c5: metric_card("Eventos fatiga", len(fatigue), "Cansancio o fatiga")
with c6: metric_card("No cumple", no_cumple, "Fatiga sin detención")
with c7:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Riesgo</div><div class="metric-value"><span class="{css_class}">{level}</span></div><div class="metric-note">Score {score}/100</div></div>', unsafe_allow_html=True)

st.markdown("### 🧠 Insight ejecutivo")
st.markdown(executive_insight(filtered))

st.markdown("### 📊 Visualización principal")

g0,g1 = st.columns(2)
with g0:
    st.subheader("Alertas por plataforma")
    counts = filtered["Plataforma"].value_counts()
    fig = px.bar(counts.reset_index(), x="Plataforma", y="count", labels={"count":"Alertas"}, text_auto=True)
    fig.update_layout(height=380, margin=dict(l=10,r=10,t=30,b=70))
    st.plotly_chart(fig, use_container_width=True)
with g1:
    st.subheader("Alertas por transportista")
    counts = filtered["Transportista"].value_counts().head(25)
    fig = px.bar(counts.reset_index(), x="Transportista", y="count", labels={"count":"Alertas"}, text_auto=True)
    fig.update_layout(height=380, xaxis_tickangle=-45, margin=dict(l=10,r=10,t=30,b=120))
    st.plotly_chart(fig, use_container_width=True)

g2,g3 = st.columns(2)
with g2:
    st.subheader("Top tipos de alerta")
    counts = filtered["Incidente"].value_counts().head(12)
    fig = px.bar(counts.reset_index(), x="Incidente", y="count", labels={"count":"Alertas"}, text_auto=True)
    fig.update_layout(height=420, xaxis_tickangle=-45, margin=dict(l=10,r=10,t=30,b=120))
    st.plotly_chart(fig, use_container_width=True)
with g3:
    st.subheader("Conductores críticos")
    counts = filtered["Conductor"].value_counts().head(15)
    fig = px.bar(counts.reset_index(), x="count", y="Conductor", orientation="h", labels={"count":"Alertas"}, text_auto=True)
    fig.update_layout(height=420, yaxis=dict(autorange="reversed"), margin=dict(l=10,r=10,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)

g4,g5 = st.columns(2)
with g4:
    st.subheader("Fatiga / Somnolencia: Cumple vs No cumple")
    fat_df = pd.DataFrame({"Estado":["Cumple","No cumple"],"Eventos":[cumple,no_cumple]})
    fig = px.bar(fat_df, x="Estado", y="Eventos", text="Eventos", color="Estado",
                 color_discrete_map={"Cumple":"#16A34A","No cumple":"#DC2626"})
    fig.update_layout(height=420, showlegend=False, margin=dict(l=10,r=10,t=30,b=10))
    st.plotly_chart(fig, use_container_width=True)
with g5:
    st.subheader("Distribución plataforma / alerta")
    pa = filtered.groupby(["Plataforma","Incidente"]).size().reset_index(name="Alertas").sort_values("Alertas", ascending=False).head(20)
    fig = px.bar(pa, x="Incidente", y="Alertas", color="Plataforma", barmode="group")
    fig.update_layout(height=420, xaxis_tickangle=-45, margin=dict(l=10,r=10,t=30,b=120))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Alertas por día")

date_index = pd.date_range(start=start_date, end=end_date, freq="D")
platforms_active = sorted(filtered["Plataforma"].dropna().unique().tolist())

if platforms_active:
    full_index = pd.MultiIndex.from_product(
        [date_index, platforms_active],
        names=["FechaDia", "Plataforma"]
    )

    daily_counts = (
        filtered.assign(FechaDia=pd.to_datetime(filtered["FechaDia"], errors="coerce"))
        .dropna(subset=["FechaDia"])
        .groupby([pd.Grouper(key="FechaDia", freq="D"), "Plataforma"])
        .size()
        .rename("Alertas")
    )

    daily = daily_counts.reindex(full_index, fill_value=0).reset_index()
else:
    daily = pd.DataFrame(columns=["FechaDia","Plataforma","Alertas"])

fig = px.line(
    daily,
    x="FechaDia",
    y="Alertas",
    color="Plataforma",
    markers=True,
    color_discrete_sequence=COLOR_SEQUENCE
)

fig.update_xaxes(
    type="date",
    title_text="Fecha",
    tickformat="%d-%m",
    dtick=7 * 24 * 60 * 60 * 1000,
    tickangle=-45
)

fig.update_yaxes(title_text="Alertas", rangemode="tozero")
fig.update_layout(
    height=420,
    margin=dict(l=10,r=10,t=30,b=90),
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)


st.subheader("Evolución Fatiga / Somnolencia: Cumple vs No cumple")
if not fatigue_valid.empty:
    fatigue_evo = fatigue_valid.assign(
        FechaDia=pd.to_datetime(fatigue_valid["FechaDia"], errors="coerce"),
        Estado=fatigue_valid[CUMPL_COL].map({"SI":"Cumple","NO":"No cumple"})
    )

    date_index = pd.date_range(start=start_date, end=end_date, freq="D")

    full_index = pd.MultiIndex.from_product(
        [date_index, ["Cumple", "No cumple"]],
        names=["FechaDia", "Estado"]
    )

    evo_counts = (
        fatigue_evo
        .groupby([pd.Grouper(key="FechaDia", freq="D"), "Estado"])
        .size()
        .rename("Eventos")
    )

    evo = evo_counts.reindex(full_index, fill_value=0).reset_index()

    fig = px.line(
        evo,
        x="FechaDia",
        y="Eventos",
        color="Estado",
        markers=True,
        color_discrete_map={
            "Cumple":"#10B981",
            "No cumple":"#F59E0B"
        }
    )

    fig.update_layout(
        height=420,
        hovermode="x unified",
        xaxis_title="Fecha",
        yaxis_title="Eventos",
        legend_title="Resultado"
    )

    

    st.plotly_chart(fig, use_container_width=True)

st.markdown("### 📋 Tablas ejecutivas")
tab1,tab2,tab3,tab4,tab5 = st.tabs(["Ranking transportistas","Ranking conductores","Gestión fatiga","Resumen plataforma","Datos filtrados"])

with tab1:
    tr = transportista_ranking(filtered)
    st.dataframe(tr, use_container_width=True, hide_index=True)
with tab2:
    dr = driver_ranking(filtered)
    st.dataframe(dr, use_container_width=True, hide_index=True)
with tab3:
    if fatigue.empty:
        st.info("No hay eventos de fatiga para los filtros seleccionados.")
        fs = pd.DataFrame()
    else:
        fs = (
            fatigue.groupby(["Plataforma","Conductor"])[CUMPL_COL]
            .agg(Eventos="count", Cumple=lambda s:int((s=="SI").sum()), No_cumple=lambda s:int((s=="NO").sum()), Sin_info=lambda s:int((~s.isin(["SI","NO"])).sum()))
            .reset_index()
            .sort_values(["No_cumple","Eventos"], ascending=False)
        )
        st.dataframe(fs, use_container_width=True, hide_index=True)
with tab4:
    ps = filtered.groupby("Plataforma").agg(Alertas=("Incidente","count"), Transportistas=("Transportista","nunique"), Conductores=("Conductor","nunique"), Eventos_fatiga=("EsFatiga","sum")).reset_index()
    st.dataframe(ps, use_container_width=True, hide_index=True)
with tab5:
    cols = [c for c in ["Fecha","Plataforma","Transportista","Conductor","Patente","Planta","Incidente",CUMPL_COL] if c in filtered.columns]
    st.dataframe(filtered[cols], use_container_width=True, hide_index=True)

st.markdown("### ⬇️ Exportar información")
excel_bytes = to_excel_bytes({
    "Ranking transportistas": transportista_ranking(filtered),
    "Ranking conductores": driver_ranking(filtered),
    "Fatiga": fs if "fs" in locals() else pd.DataFrame(),
    "Resumen plataforma": ps if "ps" in locals() else pd.DataFrame(),
    "Datos filtrados": filtered[[c for c in ["Fecha","Plataforma","Transportista","Conductor","Patente","Planta","Incidente",CUMPL_COL] if c in filtered.columns]],
})
st.download_button("Descargar Excel con resultados filtrados", data=excel_bytes, file_name=f"dashboard_guardian_flotago_{start_date}_a_{end_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
