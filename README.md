# Tochka-for-Wayland-KWin
Не нашел - создал. Нативная точка для игроков Linux, которые используют Wayland + KWin. Можно использовать для игры по типу шутеров.

## 0. Требования

Все требования описаны в документе requirements.txt

## 1. Установка

Скачиваем папку, внутри папки запускаем консоль. Ставим виртуалку:

- Делаем новенькое чисто окружение
`python3 -m venv .venv`
`source .venv/bin/activate`

- Устанавливаем нужные зависимости
`pip install pywayland pycairo`

- Делаем layer-shell
```
python3 -m pywayland.scanner \
  -i wlr-layer-shell-unstable-v1.xml \
     /usr/share/wayland/wayland.xml \
     /usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml \
  -o _gen

cp -r _gen/wlr_layer_shell_unstable_v1 .venv/lib/python3.*/site-packages/pywayland/protocol/
rm -rf _gen
```

## 2. Запуск и отключение

После установки используем консоль из папки

```bash
.venv/bin/python dot_overlay_native.py
```

Если консоль мешает можно ее выключить. 
Когда точка больше не нужна

```bash
pkill -9 -f dot_overlay_native.py
```

## 3. Флаги

### 3.1 Настройка местоположения точки

Местоположение задаётся в **пикселях от верхнего левого угла экрана**

```bash
.venv/bin/python dot_overlay_native.py --x 1500 --y 900
```

### 3.2 Настройка цвета точки

Цвет задаётся в формате **R,G,B** (каждый канал 0–255).

```bash
.venv/bin/python dot_overlay_native.py --color 0,200,0      # зелёная
.venv/bin/python dot_overlay_native.py --color 0,0,255      # синяя
.venv/bin/python dot_overlay_native.py --color 255,255,255  # белая
```

### 3.3 Размер точки

Размер задается через радиус.

```bash
.venv/bin/python dot_overlay_native.py --radius 10
```



