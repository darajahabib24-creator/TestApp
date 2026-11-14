#!/usr/bin/env python3
"""Calculator — a pocket arithmetic calculator for Android (Kivy + p4a).

The expression engine is calculator.py (a whitelist AST evaluator, no eval),
so the app is safe to point at arbitrary input. UI only: this file builds the
Kivy widgets and forwards button presses to calculator.evaluate().

Usage:
    main.py            # build the APK entry point (p4a runs this)
"""

from __future__ import annotations

import sys

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from calculator import CalcError, evaluate, format_result

Window.softinput_mode = "below_target"

DARK = (0.10, 0.10, 0.12, 1)
PANEL = (0.16, 0.16, 0.19, 1)
ACCENT = (0.26, 0.52, 0.96, 1)
ACCENT_2 = (0.96, 0.55, 0.20, 1)
TXT = (0.92, 0.92, 0.95, 1)
DIM = (0.62, 0.62, 0.68, 1)

# Button grid: (label, kind) where kind drives the handler.
# kind: "digit" | "op" | "action"
BUTTONS = [
    ("C", "action"), ("⌫", "action"), ("(", "op"), (")", "op"),
    ("7", "digit"), ("8", "digit"), ("9", "digit"), ("/", "op"),
    ("4", "digit"), ("5", "digit"), ("6", "digit"), ("*", "op"),
    ("1", "digit"), ("2", "digit"), ("3", "digit"), ("-", "op"),
    ("0", "digit"), (".", "digit"), ("^", "op"), ("+", "op"),
    ("sqrt", "fn"), ("pi", "fn"), ("e", "fn"), ("=", "action"),
]


class CalculatorApp(App):
    """Standard four-function calculator with a little scientific spice."""

    expression = StringProperty("")
    result = StringProperty("0")

    def build(self):
        self._expr = ""

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))

        # --- display -----------------------------------------------------
        display = BoxLayout(orientation="vertical", size_hint_y=None,
                            height=dp(120), padding=dp(6))
        self.expr_label = Label(
            text="", font_size="22sp", color=DIM, halign="right",
            valign="bottom", text_size=(Window.width - dp(28), None),
        )
        self.expr_label.bind(width=lambda w, _: setattr(
            w, "text_size", (w.width - dp(12), None)))
        self.out_label = Label(
            text="0", font_size="40sp", color=TXT, halign="right",
            valign="top", text_size=(Window.width - dp(28), None),
        )
        self.out_label.bind(width=lambda w, _: setattr(
            w, "text_size", (w.width - dp(12), None)))
        display.add_widget(self.expr_label)
        display.add_widget(self.out_label)
        root.add_widget(display)

        # --- keypad ------------------------------------------------------
        pad = GridLayout(cols=4, spacing=dp(6), size_hint_y=1)
        for text, kind in BUTTONS:
            pad.add_widget(self._make_key(text, kind))
        root.add_widget(pad)

        # --- history -----------------------------------------------------
        self.history = Label(text="", font_size="13sp", color=DIM,
                             halign="left", valign="top",
                             size_hint_y=None, height=dp(70))
        self.history.bind(width=lambda w, _: setattr(
            w, "text_size", (w.width, None)))
        root.add_widget(self.history)
        self._history_lines = []

        # Physical keyboards (Chromebook / Bluetooth) type straight in.
        self._press = self.on_key
        Window.bind(on_key_down=self._on_hw_key)

        return root

    # -- UI helpers -------------------------------------------------------
    def _make_key(self, text, kind):
        color = {"digit": PANEL, "op": PANEL, "fn": PANEL,
                 "action": ACCENT}.get(kind, PANEL)
        if text == "=":
            color = ACCENT_2
        btn = Button(text=text, font_size="20sp", background_color=color,
                     background_normal="", color=TXT)
        btn.bind(on_release=lambda _b, t=text, k=kind: self.on_key(t, k))
        return btn

    def _on_hw_key(self, _window, key, _scancode, codepoint, modifiers):
        names = {43: "+", 45: "-", 42: "*", 47: "/", 46: ".", 48: "0",
                 49: "1", 50: "2", 51: "3", 52: "4", 53: "5", 54: "6",
                 55: "7", 56: "8", 57: "9", 94: "^", 40: "(", 41: ")",
                 390: "sqrt", 391: "pi", 392: "e"}
        if key in names:
            self.on_key(names[key], "digit" if names[key].isdigit() else
                        ("fn" if names[key] in ("sqrt", "pi", "e") else "op"))
            return True
        if key in (13, 271):          # Enter / numpad Enter
            self.on_key("=", "action")
            return True
        if key == 8:                  # Backspace
            self.on_key("⌫", "action")
            return True
        if codepoint and codepoint in "0123456789+-*/^().%":
            self.on_key(codepoint, "digit")
            return True
        return False

    # -- expression handling ---------------------------------------------
    def on_key(self, text, kind=None):
        kind = kind or ("digit" if text.isdigit() else "op")

        if text == "C":
            self._expr = ""
            self.result = "0"
        elif text == "⌫":
            self._expr = self._expr[:-1]
        elif text == "=":
            self._equals()
            return
        elif text == "sqrt":
            self._insert("sqrt(")
        elif text == "pi":
            self._insert("pi")
        elif text == "e":
            self._insert("e")
        elif kind == "digit":
            self._insert(text)
        else:
            self._insert(text)

        self.expression = self._expr
        self.expr_label.text = self._expr or " "
        self._preview()

    def _insert(self, token):
        self._expr += token

    def _closed(self):
        """Expression with unclosed '(' closed, for evaluation.

        "sqrt(2" evaluates as "sqrt(2)"; "2+" is still incomplete and fails.
        """
        opens = self._expr.count("(") - self._expr.count(")")
        return self._expr + ")" * max(opens, 0)

    def _preview(self):
        """Live result while typing; blank when the expression is incomplete."""
        if not self._expr:
            self.result = "0"
            return
        try:
            self.result = format_result(evaluate(self._closed()))
        except CalcError:
            self.result = ""

    def _equals(self):
        expr = self._closed()
        if not self._expr:
            return
        try:
            value = format_result(evaluate(expr))
        except CalcError as exc:
            self.result = "error"
            self._push_history(f"{expr}   →   error: {exc}")
            return
        self._push_history(f"{expr}   =   {value}")
        self._expr = value
        self.expression = self._expr
        self.expr_label.text = self._expr
        self.result = value

    def _push_history(self, line):
        self._history_lines = (self._history_lines + [line])[-3:]
        self.history.text = "\n".join(self._history_lines)


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if len(argv) > 1:                       # one-shot: main.py "2 + 3 * 4"
        try:
            print(format_result(evaluate(" ".join(argv[1:]))))
            return 0
        except CalcError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    CalculatorApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
