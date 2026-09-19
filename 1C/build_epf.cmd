@echo off
chcp 65001 >nul
setlocal

echo ==========================================
echo Экспорт КМ Честный ЗНАК — подготовка EPF
echo ==========================================
echo.

set "ROOT=%~dp0"
set "SRC=%ROOT%ЭкспортКодовЧестныйЗНАК_8_3.bsl"
set "FORM=%ROOT%ЭкспортКодовЧестныйЗНАК_Форма.bsl"

if not exist "%SRC%" (
  echo ОШИБКА: не найден %SRC%
  pause
  exit /b 1
)

if not exist "%FORM%" (
  echo ОШИБКА: не найден %FORM%
  pause
  exit /b 1
)

echo Исходники найдены.
echo.
echo ВАЖНО:
echo Настоящий .EPF нельзя корректно получить простым переименованием
echo .BSL или обычным архиватором. EPF должен быть сохранён самой 1С.
echo.
echo Этот скрипт открывает папку проекта и помогает выполнить
echo однократное создание внешней обработки в установленной 1С.
echo.

set "ONEC="
for %%P in (
  "C:\Program Files\1cv8\common\1cestart.exe"
  "C:\Program Files (x86)\1cv8\common\1cestart.exe"
) do (
  if exist %%P if not defined ONEC set "ONEC=%%~P"
)

if defined ONEC (
  echo Найдена 1С: %ONEC%
  echo.
  echo Запускаю 1С. Создайте новую внешнюю обработку (.epf),
  echo добавьте управляемую форму, команду «Выгрузить КМ в CSV»
  echo и вставьте исходный модуль из:
  echo %SRC%
  echo.
  start "" "%ONEC%"
) else (
  echo 1С не найдена по стандартному пути.
  echo Запустите 1С:Предприятие/Конфигуратор вручную.
)

echo.
echo Файлы проекта:
echo %SRC%
echo %FORM%
echo.
echo После сохранения EPF его можно положить в папку:
echo %ROOT%готовая_EPФ
echo.
pause
endlocal
