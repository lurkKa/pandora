"""Conservative, local quality checks for a student's explanation.

These checks reject obvious noise; they do not claim to prove understanding.
Teachers can inspect the original explanation alongside the submitted code.
"""
import re
from collections import Counter


def explanation_error(text: str, code: str, category: str | None = None) -> str | None:
    text = (text or '').strip()
    if not 10 <= len(text) <= 6000:
        return 'Объяснение должно содержать от 10 до 6000 символов.'
    words = re.findall(r'[a-zа-яё][a-zа-яё_]*', text.lower())
    meaningful = [w for w in words if len(w) >= 3]
    if not meaningful:
        return 'Опиши решение своими словами: случайные буквы и повторяющиеся слова не принимаются.'
    if len(words) >= 4 and Counter(words).most_common(1)[0][1] > len(words) * .3:
        return 'Слишком много повторов. Объясни, как работает твой код.'
    # Keyboard walks, character runs, and long unbroken noise.
    if re.search(r'(.)\1{5,}|asdf|qwert|йцук|фыва|[a-zа-яё]{32,}', text.lower()):
        return 'В объяснении обнаружен случайный набор символов. Напиши связный текст.'
    groups = (
        r'вход|аргумент|параметр|получа|принима|переда|исходн|input|argument|parameter|receive',
        r'возвращ|результат|вывод|выда|получится|итог|return|result|output',
        r'провер|сравн|вычисл|склады|сумм|умнож|дел[юи]|цикл|переб|сортир|фильтр|выбира|счита|счет|счёт|созда|преобраз|объедин|удал|добав|ищ|поиск|меня|замен|срез|рекурс|сохран|обход|разби|раздел|использ|квадрат|длин|остат|сопостав|извлек|накоп|прибав|вычита|check|compar|calculat|add|sum|multipl|divid|loop|iterat|sort|filter|count|creat|convert|search|slice|recurs|map|split|use',
    )
    if category == 'frontend':
        groups = (
            r'страниц|разметк|элемент|стил|html|css|page|markup|element|style',
            r'отображ|показ|экран|результат|вид|display|render|result|show',
            r'зада|располаг|выравн|цвет|ширин|созда|использ|добав|селектор|grid|flex|color|width|align|layout|creat|use',
        )
    if len(text) < 60:
        if not any(re.search(pattern, text.lower()) for pattern in groups[1:]):
            return 'Кратко опиши действие или результат своего кода.'
        return None
    if len(words) < 10 or len(set(meaningful)) < 7:
        return 'Опиши решение своими словами: случайные буквы и повторяющиеся слова не принимаются.'
    if not all(re.search(pattern, text.lower()) for pattern in groups):
        return 'Не хватает описания: какие данные получает код, что с ними делает и что возвращает.'
    identifiers = set(re.findall(r'\b[A-Za-z_][A-Za-z_0-9]*\b', code or ''))
    mentioned = set(re.findall(r'\b[A-Za-z_][A-Za-z_0-9]*\b', text))
    if identifiers and not (identifiers & mentioned):
        return 'Свяжи объяснение с решением: упомяни имя функции или переменной из своего кода.'
    return None
