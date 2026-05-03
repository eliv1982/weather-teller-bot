from formatters import help_text


def test_help_text_matches_visible_grouped_commands():
    text = help_text()

    assert "/start — главное меню" in text
    assert "/weather — прогноз погоды" in text
    assert "/locations — локации" in text
    assert "/subscriptions — подписки" in text
    assert "/help — помощь" in text


def test_help_text_mentions_hidden_shortcuts():
    text = help_text()

    assert "Дополнительно работают быстрые команды:" in text
    for command in ("/current", "/tomorrow", "/forecast", "/details", "/compare", "/geo"):
        assert command in text
