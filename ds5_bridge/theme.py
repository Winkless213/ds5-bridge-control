# -*- coding: utf-8 -*-
"""Visual language for the DS5 Bridge console."""

from __future__ import annotations

BG = "#080C11"
SURFACE = "#0D141B"
SURFACE_2 = "#111B23"
SURFACE_3 = "#16222C"
BORDER = "#1D2B36"
BORDER_SOFT = "#16212A"
TEXT = "#E7F0F6"
TEXT_SOFT = "#D5E1E9"
MUTED = "#AFC1CD"
MUTED_2 = "#8DA2B0"
ACCENT = "#6FA8FF"
ACCENT_2 = "#8B7CFF"
ACCENT_DIM = "#2A4A78"
GREEN = "#7CC7FF"
AMBER = "#F5B74E"
RED = "#FF6B7A"

APP_QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI";
    color: {TEXT};
    font-size: 14px;
}}
QMainWindow, QWidget#Root {{
    background: {BG};
}}
QWidget#Sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0D161D, stop:1 #090E13);
    border-right: 1px solid {BORDER_SOFT};
}}
QWidget#Content {{
    background: qradialgradient(cx:0.22, cy:0.0, radius:1.15, fx:0.22, fy:0.0,
        stop:0 #0F1A24, stop:0.48 #0A1117, stop:1 #080C11);
}}
QLabel#PageTitle {{
    color: {TEXT};
    font-size: 28px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QLabel#PageSubtitle {{
    color: {MUTED};
    font-size: 14px;
}}
QLabel#SectionTitle {{
    color: {TEXT_SOFT};
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.9px;
}}
QLabel#Muted {{
    color: {MUTED};
    font-size: 14px;
}}
QLabel#Caption {{
    color: {MUTED};
    font-size: 13px;
}}
QLabel#Description {{
    color: #C4D4DF;
    font-size: 13.5px;
}}
QLabel#Summary {{
    color: #CBD9E3;
    font-size: 13px;
}}
QLabel#ValueBadge {{
    background: rgba(111, 168, 255, 0.07);
    border: 1px solid rgba(111, 168, 255, 0.20);
    border-radius: 9px;
    color: {TEXT_SOFT};
    font-family: "Bahnschrift", "Consolas";
    font-size: 15px;
    font-weight: 600;
    padding: 5px 10px;
}}
QFrame#Card {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {SURFACE_2}, stop:1 {SURFACE});
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#HeroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #101E2E, stop:0.55 #0D1622, stop:1 #0F141C);
    border: 1px solid #24364A;
    border-radius: 18px;
}}
QWidget#CollapsibleHeader {{
    background: transparent;
    border-radius: 9px;
}}
QWidget#CollapsibleHeader:hover {{
    background: rgba(255, 255, 255, 0.025);
}}
QWidget#CollapsibleHeader[pressed="true"] {{
    background: rgba(111, 168, 255, 0.07);
}}
QFrame#Row {{
    background: transparent;
    border-bottom: 1px solid {BORDER_SOFT};
}}
QFrame#Divider {{
    background: {BORDER_SOFT};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
QWidget#StatusPill {{
    background: rgba(124, 199, 255, 0.07);
    border: 1px solid rgba(124, 199, 255, 0.22);
    border-radius: 14px;
}}
QWidget#StatusPill[state="off"] {{
    background: rgba(127, 147, 163, 0.08);
    border: 1px solid rgba(127, 147, 163, 0.22);
}}
QWidget#StatusPill[state="busy"] {{
    background: rgba(245, 183, 78, 0.08);
    border: 1px solid rgba(245, 183, 78, 0.25);
}}
QWidget#BatteryPill {{
    background: rgba(124, 199, 255, 0.07);
    border: 1px solid rgba(124, 199, 255, 0.22);
    border-radius: 14px;
}}
QWidget#BatteryPill[state="off"] {{
    background: rgba(127, 147, 163, 0.08);
    border: 1px solid rgba(127, 147, 163, 0.22);
}}
QWidget#BatteryPill[state="low"] {{
    background: rgba(245, 183, 78, 0.08);
    border: 1px solid rgba(245, 183, 78, 0.25);
}}
QPushButton#NavButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    color: {MUTED};
    font-size: 14px;
    font-weight: 500;
    padding: 12px 16px;
    text-align: left;
}}
QPushButton#NavButton:hover {{
    background: {SURFACE_2};
    color: {TEXT_SOFT};
}}
QPushButton#NavButton:checked {{
    background: rgba(111, 168, 255, 0.09);
    border: 1px solid rgba(111, 168, 255, 0.22);
    color: {TEXT};
}}
QPushButton#PrimaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_2});
    border: none;
    border-radius: 10px;
    color: #07111E;
    font-size: 14px;
    font-weight: 700;
    padding: 11px 20px;
}}
QPushButton#PrimaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #8DBBFF, stop:1 #A294FF);
}}
QPushButton#PrimaryButton:pressed {{
    background: #4F8CFF;
}}
QPushButton#PrimaryButton:disabled {{
    background: #1B2A31;
    color: {MUTED_2};
}}
QPushButton#GhostButton {{
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: {TEXT_SOFT};
    font-size: 14px;
    padding: 10px 16px;
}}
QPushButton#GhostButton:hover {{
    background: {SURFACE_3};
    border-color: #2D4351;
    color: {TEXT};
}}
QPushButton#GhostButton:disabled {{
    color: {MUTED_2};
    border-color: {BORDER_SOFT};
}}
QPushButton#DangerButton {{
    background: transparent;
    border: 1px solid rgba(255, 107, 122, 0.30);
    border-radius: 10px;
    color: {RED};
    font-size: 13.5px;
    padding: 10px 14px;
}}
QPushButton#DangerButton:hover {{
    background: rgba(255, 107, 122, 0.08);
}}
QPushButton#PillButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    color: {MUTED};
    font-size: 13px;
    padding: 8px 15px;
}}
QPushButton#PillButton:hover {{
    background: {SURFACE_3};
    color: {TEXT_SOFT};
}}
QPushButton#PillButton:checked {{
    background: rgba(111, 168, 255, 0.14);
    border: 1px solid rgba(111, 168, 255, 0.36);
    color: #DCEBFF;
    font-weight: 600;
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: #1B2831;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4F8CFF, stop:1 {ACCENT});
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
    background: #E9FFFC;
    border: 2px solid {ACCENT};
}}
QSlider::handle:horizontal:hover {{
    background: #FFFFFF;
    border-color: #A9C8FF;
}}
QComboBox {{
    background: {SURFACE_3};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 11px;
    color: {TEXT_SOFT};
    font-size: 13.5px;
    min-width: 100px;
}}
QComboBox:hover {{
    border-color: #2D4351;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    font-size: 13.5px;
    selection-background-color: rgba(111, 168, 255, 0.18);
    selection-color: {TEXT};
    outline: 0;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: rgba(255, 255, 255, 0.025);
    width: 12px;
    margin: 2px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background: #355364;
    border-radius: 5px;
    min-height: 36px;
}}
QScrollBar::handle:vertical:hover {{
    background: #4A6E80;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QToolTip {{
    background: {SURFACE_3};
    color: {TEXT_SOFT};
    border: 1px solid {BORDER};
    font-size: 13px;
    padding: 8px 10px;
}}
"""
