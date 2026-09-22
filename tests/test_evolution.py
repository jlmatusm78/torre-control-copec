import pandas as pd
from evolution import window, weekly_periods, monthly_periods, variation, comparison, period_status, evolution


def frame(dates, kinds=None):
    return pd.DataFrame({'Fecha':pd.to_datetime(dates), 'Incidente': kinds or ['A']*len(dates)})


def test_calendar_boundaries():
    weeks = weekly_periods('2026-01-05', 6)
    assert len(weeks) == 6
    assert weeks[-1] == (pd.Timestamp('2025-12-29'), pd.Timestamp('2026-01-04'))
    assert all((b-a).days == 6 for a,b in weeks)
    assert monthly_periods('2024-02', 1)[0][1] == pd.Timestamp('2024-02-29')
    assert len(monthly_periods('2026-08', 24)) == 24


def test_end_day_inclusive():
    data = frame(['2025-01-01 23:59:59', '2025-01-02 00:00:00'])
    assert len(window(data, '2025-01-01', '2025-01-01')) == 1


def test_variations_and_disappearing_categories():
    assert variation(0, 5) == '5 nuevas'
    assert variation(0, 0) == 'Sin cambio'
    assert variation(20, 10) == '-50.0 %'
    a = frame(['2025-01-01']*2, ['A','B'])
    b = frame(['2025-01-02']*2, ['A','C'])
    result = comparison(a,b,'Incidente').set_index('Incidente')
    assert result.loc['B','Cambio'] == -1
    assert result.loc['C','Variación'] == '1 nuevas'
    assert comparison(a,b,'Incidente',False).Cambio.isna().all()


def test_missing_not_zero_and_partial():
    source = frame(['2025-01-02','2025-01-15','2025-01-31'])
    assert period_status(source,'2025-01-01','2025-01-07','2025-02-01') == 'Cobertura parcial'
    assert period_status(source,'2025-01-08','2025-01-14','2025-02-01') == 'Sin datos de referencia'
    result = evolution(source.iloc[:0],source,[(pd.Timestamp('2025-01-08'),pd.Timestamp('2025-01-14')),(pd.Timestamp('2025-01-15'),pd.Timestamp('2025-01-21'))],'2025-02-01')
    assert pd.isna(result.iloc[0].Alertas)
    assert result.iloc[1].Alertas == 0


def test_all_alert_spelling_variants():
    from evolution import normalize_alerts
    values = pd.Series(['Sensor Tapado', 'SENSOR TAPADO', ' sensor  tapado ', 'DISTRACCIÓN', 'distraccion', 'CANSANCIO O FATIGA', 'Cansancio o fatiga', 'Sensor desalineado'])
    result = normalize_alerts(values)
    assert result.iloc[:3].tolist() == ['Sensor tapado'] * 3
    assert result.iloc[3] == result.iloc[4] == 'Distracción'
    assert result.iloc[5] == result.iloc[6] == 'Cansancio o fatiga'
    assert result.nunique() == 4
