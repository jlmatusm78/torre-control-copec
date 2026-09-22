"""Compliance rates use valid SI/NO responses only."""
def compliance_summary(data, column):
    yes = int(data[column].eq('SI').sum())
    no = int(data[column].eq('NO').sum())
    valid = yes + no
    return {'Cumple': yes, 'No cumple': no, 'Válidos': valid,
            'Sin información': len(data) - valid,
            'Cumplimiento (%)': 100 * yes / valid if valid else None}


def percentage_point_change(previous, current, comparable=True):
    a, b = previous['Cumplimiento (%)'], current['Cumplimiento (%)']
    return b - a if comparable and a is not None and b is not None else None
