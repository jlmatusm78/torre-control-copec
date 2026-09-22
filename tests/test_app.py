from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest


def test_dashboard_modes_and_filters():
    source = Path('app.py').read_text()
    # Inject synthetic events at the data boundary; no credentials or real data.
    source = source.replace('df = normalize_data(load_google_sheets())', '''df = normalize_data(pd.DataFrame([
        {'Fecha': d, 'Incidente': 'Fatiga' if i % 2 else 'Distracción',
         'Plataforma': 'Guardian' if i % 2 else 'FlotaGo',
         'Transportista': 'Transporte A' if i % 3 else 'Transporte B',
         'Conductor se detine mínimo 15 minutos': ['SI', 'NO', ''][i % 3]}
        for i, d in enumerate(pd.date_range(pd.Timestamp.now().normalize()-pd.Timedelta(days=800), pd.Timestamp.now().normalize()))
    ]))''')
    at = AppTest.from_string(source, default_timeout=30).run()
    assert not at.exception
    assert len(at.metric) >= 4
    assert len(at.get("plotly_chart")) == 6
    assert any("Sin información de cumplimiento" in c.value for c in at.caption)
    at.sidebar.radio[0].set_value('Mensual').run()
    assert not at.exception
    assert len(at.sidebar.radio) == 1
    assert any('Comparación con el mes anterior' in x.value for x in at.markdown)
    at.sidebar.multiselect[0].set_value(['Fatiga']).run()
    assert not at.exception
    assert len(at.get('plotly_chart')) == 4
    at.sidebar.selectbox[-1].set_value(pd.Period('2026-01', freq='M')).run()
    assert not at.exception
    assert any('Mes base' in x.value for x in at.markdown)
    at.sidebar.radio[0].set_value('Personalizada').run()
    assert not at.exception
    at.sidebar.text_input[0].set_value('no-match').run()
    assert not at.exception
