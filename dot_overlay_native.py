#!/usr/bin/env python3

import argparse
import math
import mmap
import sys

import cairo

from pywayland.client import Display
from pywayland.utils import AnonymousFile
from pywayland.protocol.wayland import WlCompositor, WlShm
from pywayland.protocol.wlr_layer_shell_unstable_v1 import (
    ZwlrLayerShellV1,
    ZwlrLayerSurfaceV1,
)


class Dot:
    def __init__(self, radius, color, x, y, image_path=None):
        self.radius = int(radius)
        self.color = tuple(int(v) for v in color)
        self.x = x
        self.y = y
        self.image_path = image_path
        self.image_surface = None

        if self.image_path:
            self.image_surface = cairo.ImageSurface.create_from_png(self.image_path)
            self.size = self.radius * 2 + 2
        else:
            self.size = self.radius * 2 + 2

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

        if not (self.compositor and self.shm and self.shell):
            raise RuntimeError(
                "Не найден zwlr_layer_shell_v1. "
                "Проверьте, что приложение запущено в Wayland-сессии (не X11)."
            )

        self.create_layer_surface()

    def on_global(self, registry, id_, interface, version):
        if interface == "wl_compositor":
            self.compositor = registry.bind(id_, WlCompositor, version)
            print("[dot] wl_compositor v%d" % version, flush=True)
        elif interface == "wl_shm":
            self.shm = registry.bind(id_, WlShm, version)
            print("[dot] wl_shm v%d" % version, flush=True)
        elif interface == "zwlr_layer_shell_v1":
            self.shell = registry.bind(id_, ZwlrLayerShellV1, version)
            print("[dot] zwlr_layer_shell_v1 v%d" % version, flush=True)

    def create_layer_surface(self):
        surface = self.compositor.create_surface()
        self.surface = surface

        layer = self.shell.get_layer_surface(
            surface, None,
            ZwlrLayerShellV1.layer.overlay.value,
            "dot-overlay",
        )
        self.layer = layer
        layer.dispatcher["configure"] = self.on_configure
        layer.dispatcher["closed"] = self.on_closed
        layer.user_data = self

        layer.set_size(self.size, self.size)
        if self.x is None or self.y is None:
            layer.set_anchor(0)
        else:
            layer.set_anchor(
                ZwlrLayerSurfaceV1.anchor.top.value
                | ZwlrLayerSurfaceV1.anchor.left.value
            )
            layer.set_margin(self.y, 0, 0, self.x)
        layer.set_keyboard_interactivity(0)

        region = self.compositor.create_region()
        surface.set_input_region(region)
        region.destroy()

        surface.commit()
        self.display.roundtrip()
        if self.image_path:
            print(f"[dot] изображение загружено: {self.image_path} ({self.size}x{self.size})", flush=True)
        else:
            print(f"[dot] точка создана (radius={self.radius}, color={self.color})", flush=True)

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

    def make_buffer(self):
        if self.buffer is not None:
            self.buffer.destroy()

        w = h = self.size
        stride = w * 4

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

        if self.image_path:
            src_data = self.image_surface.get_data()
            iw = self.image_surface.get_width()
            ih = self.image_surface.get_height()
            pixels = bytearray(w * h * 4)
            for out_y in range(self.size):
                src_y = min(max(int(out_y * ih / self.size), 0), ih - 1)
                for out_x in range(self.size):
                    src_x = min(max(int(out_x * iw / self.size), 0), iw - 1)
                    src_idx = (src_y * iw + src_x) * 4
                    r = src_data[src_idx]
                    g = src_data[src_idx + 1]
                    b = src_data[src_idx + 2]
                    a = src_data[src_idx + 3]
                    dst_idx = (out_y * w + out_x) * 4
                    pixels[dst_idx] = a
                    pixels[dst_idx + 1] = r
                    pixels[dst_idx + 2] = g
                    pixels[dst_idx + 3] = b
            self.data[:] = pixels
        else:
            img = cairo.ImageSurface.create_for_data(
                self.data, cairo.FORMAT_ARGB32, w, h, stride
            )
            ctx = cairo.Context(img)
            ctx.set_operator(cairo.OPERATOR_CLEAR)
            ctx.paint()
            ctx.set_operator(cairo.OPERATOR_OVER)
            r, g, b = (v / 255.0 for v in self.color)
            ctx.set_source_rgb(r, g, b)
            ctx.arc(w / 2.0, h / 2.0, self.radius, 0, 2 * math.pi)
            ctx.fill()
            img.flush()

    def run(self):
        try:
            self.display.dispatch(block=True)
        except KeyboardInterrupt:
            pass


def main():
    ap = argparse.ArgumentParser(description="Native Wayland dot overlay (layer-shell)",
                                   epilog="Программа выключается коммандой pkill -9 -f dot_overlay_native.py")
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--color", default="200,0,0", help="R,G,B")
    ap.add_argument("--x", type=int, default=None,
                    help="позиция верхнего-левого угла точки по X (по умолчанию центр)")
    ap.add_argument("--y", type=int, default=100,
                    help="позиция верхнего-левого угла точки по Y")
    ap.add_argument("--use", type=str, default=None,
                    help="путь к PNG-изображению — вместо точки")
    args = ap.parse_args()

    try:
        color = tuple(int(v) for v in args.color.split(","))
        if len(color) != 3:
            raise ValueError
    except ValueError:
        print("Некорректный --color, используйте формат R,G,B")
        sys.exit(1)

    dot = Dot(radius=args.radius, color=color, x=args.x, y=args.y,
              image_path=args.use)
    dot.run()

if __name__ == "__main__":
    main()
