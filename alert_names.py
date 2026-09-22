import pandas as pd

def normalize_alerts(values):
    """Group spelling variants without merging different words; keep accents in labels."""
    import unicodedata
    def clean(value):
        return ' '.join(str(value).split()).casefold() if pd.notna(value) else ''
    def key(value):
        return ''.join(c for c in unicodedata.normalize('NFD', value) if unicodedata.category(c) != 'Mn')
    cleaned = values.map(clean).replace('', 'sin clasificar')
    labels = {}
    for text in sorted(set(cleaned), key=lambda x: (-sum(unicodedata.category(c) == 'Mn' for c in unicodedata.normalize('NFD', x)), x)):
        labels.setdefault(key(text), text.capitalize())
    return cleaned.map(lambda text: labels[key(text)])
