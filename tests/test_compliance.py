import pandas as pd
from compliance import compliance_summary, percentage_point_change


def stats(yes, no, missing=0):
    return compliance_summary(pd.DataFrame({'answer':['SI']*yes+['NO']*no+['']*missing}), 'answer')


def test_percentage_points_and_missing_answers():
    previous, current = stats(30,20,10), stats(32,8,20)
    assert previous['Cumplimiento (%)'] == 60
    assert current['Cumplimiento (%)'] == 80
    assert current['Sin información'] == 20
    assert percentage_point_change(previous,current) == 20
    assert percentage_point_change(current,previous) == -20
    assert percentage_point_change(previous,current,False) is None


def test_no_valid_answers_are_not_zero_percent():
    assert stats(0,0,5)['Cumplimiento (%)'] is None
    assert stats(0,0)['Cumplimiento (%)'] is None
    assert stats(0,5)['Cumplimiento (%)'] == 0
    assert stats(5,0)['Cumplimiento (%)'] == 100
    assert percentage_point_change(stats(0,0),stats(1,1)) is None
