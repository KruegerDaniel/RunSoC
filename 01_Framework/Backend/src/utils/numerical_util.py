def clean_num(value, digits: int = 6):
    if value is None:
        return None

    rounded = round(float(value), digits)

    if abs(rounded - round(rounded)) < 10 ** (-digits):
        return int(round(rounded))

    return rounded
