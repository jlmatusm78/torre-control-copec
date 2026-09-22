import pandas as pd
from month_comparison import monthly_changes
from evolution import monthly_periods

def test_adjacent_months_and_compliance():
    rows=[]
    for month, yes, no in [(1,30,20),(2,32,8),(3,27,18)]:
        rows += [{'Fecha':pd.Timestamp(2026,month,15), 'answer':answer} for answer in ['SI']*yes+['NO']*no]
    table=monthly_changes(pd.DataFrame(rows),monthly_periods('2026-03',3),lambda a,b:'Con registros de referencia','answer')
    assert table.iloc[0]['Vs. mes anterior']=='Mes base'
    assert table.iloc[1]['Vs. mes anterior']=='-20.0 %'
    assert table.iloc[2]['Vs. mes anterior']=='+12.5 %'
    assert table.iloc[1]['Cambio cumplimiento (pp)']==20
    assert table.iloc[2]['Cambio cumplimiento (pp)']==-20
    partial=monthly_changes(pd.DataFrame(rows),monthly_periods('2026-03',1),lambda a,b:'Período en curso','answer')
    assert partial.iloc[0]['Vs. mes anterior']=='Sin base comparable'
    assert pd.isna(partial.iloc[0]['Cambio cumplimiento (pp)'])
