import io
from zoneinfo import ZoneInfo
from datetime import datetime
from evolution import window, period_status, variation, comparison, weekly_periods, monthly_periods, evolution
from alert_names import normalize_alerts
from compliance import compliance_summary, percentage_point_change
from month_comparison import monthly_changes, BASE, MONTHS
import pandas as pd
import plotly.express as px
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Torre de Control COPEC", page_icon="🚦", layout="wide", initial_sidebar_state="expanded")

CUMPL_COL = "Conductor se detine mínimo 15 minutos"

COLOR_SEQUENCE=["#2563EB","#0EA5E9","#16A34A","#D97706","#DC2626","#7C3AED","#0891B2","#475569"]

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
            raise RuntimeError(f"No se pudo leer la hoja {ws_name}") from exc
    if not dfs:
        st.error("No se pudo cargar GUARDIAN ni FLOTAGO/FlotaGo.")
        st.stop()
    return pd.concat(dfs, ignore_index=True, sort=False)

def normalize_data(df):
    df = df.copy()
    if "Fecha" not in df.columns:
        st.error("La base no contiene la columna 'Fecha'.")
        st.stop()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True, format="mixed")
    df = df[df["Fecha"].notna()].copy()
    df = df[df["Fecha"] >= BASE].copy()
    # Homologar nombres habituales para identificar cada evento.
    alias_map = {
        "ID": ["Id", "id", "ID Evento", "ID evento", "Evento ID"],
        "Tracto": ["TRACTO", "tracto", "N° Tracto", "Nº Tracto", "Nro Tracto"],
    }
    for canonical, aliases in alias_map.items():
        if canonical not in df.columns:
            for alias in aliases:
                if alias in df.columns:
                    df[canonical] = df[alias]
                    break
        if canonical not in df.columns:
            df[canonical] = ""

    for col in ["ID", "Tracto", "Plataforma", "Transportista", "Conductor", "Incidente", "Planta", "Patente"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["Plataforma"] = df["Plataforma"].replace("", "SIN PLATAFORMA")
    df["Transportista"] = df["Transportista"].replace("", "SIN TRANSPORTISTA IDENTIFICADO")
    df["Conductor"] = df["Conductor"].replace("", "SIN CONDUCTOR")
    df["Incidente original"] = df["Incidente"].copy()
    df["Incidente"] = normalize_alerts(df["Incidente"])
    df["Planta"] = df["Planta"].replace("", "SIN PLANTA")
    df["Patente"] = df["Patente"].replace("", "SIN PATENTE")
    df["ID"] = df["ID"].replace("", "SIN ID")
    # El tracto es un IDENTIFICADOR, no una magnitud numérica.
    # Limpia valores provenientes de Sheets/Excel como 5568.0 -> 5568.
    df["Tracto"] = (
        df["Tracto"]
        .str.replace(r"^([0-9]+)\.0$", r"\1", regex=True)
        .replace("", "SIN TRACTO")
    )
    if CUMPL_COL not in df.columns:
        df[CUMPL_COL] = ""
    df[CUMPL_COL] = df[CUMPL_COL].fillna("").astype(str).str.strip().str.upper().replace({"SÍ":"SI","SI.":"SI","NO.":"NO"})
    df["EsFatiga"] = df["Incidente"].str.contains("fatiga|cansancio|somnolencia", case=False, na=False)
    df["FechaDia"] = df["Fecha"].dt.date
    return df

def to_excel_bytes(dfs):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, dataframe in dfs.items():
            dataframe.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    output.seek(0)
    return output


st.title('Torre de Control COPEC')
st.caption('Evolución de alertas · Guardian y FlotaGo · Actualización cada 5 minutos')

if st.sidebar.button('Actualizar datos'):
    st.cache_data.clear()
    st.rerun()
try:
    df = normalize_data(load_google_sheets())
except Exception:
    st.error('No se pudo conectar a Google Sheets. Revisa la configuración y los permisos de la cuenta de servicio.')
    st.stop()
if df.empty:
    st.info('No hay registros con fechas válidas.')
    st.stop()
today = pd.Timestamp(datetime.now(ZoneInfo('America/Santiago')).date())
future = int((df.Fecha.dt.normalize() > today).sum())
df = df[df.Fecha.dt.normalize() <= today].copy()
if future:
    st.warning(f'Se excluyeron {future} registros con fechas futuras.')
if df.empty:
    st.info('No hay registros hasta la fecha actual.')
    st.stop()
st.caption(f'Histórico disponible: {df.Fecha.min():%d/%m/%Y} – {df.Fecha.max():%d/%m/%Y}. Cada fila representa una alerta registrada.')

st.sidebar.header('Filtros')
platform = st.sidebar.selectbox('Plataforma', ['Todas'] + sorted(df.Plataforma.unique()))
source = df if platform == 'Todas' else df[df.Plataforma == platform]
carrier = st.sidebar.selectbox('Transportista', ['Todos'] + sorted(source.Transportista.unique()))
data = source.copy() if carrier == 'Todos' else source[source.Transportista == carrier].copy()
selected_types = st.sidebar.multiselect('Tipo de alerta', sorted(data.Incidente.unique()), help='Sin selección: todas las alertas.')
if selected_types:
    data = data[data.Incidente.isin(selected_types)]
with st.sidebar.expander('Más filtros'):
    plant = st.selectbox('Planta', ['Todas'] + sorted(source.Planta.unique()))
    driver = st.selectbox('Conductor', ['Todos'] + sorted(source.Conductor.unique()))
    search = st.text_input('Buscar tracto, patente o texto').strip().lower()
if plant != 'Todas':
    data = data[data.Planta == plant]
if driver != 'Todos':
    data = data[data.Conductor == driver]
if search:
    exact = data.Tracto.str.lower().eq(search)
    data = data[exact] if exact.any() else data[data.astype(str).apply(lambda col: col.str.lower().str.contains(search, regex=False)).any(axis=1)]

st.sidebar.header('Comparación')
mode = st.sidebar.radio('Vista', ['Semanal', 'Mensual', 'Personalizada'])
if mode == 'Semanal':
    count = st.sidebar.select_slider('Semanas de evolución', options=[4, 5, 6], value=6)
    periods = weekly_periods(today, count)
    current_start, current_end = periods[-1]
    previous_start, previous_end = periods[-2]
    average_label = 'Promedio semanal'
elif mode == 'Mensual':
    months = list(pd.period_range(start=BASE, end=today.to_period('M'), freq='M'))[::-1]
    current_month = st.sidebar.selectbox('Último mes a mostrar', months, index=0,
                                       format_func=lambda p: f'{MONTHS[p.month-1]} {p.year}')
    available = min(24, len(pd.period_range(start=BASE, end=current_month, freq='M')))
    count = st.sidebar.slider('Meses de evolución', 1, available, available) if available > 1 else 1
    previous_month = current_month - 1
    current_start, current_end = monthly_periods(current_month, 1)[0]
    previous_start, previous_end = monthly_periods(previous_month, 1)[0]
    periods = monthly_periods(current_month, count)
    st.sidebar.caption('Cada mes frente al anterior · Enero 2026 es el mes base. El mes en curso no genera una comparación concluyente.')
    average_label = 'Promedio mensual'
else:
    earliest = max(BASE.date(), (today.to_period('M') - 23).start_time.date())
    latest = today.date()
    current_range = st.sidebar.date_input('Período actual', (max(earliest, (today - pd.Timedelta(days=28)).date()), (today-pd.Timedelta(days=1)).date()), min_value=earliest, max_value=latest)
    previous_range = st.sidebar.date_input('Período de referencia', (max(earliest, (today-pd.Timedelta(days=56)).date()), (today-pd.Timedelta(days=29)).date()), min_value=earliest, max_value=latest)
    if len(current_range) != 2 or len(previous_range) != 2:
        st.info('Selecciona el inicio y el fin de ambos períodos.')
        st.stop()
    current_start, current_end = map(pd.Timestamp, current_range)
    previous_start, previous_end = map(pd.Timestamp, previous_range)
    if max(current_start, previous_start) <= min(current_end, previous_end):
        st.warning('Los períodos se superponen. Elige períodos separados para compararlos.')
        st.stop()
    periods = [(d, min(d + pd.Timedelta(days=6), current_end)) for d in pd.date_range(current_start, current_end, freq='7D')]
    average_label = 'Promedio diario actual'

current = window(data, current_start, current_end)
previous = window(data, previous_start, previous_end)
# Evaluate availability per selected platform, before category filters. An empty
# selected category can be zero; an absent source period cannot establish zero.
scopes = [group for _, group in source.groupby('Plataforma')]
def status(start, end):
    states = [period_status(group, start, end, today) for group in scopes]
    return next((s for s in states if s != 'Con registros de referencia'), 'Con registros de referencia')
current_status, previous_status = status(current_start, current_end), status(previous_start, previous_end)
comparable = current_status == previous_status == 'Con registros de referencia'
current_days = (current_end-current_start).days+1
previous_days = (previous_end-previous_start).days+1
st.subheader('Qué cambió')
st.write('**Enero 2026 · Mes base, sin referencia anterior.**') if mode == 'Mensual' and current_start == BASE else st.write(f'**Actual:** {current_start:%d/%m/%Y} al {current_end:%d/%m/%Y}  ·  **Referencia:** {previous_start:%d/%m/%Y} al {previous_end:%d/%m/%Y}')
if not comparable:
    st.warning(f'Actual: {current_status}. Referencia: {previous_status}. Se muestran los registros disponibles, sin calcular variaciones concluyentes.')
if current_days != previous_days:
    st.info(f'Los períodos tienen distinta duración: {current_days} y {previous_days} días. Compara también los promedios diarios.')

alerts = comparison(previous, current, 'Incidente', comparable)
carriers = comparison(previous, current, 'Transportista', comparable)
series = evolution(data, source, periods, today)
for start, end in periods:
    coverage = status(start, end)
    series.loc[series.Inicio.eq(start), 'Cobertura'] = coverage
    if coverage == 'Sin datos de referencia':
        series.loc[series.Inicio.eq(start), 'Alertas'] = float('nan')
full_starts = [start for start, end in periods if status(start, end) == 'Con registros de referencia']
average = sum(len(window(data, start, end)) for start, end in periods if start in full_starts) / len(full_starts) if full_starts else None
if mode == 'Personalizada':
    average = len(current) / current_days if comparable else None
cols = st.columns(4)
cols[0].metric('Alertas del período actual', len(current) if current_status != 'Sin datos de referencia' else 'Sin datos', delta=f'{len(current)-len(previous):+d} alertas' if comparable else None, delta_color='inverse')
cols[1].metric('Variación vs. referencia', variation(len(previous), len(current)) if comparable else 'Sin base')
cols[2].metric(average_label, f'{average:.1f}' if average is not None else 'Sin base')
if not alerts.empty and comparable and alerts.iloc[0]['Cambio'] > 0:
    top = alerts.iloc[0]
    cols[3].metric('Mayor aumento', str(top['Incidente']), f"+{int(top['Cambio'])} alertas", delta_color='inverse')
else:
    cols[3].metric('Mayor aumento', 'Ninguno' if comparable else 'Sin base')
if comparable:
    direction = 'aumentaron' if len(current) > len(previous) else 'disminuyeron' if len(current) < len(previous) else 'no cambiaron'
    st.info(f'Las alertas {direction}: {len(current)} frente a {len(previous)} ({variation(len(previous), len(current))}).')
st.caption('Los promedios semanales/mensuales consideran solo los períodos con referencia disponible. Los conteos reflejan alertas registradas, no una tasa de riesgo por kilómetros o viajes.')

def covered_series(sample, types=None):
    result = evolution(sample, source, periods, today, types)
    for start, end in periods:
        coverage = status(start, end)
        result.loc[result.Inicio.eq(start), 'Cobertura'] = coverage
        if coverage == 'Sin datos de referencia':
            result.loc[result.Inicio.eq(start), 'Alertas'] = float('nan')
    return result


def plot_evolution(values, chart_key, colors=None):
    fig = px.line(values, x='Inicio', y='Alertas', color='Serie', markers=True,
                  text='Alertas', hover_data=['Fin', 'Cobertura'],
                  color_discrete_map=colors, color_discrete_sequence=COLOR_SEQUENCE)
    fig.update_traces(connectgaps=False, textposition='top center')
    fig.update_layout(height=340, hovermode='x unified', legend_title_text='')
    fig.update_xaxes(title='Inicio del período', tickformat='%d/%m/%Y')
    fig.update_yaxes(rangemode='tozero', title='Alertas registradas')
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


monthly_exports = []
def show_monthly(sample, name, fatigue=False):
    if mode != 'Mensual':
        return
    table = monthly_changes(sample, periods, status, CUMPL_COL if fatigue else None)
    if fatigue:
        columns = ['Mes', 'Cumple', 'No cumple', 'Sin información', 'Cumplimiento (%)', 'Comparación cumplimiento', 'Cobertura']
    else:
        columns = ['Mes', 'Alertas', 'Cambio', 'Vs. mes anterior', 'Promedio diario', 'Cobertura']
    st.markdown('**Comparación con el mes anterior**')
    st.dataframe(table[columns], hide_index=True, use_container_width=True)
    monthly_exports.append(table.assign(Serie=name))

st.subheader('Evolución general')
plot_evolution(series, 'evolution_total')
show_monthly(data, 'Total')
st.caption('Sin datos de referencia se muestra como un espacio en el gráfico. La cobertura se infiere de los registros por plataforma y no certifica que la carga esté completa.')
export_series = [series]
fatigue_exports = []
rate_exports = []
compliance_comparisons = []
visible_types = selected_types or sorted(data.Incidente.unique())
for index, kind in enumerate(visible_types):
    st.subheader(kind)
    kind_data = data[data.Incidente.eq(kind)]
    current_count = int(current.Incidente.eq(kind).sum())
    previous_count = int(previous.Incidente.eq(kind).sum())
    st.write(f'Actual: **{current_count}** · Referencia: **{previous_count}** · Cambio: **{current_count-previous_count:+d} ({variation(previous_count, current_count)})**' if comparable else f'Registros actuales: **{current_count}** · Referencia: **{previous_count}** · Sin base comparable')
    individual = covered_series(kind_data, [kind])
    plot_evolution(individual, f'alert_{index}')
    export_series.append(individual)
    show_monthly(kind_data, kind)
    visible_fatigue = window(kind_data[kind_data.EsFatiga], periods[0][0], periods[-1][1])
    if not visible_fatigue.empty or not window(kind_data[kind_data.EsFatiga], previous_start, previous_end).empty or not window(kind_data[kind_data.EsFatiga], current_start, current_end).empty:
        st.markdown('**Cumplimiento de detención · ' + kind + '**')
        compliance = kind_data[kind_data.EsFatiga].copy()
        compliance['Incidente'] = compliance[CUMPL_COL].map({'SI':'Cumple', 'NO':'No cumple'})
        compliance_series = covered_series(compliance, ['Cumple', 'No cumple'])
        plot_evolution(compliance_series, f'compliance_{index}', {'Cumple':'#16A34A', 'No cumple':'#DC2626'})
        missing = int((~visible_fatigue[CUMPL_COL].isin(['SI', 'NO'])).sum())
        st.caption(f'Sin información de cumplimiento: {missing} eventos en la evolución mostrada. No se incluyen en Cumple ni No cumple.')
        fatigue_exports.append(compliance_series.assign(Alerta=kind))
        actual_stats = compliance_summary(window(kind_data, current_start, current_end), CUMPL_COL)
        reference_stats = compliance_summary(window(kind_data, previous_start, previous_end), CUMPL_COL)
        change_pp = percentage_point_change(reference_stats, actual_stats, comparable)
        rate = actual_stats['Cumplimiento (%)']
        reference_rate = reference_stats['Cumplimiento (%)']
        k1, k2, k3, k4 = st.columns(4)
        k1.metric('Cumplimiento actual', f'{rate:.1f} %' if rate is not None else 'Sin información',
                  delta=f'{change_pp:+.1f} puntos porcentuales' if change_pp is not None else None)
        k2.metric('Cumplimiento de referencia', f'{reference_rate:.1f} %' if reference_rate is not None else 'Sin información')
        no_delta = actual_stats['No cumple'] - reference_stats['No cumple']
        k3.metric('No cumple · actual', actual_stats['No cumple'],
                  delta=f"{no_delta:+d} ({variation(reference_stats['No cumple'], actual_stats['No cumple'])})" if change_pp is not None else None,
                  delta_color='inverse')
        k4.metric('Sin información · actual', actual_stats['Sin información'])
        st.caption(f"Respuestas válidas: actual {actual_stats['Válidos']} · referencia {reference_stats['Válidos']}. No cumple de referencia: {reference_stats['No cumple']}. Sin información de referencia: {reference_stats['Sin información']}.")
        if change_pp is not None:
            movement = 'subió' if change_pp > 0 else 'bajó' if change_pp < 0 else 'se mantuvo'
            st.info(f'El cumplimiento {movement}: {reference_rate:.1f} % → {rate:.1f} % ({change_pp:+.1f} puntos porcentuales).')
        else:
            st.info('Sin base comparable de cumplimiento: faltan respuestas válidas o alguno de los períodos tiene cobertura parcial.')
        rate_rows = []
        for start, end in periods:
            stats = compliance_summary(window(kind_data, start, end), CUMPL_COL)
            coverage = status(start, end)
            if coverage == 'Sin datos de referencia':
                stats['Cumplimiento (%)'] = None
            rate_rows.append({'Inicio': start, 'Fin': end, 'Cobertura': coverage, 'Alerta': kind, **stats})
        rates = pd.DataFrame(rate_rows)
        st.markdown('**Evolución del porcentaje de cumplimiento**')
        rate_fig = px.line(rates, x='Inicio', y='Cumplimiento (%)', markers=True,
                           hover_data=['Fin', 'Cumple', 'No cumple', 'Válidos', 'Sin información', 'Cobertura'],
                           color_discrete_sequence=['#16A34A'])
        rate_fig.update_traces(connectgaps=False, text=rates['Cumplimiento (%)'].map(lambda x: f'{x:.1f} %' if pd.notna(x) else ''),
                               mode='lines+markers+text', textposition='bottom center')
        rate_fig.update_yaxes(range=[0, 100], ticksuffix=' %')
        rate_fig.update_xaxes(title='Inicio del período', tickformat='%d/%m/%Y')
        rate_fig.update_layout(height=340, hovermode='x unified')
        st.plotly_chart(rate_fig, use_container_width=True, key=f'compliance_rate_{index}')
        st.caption('Cumplimiento = Cumple ÷ (Cumple + No cumple). Sin respuestas válidas: Sin información, sin punto en el gráfico. Los períodos parciales muestran solo el porcentaje observado; no se usan para concluir alzas o bajas.')
        rate_exports.append(rates)
        show_monthly(kind_data, kind + ' · Cumplimiento', fatigue=True)
        compliance_comparisons.extend([
            {'Alerta':kind, 'Período':'Actual', 'Inicio':current_start, 'Fin':current_end, 'Cobertura':current_status, 'Cambio (pp)':change_pp, **actual_stats},
            {'Alerta':kind, 'Período':'Referencia', 'Inicio':previous_start, 'Fin':previous_end, 'Cobertura':previous_status, 'Cambio (pp)':None, **reference_stats}
        ])

series = pd.concat(export_series, ignore_index=True)
with st.expander('Ver valores y cobertura de la evolución'):
    st.dataframe(series, hide_index=True, use_container_width=True)

st.subheader('Comparación por tipo de alerta')
total = pd.DataFrame([{'Incidente':'TOTAL', 'Anterior':len(previous), 'Actual':len(current), 'Cambio':len(current)-len(previous) if comparable else None, 'Variación':variation(len(previous), len(current)) if comparable else 'Sin base comparable'}])
alert_table = pd.concat([alerts, total], ignore_index=True)
st.dataframe(alert_table, hide_index=True, use_container_width=True)
st.write(f'**Promedio diario registrado:** actual {len(current)/current_days:.2f} · referencia {len(previous)/previous_days:.2f}')

st.subheader('Dónde se concentra el cambio')
carriers['Participación actual (%)'] = (carriers.Actual / len(current)*100).round(1) if len(current) else 0.0
st.dataframe(carriers, hide_index=True, use_container_width=True)
if comparable and not carriers.empty:
    chart = carriers.assign(magnitude=carriers.Cambio.abs()).nlargest(15, 'magnitude')
    fig = px.bar(chart, x='Cambio', y='Transportista', orientation='h', color='Cambio', color_continuous_scale=['#16A34A','#CBD5E1','#DC2626'], color_continuous_midpoint=0)
    fig.update_layout(height=max(300, len(chart)*30), yaxis={'autorange':'reversed'}, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with st.expander('Detalle de eventos y gestión de fatiga'):
    fatigue = current[current.EsFatiga]
    a, b, c = st.columns(3)
    a.metric('Fatiga: cumple detención', int(fatigue[CUMPL_COL].eq('SI').sum()))
    b.metric('Fatiga: no cumple', int(fatigue[CUMPL_COL].eq('NO').sum()))
    c.metric('Fatiga: sin respuesta válida', int((~fatigue[CUMPL_COL].isin(['SI','NO'])).sum()))
    detail_cols = ['ID','Fecha','Tracto','Plataforma','Transportista','Conductor','Patente','Planta','Incidente','Incidente original',CUMPL_COL]
    st.dataframe(current[detail_cols].sort_values('Fecha', ascending=False), hide_index=True, use_container_width=True)
metadata = pd.DataFrame([{'Actual desde':current_start, 'Actual hasta':current_end, 'Referencia desde':previous_start, 'Referencia hasta':previous_end, 'Estado actual':current_status, 'Estado referencia':previous_status, 'Plataforma':platform, 'Transportista':carrier, 'Alertas':', '.join(selected_types) or 'Todas', 'Planta':plant, 'Conductor':driver, 'Búsqueda':search}])
st.download_button('Descargar comparación y detalle en Excel', data=to_excel_bytes({'Comparación alertas':alert_table, 'Transportistas':carriers, 'Evolución':series, 'Evolución cumplimiento':pd.concat(fatigue_exports, ignore_index=True) if fatigue_exports else pd.DataFrame(), 'Tasa cumplimiento':pd.concat(rate_exports, ignore_index=True) if rate_exports else pd.DataFrame(), 'Comparación cumplimiento':pd.DataFrame(compliance_comparisons), 'Comparación mensual':pd.concat(monthly_exports, ignore_index=True) if monthly_exports else pd.DataFrame(), 'Período actual':current[detail_cols], 'Referencia':previous[detail_cols], 'Filtros y períodos':metadata}), file_name=f'COPEC_evolucion_{current_start:%Y%m%d}_{current_end:%Y%m%d}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
