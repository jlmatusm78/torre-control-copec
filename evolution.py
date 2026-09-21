"""Calendar comparisons for recorded alerts (no exposure-based risk inference)."""
import pandas as pd


def window(data, start, end):
    dates = data['Fecha'].dt.normalize()
    return data.loc[dates.between(pd.Timestamp(start), pd.Timestamp(end))].copy()


def period_status(source, start, end, today):
    start, end, today = map(pd.Timestamp, (start, end, today))
    if source.empty or window(source, start, end).empty:
        return 'Sin datos de referencia'
    if end >= today:
        return 'Período en curso'
    if start < source.Fecha.min().normalize() or end > source.Fecha.max().normalize():
        return 'Cobertura parcial'
    return 'Con registros de referencia'


def variation(previous, current):
    if previous == 0:
        return f'{current} nuevas' if current else 'Sin cambio'
    return f'{(current - previous) / previous * 100:+.1f} %'


def comparison(previous, current, column, comparable=True):
    a = previous.groupby(column).size().rename('Anterior')
    b = current.groupby(column).size().rename('Actual')
    result = pd.concat([a, b], axis=1).fillna(0).astype(int)
    result['Cambio'] = result.Actual - result.Anterior
    result['Variación'] = [variation(a, b) if comparable else 'Sin base comparable'
                           for a, b in zip(result.Anterior, result.Actual)]
    if not comparable:
        result['Cambio'] = float('nan')
    return result.sort_values(['Cambio', 'Actual'], ascending=False).reset_index()


def weekly_periods(today, count):
    monday = pd.Timestamp(today).normalize() - pd.Timedelta(days=pd.Timestamp(today).weekday())
    return [(monday - pd.Timedelta(weeks=i), monday - pd.Timedelta(weeks=i-1, days=1))
            for i in range(count, 0, -1)]


def monthly_periods(end_month, count):
    return [(p.start_time.normalize(), p.end_time.normalize())
            for p in pd.period_range(end=pd.Period(end_month, freq='M'), periods=count, freq='M')]


def evolution(data, source, periods, today, types=None):
    rows = []
    for start, end in periods:
        status = period_status(source, start, end, today)
        sample = window(data, start, end)
        for kind in types or ['Total']:
            count = len(sample) if kind == 'Total' and not types else int((sample.Incidente == kind).sum())
            rows.append({'Inicio': start, 'Fin': end, 'Serie': kind,
                         'Alertas': None if status == 'Sin datos de referencia' else count,
                         'Cobertura': status})
    return pd.DataFrame(rows)
