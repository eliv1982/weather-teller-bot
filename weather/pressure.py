LOW_PRESSURE_HPA = 1000
HIGH_PRESSURE_HPA = 1025

LOW_PRESSURE_NOTE = (
    "Давление заметно ниже обычного — если ты реагируешь на перепады погоды, это стоит учесть."
)
HIGH_PRESSURE_NOTE = (
    "Давление заметно выше обычного — если ты реагируешь на перепады погоды, это стоит учесть."
)


def get_pressure_note_hpa(pressure_hpa: object) -> str | None:
    if not isinstance(pressure_hpa, (int, float)):
        return None

    pressure = float(pressure_hpa)
    if pressure <= LOW_PRESSURE_HPA:
        return LOW_PRESSURE_NOTE
    if pressure >= HIGH_PRESSURE_HPA:
        return HIGH_PRESSURE_NOTE
    return None
