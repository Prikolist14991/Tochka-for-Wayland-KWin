#!/usr/bin/env python3

import argparse
import math
import mmap
import os
import sys

import cairo

from pywayland.client import Display
from pywayland.utils import AnonymousFile
from pywayland.protocol.wayland import WlCompositor, WlShm
from pywayland.protocol.wlr_layer_shell_unstable_v1 import (
    ZwlrLayerShellV1,
    ZwlrLayerSurfaceV1,
)

# Нативный Wayland overlay точки для KWin 6+.

class Dot:
    def __init__(self, radius, color, x, y):
        self.radius = int(radius)
        self.color = tuple(int(v) for v in color)
        self.x = x   # Координаты на Х
        self.y = y   # Координаты на У
   
        self.size = self.radius * 2 + 2    # Размер поверхности: точка + 1px для сглаживания по краям

# Заглушки
        self.compositor = None
        self.shm = None
        self.shell = None
        self.surface = None
        self.layer = None
        self.buffer = None
        self.data = None

        self.display = Display()
        self.display.connect()
        registry = self.display.get_registry()
        registry.dispatcher["global"] = self.on_global
        registry.user_data = self
        self.display.dispatch(block=True)
        self.display.roundtrip()

# Ошибки
        if not (self.compositor and self.shm and self.shell):
            raise RuntimeError(
                "Не найден zwlr_layer_shell_v1.\n "
                "KWin поддерживает его начиная с Plasma 6; проверьте, что приложение запущено \n"
                "в Wayland-сессии (не X11) \n"
            )

        self.create_layer_surface()

    # === Wayland вызов ===
    def on_global(self, registry, id_, interface, version):
        if interface == "wl_compositor":
            self.compositor = registry.bind(id_, WlCompositor, version) 
            print("[dot] wl_compositor v%d" % version, flush=True)   # Подвязываем композитный сервер ака оконный менеджер
        elif interface == "wl_shm":
            self.shm = registry.bind(id_, WlShm, version)
            print("[dot] wl_shm v%d" % version, flush=True)   # Подвязываем передачу изображения между прогой и сервером
        elif interface == "zwlr_layer_shell_v1":
            self.shell = registry.bind(id_, ZwlrLayerShellV1, version)
            print("[dot] zwlr_layer_shell_v1 v%d" % version, flush=True)   # Подвязываем оболочку для слоев

   def create_layer_surface(self):   
        surface = self.compositor.create_surface()
        self.surface = surface

        # output=None -> композитор сам выберет экран
        layer = self.shell.get_layer_surface(
            surface, None,
            ZwlrLayerShellV1.layer.overlay.value, 
            "dot-overlay",
        )
        self.layer = layer   # Слой
        layer.dispatcher["configure"] = self.on_configure
        layer.dispatcher["closed"] = self.on_closed
        layer.user_data = self

        layer.set_size(self.size, self.size)
        if self.x is None or self.y is None:
            layer.set_anchor(0)   # Без якоря точка становится в центр
        else:
            # Якорь в верхний-левый угол экрана, отступы = позиция точки
            layer.set_anchor(
                ZwlrLayerSurfaceV1.anchor.top.value
                | ZwlrLayerSurfaceV1.anchor.left.value
            )
            layer.set_margin(self.y, 0, 0, self.x)    # Отуступы - верх, право, низ, лево
        layer.set_keyboard_interactivity(0)   

        # Клики и прочий ввод проходят сквозь точку окнам ниже
        region = self.compositor.create_region()    # Пустая область
        surface.set_input_region(region)
        region.destroy()

        # Обязательный первый commit БЕЗ буфера: композитор ответит configure
        surface.commit()
        self.display.roundtrip()
        print("[dot] точка создана (radius=%d, color=%s)" % (
            self.radius, self.color), flush=True)

    def on_configure(self, layer, serial, width, height):
        layer.ack_configure(serial)
        if width and height:
            self.size = int(width)
        self.make_buffer()
        self.surface.attach(self.buffer, 0, 0)
        self.surface.damage(0, 0, self.size, self.size)
        self.surface.commit()

    def on_closed(self, layer):
        print("[dot] окно закрыто композитором, выход", flush=True)
        sys.exit(0)

    # === отрисовка на слой===
    def make_buffer(self):
        if self.buffer is not None:
            self.buffer.destroy()

        w = h = self.size
        stride = w * 4    # 4 байта на пиксель

        with AnonymousFile(stride * h) as fd:
            self.data = mmap.mmap(
                fd,
                stride * h,
                prot=mmap.PROT_READ | mmap.PROT_WRITE,
                flags=mmap.MAP_SHARED,
            )
            self.paint()
            pool = self.shm.create_pool(fd, stride * h)
            self.buffer = pool.create_buffer(
                0, w, h, stride, WlShm.format.argb8888.value
            )
            pool.destroy()

    def paint(self):
        w = h = self.size
        stride = w * 4
        img = cairo.ImageSurface.create_for_data(
            self.data, cairo.FORMAT_ARGB32, w, h, stride
        )
        ctx = cairo.Context(img)

        # Прозрачный фон
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.paint()

        # Точка
        ctx.set_operator(cairo.OPERATOR_OVER)
        r, g, b = (v / 255.0 for v in self.color)
        ctx.set_source_rgb(r, g, b)
        ctx.arc(w / 2.0, h / 2.0, self.radius, 0, 2 * math.pi)
        ctx.fill()

        img.flush()

    # === Хелп \ Аргументы ===
    def run(self):
        try:
            self.display.dispatch(block=True)
        except KeyboardInterrupt:
            pass

# Все что ниже можно использовать при вызове программы через консоль. 
# Программу можно запускать, если py-файл сделать исполняемым, но лучше через консоль 
# (Тебе придется редачить default значения, и я не очень уверен что default работает для других значений кроме none)
def main():
    ap = argparse.ArgumentParser(description="Native Wayland dot overlay (layer-shell)",
                                 epilog="Программа выключается коммандой pkill -9 -f dot_overlay_native.py")
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--color", default="200,0,200", help="R,G,B")
    ap.add_argument("--x", type=int, default=None,
                    help="позиция верхнего-левого угла точки по X (по умолчанию центр)")
    ap.add_argument("--y", type=int, default=None,
                    help="позиция верхнего-левого угла точки по Y")
    args = ap.parse_args()

    try:
        color = tuple(int(v) for v in args.color.split(","))
        if len(color) != 3:
            raise ValueError
    except ValueError:
        print("Некорректный --color, используйте формат R,G,B")
        sys.exit(1)

    dot = Dot(radius=args.radius, color=color, x=args.x, y=args.y)
    dot.run()


if __name__ == "__main__":
    main()
