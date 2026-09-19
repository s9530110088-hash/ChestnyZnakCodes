# PDF → CSV для Контур СУЛ

Программа распознаёт графические GS1 DataMatrix из PDF и создаёт CSV из трёх колонок:

1. Код маркировки
2. GTIN
3. Название товара

GTIN и название товара вводятся вручную. Код маркировки распознаётся автоматически.

## Важно

ASCII 29 (GS) внутри GS1-кода не удаляется.

## Запуск из Python

```
pip install -r requirements.txt
python app.py
```

## Сборка EXE

Проект содержит GitHub Actions workflow, который собирает Windows EXE через PyInstaller.
