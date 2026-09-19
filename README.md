# Честный ЗНАК — СУЗ API 3.0

Windows GUI for СУЗ API 3.0: manual server URL, OMS ID, clientToken, CryptoPro CAdESCOM detached GOST signature, order/status/codes and CSV export preserving ASCII 29 (GS).

## Important
- ИНН не запрашивается в интерфейсе.
- Для подписи нужен установленный CryptoPro CSP/CAdESCOM и сертификат в CurrentUser\\My.
- СУЗ API 3.0 requires detached CMS/CAdES signature in X-Signature for signed requests.
- Тип оплаты в интерфейсе: «Оплата по нанесению» / «Оплата по эмиссии».

## Build
Run build_exe.bat on Windows with Python 3.11+.

## Current API notes
The API 3.0 documentation is distributed through the Честный ЗНАК help area; exact instance URL is supplied by the participant's СУЗ. The application therefore keeps the server URL editable.
