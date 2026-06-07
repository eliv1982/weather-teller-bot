import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def collect_inline_callback_data(markup) -> list[str]:
    """Extract all callback_data strings from an InlineKeyboardMarkup (real or stub)."""
    result = []
    for row in getattr(markup, "keyboard", []):
        for button in row:
            cd = getattr(button, "callback_data", None)
            if cd is not None:
                result.append(cd)
    return result


TELEGRAM_CALLBACK_DATA_LIMIT = 64

