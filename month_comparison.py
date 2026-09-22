"""Adjacent-month comparisons; January 2026 is the baseline."""
import pandas as pd
from evolution import window, variation
from compliance import compliance_summary, percentage_point_change

BASE = pd.Timestamp('2026-01-01')
MONTHS = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

def monthly_changes(data, periods, status, compliance_column=None):
    rows = []
    for start, end in periods:
        prior = start.to_period('M') - 1
        a, b = prior.start_time.normalize(), prior.end_time.normalize()
        current = window(data,start,end)
        previous = window(data,a,b)
        coverage = status(start,end)
        baseline = start == BASE
        valid = not baseline and a >= BASE and coverage == status(a,b) == 'Con registros de referencia'
        label = 'Mes base' if baseline else 'Comparable' if valid else 'Sin base comparable'
        row = {'Mes':f'{MONTHS[start.month-1]} {start.year}', 'Cobertura':coverage,
               'Alertas':len(current) if coverage != 'Sin datos de referencia' else None,
               'Cambio':len(current)-len(previous) if valid else None,
               'Vs. mes anterior':variation(len(previous),len(current)) if valid else label,
               'Promedio diario':len(current)/((end-start).days+1) if coverage == 'Con registros de referencia' else None}
        if compliance_column:
            now = compliance_summary(current,compliance_column)
            before = compliance_summary(previous,compliance_column)
            pp = percentage_point_change(before,now,valid)
            row.update(now)
            row['Cambio cumplimiento (pp)'] = pp
            row['Comparación cumplimiento'] = f'{pp:+.1f} pp' if pp is not None else 'Mes base' if baseline else 'Sin información' if now['Válidos'] == 0 else 'Sin base comparable'
        rows.append(row)
    return pd.DataFrame(rows)
