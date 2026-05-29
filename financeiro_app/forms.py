from datetime import datetime


def parse_float(value):
    if value is None:
        return 0.0
    clean = str(value).strip().replace("R$", "").replace(".", "").replace(",", ".")
    return float(clean or 0)


def parse_date(value):
    if not value:
        return datetime.today().date()
    return datetime.strptime(value, "%Y-%m-%d").date()
