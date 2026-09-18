# -*- coding: utf-8 -*-
"""界面各页面：同步带传动、齿轮传动、传动链与速度、规格库、使用说明。"""

from __future__ import annotations

import datetime
import html
import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox,
                               QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QScrollArea, QSizePolicy, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from core.drive_core import (BELT_FAMILIES, BELT_PROFILES, MODULE_FIRST,
                             MODULE_SECOND, MODULES_ALL, MODULE_MAX, MODULE_MIN,
                             PRESSURE_ANGLES, TEETH_PRESETS, DesignError,
                             belt_profile, chain_compute, design_belt,
                             design_gears, gear_pair, min_teeth,
                             pulley_outside_dia, pulley_pitch_dia,
                             pulley_root_dia, system_compute)

from .diagram import BeltDiagram, ChainDiagram, GearDiagram
from .theme import (ACCENT, BAD, BORDER, CARD, OK, TEXT, TEXT_DIM, TEXT_MID,
                    WARN)


# =====================================================================
# 报告输出工具（各页共用）
# =====================================================================

DOC_FOOTER_DEFAULT = """标准依据
  GB/T 11361  同步带传动 梯形齿带轮
  GB/T 11616  同步带 尺寸系列
  ISO 5294 / ISO 5296   同步带与带轮国际系列
  GB/T 1357   渐开线圆柱齿轮 模数
  GB/T 10095  渐开线圆柱齿轮 精度制
  机械设计手册 / 米思米 · 盖茨 · 优霓塔样本（带轮最小齿数、节顶距取值）

免责声明
  本报告由程序按上述标准的通用工程取值自动生成，用于方案比选与初步设计。
  正式投产前请以最新版标准原文、供应商样本实测数据以及样机验证结果复核，
  尤其是涉及高速、重载、有安全强制要求的场合。"""


def report_text(title: str, meta: list[tuple[str, str]],
                sections: list[tuple[str, list[tuple[str, str]]]],
                warnings: list[str], notes: list[str]) -> str:
    L = ["=" * 64, f"        {title}", "=" * 64]
    L.append(f"生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    for k, v in meta:
        L.append(f"{k}：{v}")
    n = 0
    for sec_title, rows in sections:
        n += 1
        L.append("")
        L.append(f"【{sec_title}】")
        for k, v in rows:
            L.append(f"  {k}：{v}")
    L.append("")
    L.append("【校核结论】")
    if warnings:
        for w in warnings:
            L.append(f"  ⚠ {w}")
    else:
        L.append("  ✓ 各项校核均在推荐范围内。")
    for nt in notes:
        L.append(f"  · {nt}")
    L.append("")
    L.append("-" * 64)
    L.append(DOC_FOOTER_DEFAULT)
    return "\n".join(L)


def report_html(title: str, meta: list[tuple[str, str]],
                sections: list[tuple[str, list[tuple[str, str]]]],
                warnings: list[str], notes: list[str]) -> str:
    esc = html.escape

    def tbl(rows):
        return "<table>" + "".join(
            f"<tr><td class='k'>{esc(k)}</td><td class='v'>{esc(v)}</td></tr>"
            for k, v in rows) + "</table>"

    metas = "".join(f"<tr><td class='k'>{esc(k)}</td><td class='v'>{esc(v)}</td></tr>"
                    for k, v in meta)
    body = "".join(f"<h2>{i}. {esc(t)}</h2>{tbl(rows)}"
                   for i, (t, rows) in enumerate(sections, start=1))
    warn = "".join(f"<li class='w'>{esc(w)}</li>" for w in warnings) \
        or "<li class='o'>各项校核均在推荐范围内，设计可用。</li>"
    notes_html = f"<ul>{''.join(f'<li>{esc(n)}</li>' for n in notes)}</ul>" if notes else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>
 body {{ font-family:"Microsoft YaHei","Segoe UI",sans-serif; color:#1F2933;
        max-width:900px; margin:36px auto; padding:0 22px; line-height:1.7; }}
 h1 {{ font-size:22px; border-bottom:2px solid #2F6FED; padding-bottom:10px; }}
 h2 {{ font-size:15px; color:#2F6FED; margin-top:26px;
       border-left:3px solid #2F6FED; padding-left:9px; }}
 table {{ width:100%; border-collapse:collapse; margin:8px 0; font-size:13.5px; }}
 td {{ border:1px solid #E3E7ED; padding:7px 11px; }}
 td.k {{ background:#F7F9FC; width:44%; color:#4A5A6A; }}
 td.v {{ font-weight:600; text-align:right; }}
 ul {{ padding-left:20px; }}
 li.w {{ color:#8A5A12; background:#FFF9F0; margin:5px 0; padding:6px 10px;
         border-radius:5px; list-style:none; }}
 li.o {{ color:#0B7A3C; background:#F1FBF5; padding:6px 10px; border-radius:5px;
         list-style:none; }}
 .meta td {{ font-weight:400; }}
 footer {{ margin-top:34px; padding-top:14px; border-top:1px solid #E3E7ED;
           color:#7A8794; font-size:11.5px; white-space:pre-wrap; }}
</style></head><body>
<h1>{esc(title)}</h1>
<p style="color:#7A8794;font-size:12.5px">生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}</p>
<table class="meta">{metas}</table>
{body}
<h2>校核结论</h2>
<ul>{warn}</ul>
{notes_html}
<footer>{esc(DOC_FOOTER_DEFAULT)}</footer>
</body></html>"""


def save_report(parent, title: str, default_name: str, meta, sections,
                warnings, notes):
    if not sections:
        QMessageBox.warning(parent, "无可导出内容", "请先完成一次有效计算。")
        return
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出设计报告",
        f"{default_name}_{datetime.datetime.now():%Y%m%d_%H%M}.html",
        "网页报告 (*.html);;文本文件 (*.txt)")
    if not path:
        return
    try:
        content = (report_text(title, meta, sections, warnings, notes)
                   if path.lower().endswith(".txt")
                   else report_html(title, meta, sections, warnings, notes))
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        QMessageBox.critical(parent, "写入失败", str(e))
        return
    QMessageBox.information(parent, "导出完成", f"报告已保存到：\n{path}")


# =====================================================================
# 基础控件（与家族成员同款）
# =====================================================================

class Card(QFrame):
    """带标题的白色卡片容器。"""

    def __init__(self, title: str = "", hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(8)
        if title:
            head = QHBoxLayout()
            head.setSpacing(8)
            lab = QLabel(title)
            lab.setObjectName("CardTitle")
            head.addWidget(lab)
            head.addStretch(1)
            if hint:
                h = QLabel(hint)
                h.setObjectName("CardHint")
                head.addWidget(h)
            outer.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        outer.addLayout(self.body)

    def add(self, w):
        self.body.addWidget(w)
        return w

    def add_layout(self, l):
        self.body.addLayout(l)
        return l


class MetricCard(QFrame):
    """大数字指标卡。"""

    def __init__(self, name: str, unit: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Metric")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.name = QLabel(name)
        self.name.setObjectName("MetricName")
        self.unit = QLabel(unit)
        self.unit.setObjectName("MetricUnit")
        top.addWidget(self.name)
        top.addStretch(1)
        top.addWidget(self.unit)
        self.value = QLabel("—")
        self.value.setObjectName("MetricValue")
        self.value.setStyleSheet(f"color:{TEXT};")
        self.note = QLabel("")
        self.note.setObjectName("MetricNote")
        lay.addLayout(top)
        lay.addWidget(self.value)
        lay.addWidget(self.note)

    def set(self, value: str, state: str = "ok", note: str = ""):
        color = {"ok": OK, "warn": WARN, "bad": BAD, "na": TEXT_DIM}[state]
        self.value.setText(value)
        self.value.setStyleSheet(f"color:{color};")
        self.note.setText(note)


class HintLabel(QLabel):
    """输入框下方的浅色说明行。"""

    def __init__(self, text: str = "", parent=None, indent: int = 112):
        super().__init__(text, parent)
        self.setObjectName("FieldHint")
        self.setWordWrap(True)
        self.setContentsMargins(indent, 0, 0, 0)


class NumberInput(QWidget):
    """一行数值输入：标签 + 输入框 + 单位。"""

    def __init__(self, label: str, unit: str = "", placeholder: str = "",
                 label_w: int = 104, tip: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        self.label.setFixedWidth(label_w)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumWidth(70)
        if tip:
            self.edit.setToolTip(tip)
            self.label.setToolTip(tip)
        self.unit = QLabel(unit)
        self.unit.setObjectName("FieldUnit")
        self.unit.setMinimumWidth(30)
        lay.addWidget(self.label)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.unit)

    def set_label(self, text: str):
        self.label.setText(text)

    def set_unit(self, text: str):
        self.unit.setText(text)

    def value(self):
        s = self.edit.text().strip().replace("，", "").replace(",", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            raise ValueError(f"「{self.label.text()}」不是有效数值：{s}")

    def set_value(self, v):
        self.edit.setText("" if v is None else f"{v:g}")

    def set_tip(self, tip: str):
        self.edit.setToolTip(tip)
        self.label.setToolTip(tip)

    def clear(self):
        self.edit.clear()

    def on_change(self, fn):
        self.edit.textChanged.connect(fn)


class ComboInput(QWidget):
    def __init__(self, label: str, items, label_w: int = 104, parent=None,
                 editable: bool = False, unit: str = ""):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.label = QLabel(label)
        self.label.setObjectName("FieldLabel")
        self.label.setFixedWidth(label_w)
        self.combo = QComboBox()
        self.combo.addItems(items)
        if editable:
            self.combo.setEditable(True)
            self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            self.combo.lineEdit().setPlaceholderText("选择或直接输入数值")
        self.unit = QLabel(unit)
        self.unit.setObjectName("FieldUnit")
        self.unit.setMinimumWidth(30)
        lay.addWidget(self.label)
        lay.addWidget(self.combo, 1)
        if unit:
            lay.addWidget(self.unit)

    def on_change(self, fn):
        self.combo.currentIndexChanged.connect(fn)

    def on_text_change(self, fn):
        self.combo.currentTextChanged.connect(fn)

    def current(self):
        return self.combo.currentText()

    def current_data(self):
        return self.combo.currentData()

    def set_tip(self, tip: str):
        self.combo.setToolTip(tip)
        self.label.setToolTip(tip)


class RowList(QWidget):
    """键值对列表。"""

    def __init__(self, parent=None, key_w: int = 104):
        super().__init__(parent)
        self.key_w = key_w
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(5)
        self.grid.setColumnStretch(0, 0)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnMinimumWidth(0, key_w)
        self._row = 0

    def clear(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._row = 0

    def add(self, key: str, value: str, bold=False, color=None):
        k = QLabel(key)
        k.setObjectName("RowKey")
        v = QLabel(value)
        v.setObjectName("RowVal")
        v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        v.setWordWrap(True)
        v.setMinimumWidth(40)
        v.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if color:
            v.setStyleSheet(f"color:{color};font-size:12px;font-weight:600;")
        elif bold:
            v.setStyleSheet(f"color:{TEXT};font-size:12.5px;font-weight:700;")
        self.grid.addWidget(k, self._row, 0)
        self.grid.addWidget(v, self._row, 1)
        self._row += 1

    def add_sep(self):
        f = QFrame()
        f.setObjectName("Divider")
        self.grid.addWidget(f, self._row, 0, 1, 2)
        self._row += 1

    def rows(self) -> list[tuple[str, str]]:
        out = []
        for i in range(self.grid.rowCount()):
            a = self.grid.itemAtPosition(i, 0)
            b = self.grid.itemAtPosition(i, 1)
            if not (a and b):
                continue
            aw, bw = a.widget(), b.widget()
            if isinstance(aw, QLabel) and isinstance(bw, QLabel):
                out.append((aw.text(), bw.text()))
        return out


class VerifyBox(QWidget):
    """校核结论区：自动排列 通过 / 警告 条目。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)

    def clear(self):
        while self.lay.count():
            it = self.lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

    def show_items(self, warnings: list[str], notes: list[str],
                   ok_text: str = "各项校核均在推荐范围内，设计可用。"):
        self.clear()
        if warnings:
            for w in warnings:
                self._add(w, "warn")
        else:
            self._add(ok_text, "ok")
        for n in notes:
            self._add(n, "warn")

    def _add(self, text: str, kind: str = "warn"):
        f = QFrame()
        f.setObjectName("OkItem" if kind == "ok" else "WarnItem")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(10, 7, 10, 7)
        ico = QLabel("✓" if kind == "ok" else "!")
        ico.setFixedWidth(16)
        ico.setStyleSheet(
            f"color:{OK if kind == 'ok' else WARN};font-weight:700;font-size:13px;")
        t = QLabel(text)
        t.setObjectName("OkText" if kind == "ok" else "WarnText")
        t.setWordWrap(True)
        lay.addWidget(ico, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(t, 1)
        self.lay.addWidget(f)


# =====================================================================
# 一、同步带传动页
# =====================================================================

class BeltPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._res = None
        self._sections: list = []

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)
        root.addWidget(self._build_input(), 0)

        right = QSplitter(Qt.Orientation.Vertical)
        right.setChildrenCollapsible(False)
        right.addWidget(self._build_diagram())
        right.addWidget(self._build_results())
        right.setSizes([330, 520])
        right.setHandleWidth(10)
        root.addWidget(right, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(240)
        self._timer.timeout.connect(self.recalc)
        self._wire()
        self._apply_defaults()
        self.recalc()

    def _apply_defaults(self):
        """预填参考表格里的 S8M 典型工况，打开即有完整结果可看。"""
        self.in_profile.combo.setCurrentText("S8M")
        self.in_z1.set_value(47)
        self.in_z2.set_value(47)
        self.in_zb.set_value(120)
        self._on_profile(0)

    # ---------------- 输入 ----------------
    def _build_input(self) -> QWidget:
        box = QWidget()
        box.setFixedWidth(400)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        sc = QVBoxLayout(inner)
        sc.setContentsMargins(0, 0, 6, 0)
        sc.setSpacing(10)

        # 齿形
        c0 = Card("齿形", "决定节距与节顶距")
        self.in_profile = ComboInput("齿形代号", [b["code"] for b in BELT_PROFILES])
        self.in_profile.set_tip("S 系列 / HTD / T 系列 / 英制梯形齿；"
                                "切换后自动带入节距与节顶距")
        self.lbl_profile = HintLabel("")
        c0.add(self.in_profile)
        c0.add(self.lbl_profile)
        sc.addWidget(c0)

        # 齿形参数（可覆盖）
        c1 = Card("齿形参数", "留空即为该齿形的标准值")
        self.in_p = NumberInput("节距 P", "mm", "自动")
        self.in_delta = NumberInput("节顶距 δ", "mm", "自动")
        self.in_delta.set_tip("齿顶圆相对节圆的单边缩减量：OD = PD − 2δ")
        c1.add(self.in_p)
        c1.add(self.in_delta)
        sc.addWidget(c1)

        # 带轮
        c2 = Card("带轮齿数")
        self.in_z1 = NumberInput("主动轮齿数 Z₁", "", "47")
        self.in_z2 = NumberInput("从动轮齿数 Z₂", "", "47")
        self.lbl_z = HintLabel("")
        c2.add(self.in_z1)
        c2.add(self.in_z2)
        c2.add(self.lbl_z)
        sc.addWidget(c2)

        # 带
        c3 = Card("同步带", "带齿数与中心距二选一")
        self.in_zb = NumberInput("带齿数 Zb", "", "120")
        self.in_cd = NumberInput("已知中心距 CD", "mm", "留空则不用")
        self.in_cd.set_tip("填写中心距后，程序反算所需带齿数并取整到标准带长，"
                           "同时给出实际中心距")
        self.lbl_belt = HintLabel("")
        c3.add(self.in_zb)
        c3.add(self.in_cd)
        c3.add(self.lbl_belt)
        sc.addWidget(c3)

        sc.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_calc = QPushButton("开始计算")
        self.btn_calc.setObjectName("Primary")
        self.btn_calc.setMinimumHeight(34)
        self.btn_calc.clicked.connect(self.recalc)
        self.btn_reset = QPushButton("重置")
        self.btn_reset.setMinimumHeight(34)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_export = QPushButton("导出报告")
        self.btn_export.setMinimumHeight(34)
        self.btn_export.clicked.connect(self._export)
        bar.addWidget(self.btn_calc, 2)
        bar.addWidget(self.btn_reset, 1)
        bar.addWidget(self.btn_export, 1)
        outer.addLayout(bar)
        return box

    def _build_diagram(self) -> QWidget:
        c = Card("传动示意")
        self.diagram = BeltDiagram()
        c.add(self.diagram)
        c.setMinimumHeight(250)
        return c

    def _build_results(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)

        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        self.m_i = MetricCard("传动比 i", "Z₂/Z₁")
        self.m_u = MetricCard("减速比 u", "Z₁/Z₂")
        self.m_theta = MetricCard("小轮包角", "°")
        self.m_zm = MetricCard("啮合齿数", "个")
        for m in (self.m_i, self.m_u, self.m_theta, self.m_zm):
            mrow.addWidget(m, 1)
        lay.addLayout(mrow)

        c1 = Card("带轮 1（主动）")
        self.row_p1 = RowList()
        c1.add(self.row_p1)
        lay.addWidget(c1)

        c2 = Card("带轮 2（从动）")
        self.row_p2 = RowList()
        c2.add(self.row_p2)
        lay.addWidget(c2)

        c3 = Card("同步带与中心距")
        self.row_b = RowList()
        c3.add(self.row_b)
        lay.addWidget(c3)

        c4 = Card("校核结论")
        self.verify = VerifyBox()
        c4.body.addWidget(self.verify)
        lay.addWidget(c4)

        lay.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    # ---------------- 交互 ----------------
    def _wire(self):
        for w in (self.in_p, self.in_delta, self.in_z1, self.in_z2,
                  self.in_zb, self.in_cd):
            w.on_change(lambda _t: self._timer.start())
        self.in_profile.on_change(self._on_profile)

    def _on_profile(self, _i):
        b = belt_profile(self.in_profile.current())
        self.in_p.clear()
        self.in_delta.clear()
        self.lbl_profile.setText(
            f"{b['code']}：节距 P = {b['p']:g} mm，节顶距 δ = {b['delta']:g} mm，"
            f"{b['family']}；推荐最少带轮齿数 {min_teeth(b['code'])} 齿。")
        self._timer.start()

    def _reset(self):
        for w in (self.in_p, self.in_delta, self.in_z1, self.in_z2,
                  self.in_zb, self.in_cd):
            w.clear()
        self.in_profile.combo.setCurrentIndex(0)
        self._on_profile(0)
        self.recalc()

    # ---------------- 计算 ----------------
    def recalc(self):
        try:
            r = design_belt(
                profile_code=self.in_profile.current(),
                z1=self.in_z1.value() or 47.0,
                z2=self.in_z2.value() or 47.0,
                belt_teeth=self.in_zb.value(),
                p=self.in_p.value(),
                delta=self.in_delta.value(),
                center_distance=self.in_cd.value(),
            )
        except (DesignError, ValueError) as e:
            self._show_error(str(e))
            return
        self._res = r
        self._fill(r)

    def _show_error(self, msg: str):
        self._res = None
        for m in (self.m_i, self.m_u, self.m_theta, self.m_zm):
            m.set("—", "na", "")
        for rl in (self.row_p1, self.row_p2, self.row_b):
            rl.clear()
        self.row_p1.add("提示", msg, color=BAD)
        self.verify.clear()
        self.verify._add(msg, "warn")
        self.diagram.set_result(None)
        self.lbl_belt.setText("")
        self._sections = []

    def _fill(self, r):
        A, B, bl, g, m = r["pulley1"], r["pulley2"], r["belt"], r["geom"], r["metrics"]

        self.m_i.set(f"{m['i']:.4f}", "ok", "等速" if abs(m["i"] - 1) < 1e-9 else "有速比")
        self.m_u.set(f"{m['u']:.4f}", "ok", "Z₁/Z₂")
        st = "ok" if m["theta"] >= 120 else "warn"
        self.m_theta.set(f"{m['theta']:.1f}", st, "建议 ≥ 120°")
        st = "ok" if m["mesh_teeth"] >= 6 else "bad"
        self.m_zm.set(f"{m['mesh_teeth']:.2f}", st, "建议 ≥ 6")

        rw = self.row_p1
        rw.clear()
        rw.add("齿数 Z₁", f"{A['z']:.0f} 齿", bold=True)
        rw.add("节圆直径 PD₁", f"{A['pd']:.3f} mm", bold=True)
        rw.add("齿顶圆直径 OD₁", f"{A['od']:.3f} mm", bold=True)
        rw.add("齿根圆直径（估算）", f"{A['df']:.3f} mm", color=TEXT_DIM)
        rw.add("节圆周长", f"{A['circumference']:.3f} mm")
        rw.add_sep()
        rw.add("推荐最少齿数", f"{m['min_teeth']} 齿",
               color=OK if A["z"] >= m["min_teeth"] else BAD)

        rw = self.row_p2
        rw.clear()
        rw.add("齿数 Z₂", f"{B['z']:.0f} 齿", bold=True)
        rw.add("节圆直径 PD₂", f"{B['pd']:.3f} mm", bold=True)
        rw.add("齿顶圆直径 OD₂", f"{B['od']:.3f} mm", bold=True)
        rw.add("齿根圆直径（估算）", f"{B['df']:.3f} mm", color=TEXT_DIM)
        rw.add("节圆周长", f"{B['circumference']:.3f} mm")
        rw.add_sep()
        rw.add("两轮节圆直径差", f"{abs(B['pd'] - A['pd']):.3f} mm")
        rw.add("节圆直径比", f"{m['speed_ratio']:.4f}")

        rw = self.row_b
        rw.clear()
        rw.add("带齿数 Zb", f"{bl['teeth']:.0f} 齿", bold=True)
        rw.add("带长 L = Zb·P", f"{bl['length']:.3f} mm", bold=True)
        rw.add("带圆形直径 L/π", f"{bl['circle_dia']:.3f} mm")
        rw.add_sep()
        rw.add("中心距 CD（简化式）", f"{g['cd']:.3f} mm", bold=True)
        rw.add("中心距（精确解）", f"{g['cd_exact']:.3f} mm", color=ACCENT, bold=True)
        rw.add("两轮中心理论最小距", f"{g['cd_a_ref']:.3f} mm", color=TEXT_DIM)
        rw.add_sep()
        rw.add("小轮包角 θ", f"{g['wrap_angle']:.2f} °")
        rw.add("小轮啮合齿数 Zm", f"{g['mesh_teeth']:.2f} 个")
        if r["reverse"]:
            rv = r["reverse"]
            rw.add_sep()
            rw.add("按中心距反算带齿数", f"{rv['zb_ideal']:.3f} → 取 {rv['zb_std']:.0f} 齿",
                   color=ACCENT)
            rw.add("取整后实际中心距", f"{rv['cd_at_std']:.3f} mm")

        self.lbl_z.setText(
            f"最少齿数校验：{min(m['min_teeth'], 9999)} 齿为 {r['input']['profile']} "
            f"的推荐下限，当前小轮 {min(A['z'], B['z']):.0f} 齿。")
        self.lbl_belt.setText(
            f"当前带长 {bl['length']:.1f} mm，中心距 {g['cd']:.2f} mm"
            + ("；中心距由带齿数正向计算。" if not r["reverse"]
               else "；带齿数由中心距反算。"))

        self.verify.show_items(r["warnings"], r["notes"])
        self.diagram.set_result(r)

        self._sections = [
            ("一、齿形与输入", [
                ("齿形代号", r["input"]["profile"]),
                ("节距 P", f"{r['input']['p']:g} mm"),
                ("节顶距 δ", f"{r['input']['delta']:.4f} mm"),
                ("主动轮齿数 Z₁", f"{r['input']['z1']:.0f}"),
                ("从动轮齿数 Z₂", f"{r['input']['z2']:.0f}"),
                ("带齿数 Zb", f"{r['input']['belt_teeth']:.0f}"),
            ]),
            ("二、带轮 1（主动）", self.row_p1.rows()),
            ("三、带轮 2（从动）", self.row_p2.rows()),
            ("四、同步带与中心距", self.row_b.rows()),
        ]

    def _export(self):
        save_report(self, "同步带传动设计计算报告", "同步带传动设计报告",
                    [("齿形", self.in_profile.current()),
                     ("带轮 1 齿数", str(int(self.in_z1.value() or 0))),
                     ("带轮 2 齿数", str(int(self.in_z2.value() or 0)))],
                    self._sections,
                    self._res["warnings"] if self._res else [],
                    self._res["notes"] if self._res else [])


# =====================================================================
# 二、齿轮传动页
# =====================================================================

class GearPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._res = None
        self._sections: list = []

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)
        root.addWidget(self._build_input(), 0)

        right = QSplitter(Qt.Orientation.Vertical)
        right.setChildrenCollapsible(False)
        right.addWidget(self._build_diagram())
        right.addWidget(self._build_results())
        right.setSizes([300, 560])
        right.setHandleWidth(10)
        root.addWidget(right, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(240)
        self._timer.timeout.connect(self.recalc)
        self._wire()
        self._apply_defaults()
        self.recalc()

    def _apply_defaults(self):
        """预填 2526 齿轮方案的典型参数。"""
        self.in_m.combo.setCurrentText("2")
        self.in_alpha.combo.setCurrentText("20")
        self.in_z1.set_value(17)
        self.in_z2.set_value(51)
        self.in_x1.set_value(0)
        self.in_x2.set_value(0)
        self.in_beta.set_value(0)

    def _build_input(self) -> QWidget:
        box = QWidget()
        box.setFixedWidth(400)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        sc = QVBoxLayout(inner)
        sc.setContentsMargins(0, 0, 6, 0)
        sc.setSpacing(10)

        c0 = Card("基本参数")
        self.in_m = ComboInput("模数 m", [], editable=True, unit="mm")
        for v in MODULES_ALL:
            self.in_m.combo.addItem(f"{v:g}", v)
        self.in_m.combo.setCurrentText("2")
        self.in_m.set_tip(f"GB/T 1357 标准模数系列（{MODULE_MIN:g} ~ {MODULE_MAX:g} mm），"
                          f"可直接输入非标模数")
        self.in_alpha = ComboInput("压力角 α", [f"{a:g}" for a in PRESSURE_ANGLES],
                                   unit="°")
        self.in_alpha.combo.setCurrentText("20")
        self.in_beta = NumberInput("螺旋角 β", "°", "0（直齿）")
        self.in_beta.set_tip("0 为直齿；斜齿的轴向力随 β 增大，请核对轴承")
        self.lbl_m = HintLabel("")
        c0.add(self.in_m)
        c0.add(self.in_alpha)
        c0.add(self.in_beta)
        c0.add(self.lbl_m)
        sc.addWidget(c0)

        c1 = Card("齿轮 1（主动）")
        self.in_z1 = NumberInput("齿数 Z₁", "", "17")
        self.in_x1 = NumberInput("变位系数 x₁", "", "0")
        self.lbl_g1 = HintLabel("")
        c1.add(self.in_z1)
        c1.add(self.in_x1)
        c1.add(self.lbl_g1)
        sc.addWidget(c1)

        c2 = Card("齿轮 2（从动）")
        self.in_z2 = NumberInput("齿数 Z₂", "", "51")
        self.in_x2 = NumberInput("变位系数 x₂", "", "0")
        self.lbl_g2 = HintLabel("")
        c2.add(self.in_z2)
        c2.add(self.in_x2)
        c2.add(self.lbl_g2)
        sc.addWidget(c2)

        presets = Card("常用配对速选")
        row = QHBoxLayout()
        row.setSpacing(6)
        for z1, z2 in ((15, 59), (17, 51), (20, 51), (23, 14), (31, 18), (18, 11)):
            b = QPushButton(f"{z1}/{z2}")
            b.setObjectName("Mini")
            b.setToolTip(f"一键设为 Z₁={z1}，Z₂={z2}")
            b.clicked.connect(lambda _c, a=z1, b2=z2: self._preset(a, b2))
            row.addWidget(b)
        presets.body.addLayout(row)
        sc.addWidget(presets)

        sc.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_calc = QPushButton("开始计算")
        self.btn_calc.setObjectName("Primary")
        self.btn_calc.setMinimumHeight(34)
        self.btn_calc.clicked.connect(self.recalc)
        self.btn_reset = QPushButton("重置")
        self.btn_reset.setMinimumHeight(34)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_export = QPushButton("导出报告")
        self.btn_export.setMinimumHeight(34)
        self.btn_export.clicked.connect(self._export)
        bar.addWidget(self.btn_calc, 2)
        bar.addWidget(self.btn_reset, 1)
        bar.addWidget(self.btn_export, 1)
        outer.addLayout(bar)
        return box

    def _build_diagram(self) -> QWidget:
        c = Card("啮合示意")
        self.diagram = GearDiagram()
        c.add(self.diagram)
        c.setMinimumHeight(268)
        return c

    def _build_results(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)

        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        self.m_i = MetricCard("传动比 i", "Z₁/Z₂")
        self.m_u = MetricCard("减速比 u", "Z₂/Z₁")
        self.m_a = MetricCard("中心距 a", "mm")
        self.m_aw = MetricCard("啮合角 αw", "°")
        for m in (self.m_i, self.m_u, self.m_a, self.m_aw):
            mrow.addWidget(m, 1)
        lay.addLayout(mrow)

        c1 = Card("齿轮 1（主动）几何")
        self.row_g1 = RowList()
        c1.add(self.row_g1)
        lay.addWidget(c1)

        c2 = Card("齿轮 2（从动）几何")
        self.row_g2 = RowList()
        c2.add(self.row_g2)
        lay.addWidget(c2)

        c3 = Card("齿轮副啮合")
        self.row_pair = RowList()
        c3.add(self.row_pair)
        lay.addWidget(c3)

        c4 = Card("校核结论")
        self.verify = VerifyBox()
        c4.body.addWidget(self.verify)
        lay.addWidget(c4)

        lay.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    def _wire(self):
        for w in (self.in_beta, self.in_z1, self.in_x1, self.in_z2, self.in_x2):
            w.on_change(lambda _t: self._timer.start())
        self.in_m.on_text_change(self._on_m)
        self.in_alpha.on_text_change(lambda _t: self._timer.start())

    def _on_m(self, _t):
        try:
            v = self._read_m()
            near = min(MODULES_ALL, key=lambda a: abs(a - v))
            if abs(near - v) > 1e-6:
                self.lbl_m.setText(f"m = {v:g} 非 GB/T 1357 标准值，最接近 "
                                   f"{near:g}（非标模数需定制滚刀）")
            else:
                s = "第一系列" if near in MODULE_FIRST else "第二系列"
                self.lbl_m.setText(f"m = {v:g} mm，GB/T 1357 {s}")
        except Exception:
            self.lbl_m.setText("")
        self._timer.start()

    def _read_m(self) -> float:
        s = self.in_m.current().strip().replace("，", "").replace(",", "")
        head = s.replace("　", " ").split()[0] if s else ""
        if not head:
            raise DesignError("请填写模数")
        try:
            return float(head)
        except ValueError:
            d = self.in_m.current_data()
            if d is not None:
                return float(d)
            raise DesignError(f"模数「{s}」不是有效数值")

    def _preset(self, z1: int, z2: int):
        self.in_z1.set_value(z1)
        self.in_z2.set_value(z2)
        self.recalc()

    def _reset(self):
        for w in (self.in_x1, self.in_x2, self.in_beta):
            w.clear()
        self.in_z1.set_value(17)
        self.in_z2.set_value(51)
        self.in_m.combo.setCurrentText("2")
        self.in_alpha.combo.setCurrentText("20")
        self.recalc()

    def recalc(self):
        try:
            r = design_gears(
                z1=self.in_z1.value() or 17.0,
                z2=self.in_z2.value() or 51.0,
                mn=self._read_m(),
                alpha_deg=float(self.in_alpha.current() or 20),
                beta_deg=self.in_beta.value() or 0.0,
                x1=self.in_x1.value() or 0.0,
                x2=self.in_x2.value() or 0.0,
            )
        except (DesignError, ValueError) as e:
            self._show_error(str(e))
            return
        self._res = r
        self._fill(r)

    def _show_error(self, msg: str):
        self._res = None
        for m in (self.m_i, self.m_u, self.m_a, self.m_aw):
            m.set("—", "na", "")
        for rl in (self.row_g1, self.row_g2, self.row_pair):
            rl.clear()
        self.row_g1.add("提示", msg, color=BAD)
        self.verify.clear()
        self.verify._add(msg, "warn")
        self.diagram.set_result(None)
        self._sections = []

    @staticmethod
    def _geo_rows(g) -> list[tuple[str, str]]:
        return [
            ("齿数 Z", f"{g['z']:.0f} 齿"),
            ("分度圆直径 d", f"{g['d']:.4f} mm"),
            ("齿顶圆直径 da", f"{g['da']:.4f} mm"),
            ("齿根圆直径 df", f"{g['df']:.4f} mm"),
            ("基圆直径 db", f"{g['db']:.4f} mm"),
            ("齿顶高 ha", f"{g['ha']:.4f} mm"),
            ("齿根高 hf", f"{g['hf']:.4f} mm"),
            ("全齿高 h", f"{g['h']:.4f} mm"),
            ("法向齿距 pn", f"{g['p']:.4f} mm"),
            ("端面齿厚 st", f"{g['st']:.4f} mm"),
        ]

    def _fill(self, r):
        gp, m = r["pair"], r["metrics"]
        g1, g2 = gp["g1"], gp["g2"]

        st = "warn" if gp["a"] < gp["a_std"] - 1e-6 else "ok"
        self.m_i.set(f"{m['i']:.4f}", "ok",
                     "减速" if m["i"] < 1 else ("增速" if m["i"] > 1 else "等速"))
        self.m_u.set(f"{m['u']:.4f}", "ok",
                     "各级齿数：" + f"{g1['z']:.0f} / {g2['z']:.0f}")
        self.m_a.set(f"{m['a']:.3f}", st, f"标准 {m['a_std']:.3f} mm")
        self.m_aw.set(f"{m['alpha_w']:.3f}", "ok",
                      "标准 20°" if abs(m["alpha_w"] - 20) < 1e-6 else "变位啮合角")

        rw = self.row_g1
        rw.clear()
        for k, v in self._geo_rows(g1):
            rw.add(k, v, bold=k.startswith(("分度圆", "齿顶圆", "齿根圆")))
        rw.add_sep()
        rw.add("变位系数 x₁", f"{g1['x']:.4f}")
        rw.add("不根切最小变位", f"{g1['xmin']:.4f}",
               color=OK if not g1["undercut"] else BAD)
        rw.add("不根切最小齿数", f"{g1['zmin']:.2f}")

        rw = self.row_g2
        rw.clear()
        for k, v in self._geo_rows(g2):
            rw.add(k, v, bold=k.startswith(("分度圆", "齿顶圆", "齿根圆")))
        rw.add_sep()
        rw.add("变位系数 x₂", f"{g2['x']:.4f}")
        rw.add("不根切最小变位", f"{g2['xmin']:.4f}",
               color=OK if not g2["undercut"] else BAD)

        rw = self.row_pair
        rw.clear()
        rw.add("传动比 i = Z₁/Z₂", f"{m['i']:.6f}", bold=True, color=ACCENT)
        rw.add("减速比 u = Z₂/Z₁", f"{m['u']:.6f}", bold=True, color=ACCENT)
        rw.add_sep()
        rw.add("标准中心距", f"{m['a_std']:.4f} mm")
        rw.add("实际中心距 a", f"{m['a']:.4f} mm", bold=True)
        rw.add("中心距变动量", f"{m['center_shift']:+.4f} mm",
               color=OK if abs(m["center_shift"]) < 1e-6 else WARN)
        rw.add("啮合角 αw", f"{m['alpha_w']:.4f} °")
        rw.add_sep()
        rw.add("两轮齿数之和", f"{g1['z'] + g2['z']:.0f}")
        rw.add("模数", f"{g1['mn']:g} mm")
        rw.add("压力角", f"{g1['alpha']:g} °")
        rw.add("螺旋角", f"{g1['beta']:g} °")

        self.lbl_g1.setText(f"不根切最小齿数 {g1['zmin']:.1f}；"
                            f"当前 z={g1['z']:.0f}"
                            + ("，需变位" if g1["undercut"] else "，无需变位"))
        self.lbl_g2.setText(f"不根切最小齿数 {g2['zmin']:.1f}；"
                            f"当前 z={g2['z']:.0f}"
                            + ("，需变位" if g2["undercut"] else "，无需变位"))

        self.verify.show_items(r["warnings"], r["notes"])
        self.diagram.set_result(r)

        self._sections = [
            ("一、输入参数", [
                ("模数 m", f"{g1['mn']:g} mm"),
                ("压力角 α", f"{g1['alpha']:g} °"),
                ("螺旋角 β", f"{g1['beta']:g} °"),
                ("主动轮齿数 Z₁", f"{g1['z']:.0f}"),
                ("从动轮齿数 Z₂", f"{g2['z']:.0f}"),
                ("变位系数 x₁ / x₂", f"{g1['x']:g} / {g2['x']:g}"),
            ]),
            ("二、齿轮 1（主动）几何", self.row_g1.rows()),
            ("三、齿轮 2（从动）几何", self.row_g2.rows()),
            ("四、齿轮副啮合", self.row_pair.rows()),
        ]

    def _export(self):
        save_report(self, "齿轮传动设计计算报告", "齿轮传动设计报告",
                    [("模数", self.in_m.current()),
                     ("齿数 Z₁ / Z₂", f"{self.in_z1.value()} / {self.in_z2.value()}")],
                    self._sections,
                    self._res["warnings"] if self._res else [],
                    self._res["notes"] if self._res else [])


# =====================================================================
# 三、传动链与整机速度页
# =====================================================================

_COLS = ["级", "类型", "名称", "主动侧 Z₁", "从动侧 Z₂", "模数 m / 节距 P",
         "单级 i"]


def _default_stages() -> list[dict]:
    """默认载入参考表格 2526 方案的传动链。"""
    return [
        {"kind": "gear", "name": "主动轮过渡", "z1": 17, "z2": 20, "m": 2.0},
        {"kind": "gear", "name": "主动轮", "z1": 20, "z2": 51, "m": 2.0},
        {"kind": "belt", "name": "履带", "z1": 47, "z2": 47, "p": 8.0,
         "p_code": "S8M"},
        {"kind": "gear", "name": "滚刷过渡", "z1": 31, "z2": 18, "m": 1.5},
        {"kind": "gear", "name": "滚刷", "z1": 18, "z2": 11, "m": 1.5},
    ]


class ChainPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stages = _default_stages()
        self._chain = None
        self._sys = None
        self._loading = False

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)
        root.addWidget(self._build_input(), 0)
        root.addWidget(self._build_results(), 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(240)
        self._timer.timeout.connect(self.recalc)
        self._apply_defaults()
        self._rebuild_table()
        self.recalc()

    def _apply_defaults(self):
        """预填一套可跑通的整机参数（行走 150 mm/s 的履带机器）。"""
        self.in_v.set_value(150)
        self.in_rw.set_value(65.36)
        self.in_rb.set_value(39.5)
        self.in_unit.combo.setCurrentText("mm/s")

    # ---------------- 输入 ----------------
    def _build_input(self) -> QWidget:
        box = QWidget()
        box.setFixedWidth(540)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        c0 = Card("传动链", "每行一级，串联累计")
        btn = QHBoxLayout()
        btn.setSpacing(6)
        b1 = QPushButton("+ 齿轮级")
        b1.setObjectName("Mini")
        b1.clicked.connect(lambda: self._add("gear"))
        b2 = QPushButton("+ 同步带级")
        b2.setObjectName("Mini")
        b2.clicked.connect(lambda: self._add("belt"))
        b3 = QPushButton("删除末级")
        b3.setObjectName("Mini")
        b3.clicked.connect(self._del_last)
        b4 = QPushButton("还原示例")
        b4.setObjectName("Mini")
        b4.clicked.connect(self._restore)
        for b in (b1, b2, b3, b4):
            btn.addWidget(b)
        c0.body.addLayout(btn)

        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hh = self.table.horizontalHeader()
        # 类型列放的是 QComboBox，ResizeToContents 会算成 0 宽，必须给定宽
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for i in (3, 4, 5, 6):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 84)
        for i, w in ((3, 64), (4, 64), (5, 76), (6, 64)):
            self.table.setColumnWidth(i, w)
        self.table.itemChanged.connect(self._on_item)
        c0.body.addWidget(self.table)
        hint = QLabel("「模数 m / 节距 P」列：齿轮级填模数（mm），同步带级填节距（mm）。"
                      "「单级 i」为只读自动计算；减速比 u = 1/i 见下方明细表。")
        hint.setObjectName("CardHint")
        hint.setWordWrap(True)
        c0.body.addWidget(hint)
        outer.addWidget(c0)

        c1 = Card("驱动轮", "履带驱动轮 / 行走轮")
        self.in_v = NumberInput("行走速度 v", "", "150")
        self.in_unit = ComboInput("速度单位", ["mm/s", "m/min", "km/h"])
        self.in_unit.combo.setCurrentText("mm/s")
        self.in_rw = NumberInput("驱动轮半径 R", "mm", "65.36")
        self.lbl_v = HintLabel("")
        c1.add(self.in_v)
        c1.add(self.in_unit)
        c1.add(self.in_rw)
        c1.add(self.lbl_v)
        outer.addWidget(c1)

        c2 = Card("执行机构（滚刷 / 输送等）")
        self.in_rb = NumberInput("执行机构半径", "mm", "39.5")
        self.in_idrv = NumberInput("驱动轮前累计 i", "", "自动")
        self.in_idrv.set_tip("电机到驱动轮之间的累计传动比（输出/输入）。"
                             "留空 = 自动取传动链中第一个同步带级之前的齿轮级累计")
        self.in_ibrush = NumberInput("执行机构累计 i", "", "自动")
        self.in_ibrush.set_tip("电机到执行机构之间的累计传动比。留空 = 取整条链的累计")
        c2.add(self.in_rb)
        c2.add(self.in_idrv)
        c2.add(self.in_ibrush)
        outer.addWidget(c2)

        outer.addStretch(1)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_calc = QPushButton("开始计算")
        self.btn_calc.setObjectName("Primary")
        self.btn_calc.setMinimumHeight(34)
        self.btn_calc.clicked.connect(self.recalc)
        self.btn_export = QPushButton("导出报告")
        self.btn_export.setMinimumHeight(34)
        self.btn_export.clicked.connect(self._export)
        bar.addWidget(self.btn_calc, 2)
        bar.addWidget(self.btn_export, 1)
        outer.addLayout(bar)
        return box

    def _build_results(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)

        c0 = Card("传动链框图")
        self.diagram = ChainDiagram()
        c0.add(self.diagram)
        lay.addWidget(c0)

        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        self.m_it = MetricCard("累计传动比 i", "")
        self.m_ut = MetricCard("累计减速比 u", "")
        self.m_rw = MetricCard("驱动轮转速", "r/min")
        self.m_rm = MetricCard("驱动电机转速", "r/min")
        for m in (self.m_it, self.m_ut, self.m_rw, self.m_rm):
            mrow.addWidget(m, 1)
        lay.addLayout(mrow)

        c1 = Card("各级传动明细")
        self.tbl_detail = QTableWidget(0, 7)
        self.tbl_detail.setHorizontalHeaderLabels(
            ["级", "名称", "类型", "Z₁", "Z₂", "单级 i", "累计 i"])
        self.tbl_detail.verticalHeader().setVisible(False)
        self.tbl_detail.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_detail.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        hh = self.tbl_detail.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in (0, 2, 3, 4, 5, 6):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        c1.body.addWidget(self.tbl_detail)
        lay.addWidget(c1)

        c2 = Card("执行机构速度")
        self.row_sys = RowList(key_w=140)
        c2.add(self.row_sys)
        lay.addWidget(c2)

        c3 = Card("校核结论")
        self.verify = VerifyBox()
        c3.body.addWidget(self.verify)
        lay.addWidget(c3)

        lay.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    # ---------------- 表格编辑 ----------------
    def _rebuild_table(self):
        self._loading = True
        try:
            self.table.setRowCount(len(self._stages))
            for i, st in enumerate(self._stages):
                self._fill_row(i, st)
        finally:
            self._loading = False
        self._fit_height(self.table)

    def _fill_row(self, i: int, st: dict):
        # 级序
        it = QTableWidgetItem(str(i + 1))
        it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(i, 0, it)

        # 类型
        cb = QComboBox()
        cb.addItems(["齿轮级", "同步带级"])
        cb.setCurrentIndex(0 if st.get("kind", "gear") == "gear" else 1)
        cb.currentIndexChanged.connect(
            lambda _idx, r=i: self._on_kind(r))
        self.table.setCellWidget(i, 1, cb)

        for col, key, val in ((2, "name", st.get("name", "")),
                              (3, "z1", st.get("z1")),
                              (4, "z2", st.get("z2"))):
            c = QTableWidgetItem("" if val is None else str(val))
            c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, col, c)

        if st.get("kind", "gear") == "belt":
            pv = st.get("p", 8.0)
        else:
            pv = st.get("m", 2.0)
        c = QTableWidgetItem(f"{pv:g}")
        c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(i, 5, c)

        # 只读结果列
        c = QTableWidgetItem("—")
        c.setFlags(Qt.ItemFlag.ItemIsEnabled)
        c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(i, 6, c)

    @staticmethod
    def _fit_height(tbl: QTableWidget, extra: int = 6):
        """把表格高度收紧到恰好容纳全部行，避免出现半截行。"""
        h = tbl.horizontalHeader().height()
        for i in range(tbl.rowCount()):
            h += tbl.rowHeight(i)
        tbl.setFixedHeight(max(76, h + extra))

    def _on_kind(self, row: int):
        if self._loading or row >= len(self._stages):
            return
        cb = self.table.cellWidget(row, 1)
        kind = "gear" if cb.currentIndex() == 0 else "belt"
        st = self._stages[row]
        st["kind"] = kind
        if kind == "belt":
            st.setdefault("p", 8.0)
            st.setdefault("p_code", "S8M")
            c = self.table.item(row, 5)
            if c is None or not c.text().strip():
                self.table.setItem(row, 5, QTableWidgetItem("8"))
            if not st.get("name"):
                st["name"] = "同步带级"
        else:
            st.setdefault("m", 2.0)
        self.recalc()

    def _on_item(self, item: QTableWidgetItem):
        if self._loading:
            return
        r, c = item.row(), item.column()
        if r >= len(self._stages) or c not in (2, 3, 4, 5):
            return
        st = self._stages[r]
        txt = item.text().strip().replace("，", "").replace(",", "")
        if c == 2:
            st["name"] = txt or f"第 {r + 1} 级"
        elif c in (3, 4):
            try:
                v = float(txt)
                if v <= 0:
                    raise ValueError
            except ValueError:
                item.setBackground(QColor("#FFF1F1"))
                return
            item.setBackground(QColor(CARD))
            st["z1" if c == 3 else "z2"] = v
        else:
            try:
                v = float(txt)
                if v <= 0:
                    raise ValueError
            except ValueError:
                item.setBackground(QColor("#FFF1F1"))
                return
            item.setBackground(QColor(CARD))
            if st.get("kind", "gear") == "belt":
                st["p"] = v
            else:
                st["m"] = v
        self._timer.start()

    def _add(self, kind: str):
        if len(self._stages) >= 12:
            QMessageBox.information(self, "数量上限", "传动级最多 12 级。")
            return
        n = len(self._stages) + 1
        if kind == "belt":
            self._stages.append({"kind": "belt", "name": f"同步带级 {n}",
                                 "z1": 47, "z2": 47, "p": 8.0, "p_code": "S8M"})
        else:
            self._stages.append({"kind": "gear", "name": f"齿轮级 {n}",
                                 "z1": 20, "z2": 20, "m": 2.0})
        self._rebuild_table()
        self.recalc()

    def _del_last(self):
        if len(self._stages) <= 1:
            QMessageBox.information(self, "至少一级", "传动链至少保留一级。")
            return
        self._stages.pop()
        self._rebuild_table()
        self.recalc()

    def _restore(self):
        self._stages = _default_stages()
        self._rebuild_table()
        self.recalc()

    # ---------------- 计算 ----------------
    def recalc(self):
        try:
            ch = chain_compute(self._stages)
        except (DesignError, ValueError, KeyError) as e:
            self._show_error(str(e))
            return

        # 自动 i：驱动轮 = 第一个同步带级之前的齿轮级累计；执行机构 = 整链累计
        i_drv_auto = self._auto_drive_ratio(ch)
        i_brush_auto = ch["i_total"]

        v = self.in_v.value()
        rw = self.in_rw.value()
        rb = self.in_rb.value()
        i_drv = self.in_idrv.value()
        i_br = self.in_ibrush.value()

        sysres = None
        if v is not None and rw:
            try:
                sysres = system_compute(
                    v=v, unit=self.in_unit.current(), wheel_radius=rw,
                    i_drive=(i_drv if i_drv else i_drv_auto) or 1.0,
                    brush_radius=rb or 0.0,
                    i_brush_from_wheel=(
                        ((i_br if i_br else i_brush_auto) /
                         ((i_drv if i_drv else i_drv_auto) or 1.0))
                        if rb else 0.0))
            except (DesignError, ValueError):
                sysres = None

        self._chain = ch
        self._sys = sysres
        self._fill(ch, sysres, i_drv_auto, i_brush_auto)

    @staticmethod
    def _auto_drive_ratio(ch: dict) -> float:
        """第一个同步带级之前（不含该级）的齿轮级累计传动比。"""
        acc = 1.0
        for st in ch["stages"]:
            if st["kind"] == "belt":
                return acc
            acc *= st["i"]
        return acc

    def _show_error(self, msg: str):
        self._chain = None
        self._sys = None
        for m in (self.m_it, self.m_ut, self.m_rw, self.m_rm):
            m.set("—", "na", "")
        self.tbl_detail.setRowCount(0)
        self.row_sys.clear()
        self.row_sys.add("提示", msg, color=BAD)
        self.verify.clear()
        self.verify._add(msg, "warn")
        self.diagram.set_result(None)
        self._loading = True
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 6)
            if it:
                it.setText("—")
        self._loading = False
        self._sections = []

    def _fill(self, ch, sysres, i_drv_auto, i_brush_auto):
        stages = ch["stages"]

        # 输入表只读列
        self._loading = True
        for i, st in enumerate(stages):
            it = self.table.item(i, 6)
            if it:
                it.setText(f"{st['i']:.4f}")
        self._loading = False

        i_t = ch["i_total"]
        self.m_it.set(f"{i_t:.4f}", "ok",
                      "减速" if i_t < 1 else ("增速" if i_t > 1 else "等速"))
        self.m_ut.set(f"{ch['u_total']:.4f}", "ok", "1/i")
        if sysres:
            self.m_rw.set(f"{sysres['rpm_wheel']:.2f}", "ok", "r/min")
            self.m_rm.set(f"{sysres['rpm_motor']:.2f}", "ok", "r/min")
        else:
            for m in (self.m_rw, self.m_rm):
                m.set("—", "na", "需填写行走速度与驱动轮半径")

        t = self.tbl_detail
        t.setRowCount(len(stages))
        for i, st in enumerate(stages):
            vals = [str(st["index"]), st["name"],
                    "同步带级" if st["kind"] == "belt" else "齿轮级",
                    f"{st['z1']:.0f}", f"{st['z2']:.0f}",
                    f"{st['i']:.4f}", f"{st['i_cum']:.4f}"]
            for j, s in enumerate(vals):
                c = QTableWidgetItem(s)
                if j != 1:
                    c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 6:
                    c.setForeground(QColor(ACCENT))
                t.setItem(i, j, c)
        t.resizeRowsToContents()
        self._fit_height(t)

        rw = self.row_sys
        rw.clear()
        if sysres:
            s = sysres
            rw.add("输入行走速度", f"{s['v_input']:g} {s['unit']}"
                                   f"（{s['v_mm_s']:.3f} mm/s）")
            rw.add("驱动轮半径 R", f"{s['wheel_radius']:.3f} mm")
            rw.add_sep()
            rw.add("驱动轮角速度 ω", f"{s['omega_wheel']:.4f} rad/s", bold=True)
            rw.add("驱动轮转速 n", f"{s['rpm_wheel']:.3f} r/min", bold=True)
            rw.add("驱动轮前累计 i", f"{s['i_drive']:.6f}"
                   + ("（自动）" if not self.in_idrv.value() else "（手动）"),
                   color=TEXT_DIM)
            rw.add_sep()
            rw.add("驱动电机角速度", f"{s['omega_motor']:.4f} rad/s", bold=True)
            rw.add("驱动电机转速", f"{s['rpm_motor']:.3f} r/min", bold=True,
                   color=ACCENT)
            rw.add_sep()
            rw.add("执行机构半径", f"{s['brush_radius']:.3f} mm")
            rw.add("行走 · 执行机构比", f"{s['ratio_brush_wheel']:.6f}",
                   color=ACCENT, bold=True)
            rw.add("执行机构角速度", f"{s['omega_brush']:.4f} rad/s", bold=True)
            rw.add("执行机构转速", f"{s['rpm_brush']:.3f} r/min", bold=True)
            rw.add("执行机构线速度", f"{s['v_brush']:.3f} mm/s", bold=True)
            rw.add("线速度之比", f"{s['k_walk_brush']:.4f}",
                   color=TEXT_DIM)
        else:
            rw.add("提示", "填写行走速度与驱动轮半径后显示速度汇总", color=BAD)

        warns, notes = [], []
        warns.extend(self._chain_warnings(ch))
        if not self.in_idrv.value():
            notes.append(f"「驱动轮前累计 i」留空，已自动取第一个同步带级之前的"
                         f"齿轮级累计 = {i_drv_auto:.6f}；"
                         f"如需按其他口径取值可直接填写覆盖。")
        if not self.in_ibrush.value():
            notes.append(f"「执行机构累计 i」留空，已自动取整条传动链的累计 = "
                         f"{i_brush_auto:.6f}。")
        if sysres and sysres["rpm_motor"] > 6000:
            warns.append(
                f"驱动电机转速 {sysres['rpm_motor']:.0f} r/min 偏高，"
                f"请核对电机额定转速与最高许用转速。")

        self.verify.show_items(warns, notes)
        self.diagram.set_result(ch)

        self._sections = [
            ("一、各级传动明细", [
                (f"{st['index']}. {st['name']}", 
                 f"{'同步带级' if st['kind'] == 'belt' else '齿轮级'}　"
                 f"Z₁={st['z1']:.0f} → Z₂={st['z2']:.0f}　"
                 f"i={st['i']:.6f}　累计={st['i_cum']:.6f}")
                for st in stages]),
            ("二、累计结果", [
                ("累计传动比 i", f"{ch['i_total']:.6f}"),
                ("累计减速比 u", f"{ch['u_total']:.6f}"),
                ("各级中心距之和", f"{ch['a_total']:.3f} mm"),
            ]),
            ("三、执行机构速度", rw.rows() if sysres else [("提示", "未填写速度参数")]),
        ]

    @staticmethod
    def _chain_warnings(ch: dict) -> list[str]:
        out = []
        for st in ch["stages"]:
            if st["kind"] == "belt":
                if abs(st["z1"] - st["z2"]) > 0.5:
                    out.append(
                        f"第 {st['index']} 级「{st['name']}」两带轮齿数不等"
                        f"（{st['z1']:.0f} / {st['z2']:.0f}），请确认传动比"
                        f"{st['i']:.4f} 符合方案意图。")
            else:
                if min(st["z1"], st["z2"]) < 12:
                    out.append(
                        f"第 {st['index']} 级「{st['name']}」最小齿数 "
                        f"{min(st['z1'], st['z2']):.0f} 偏小，齿轮易根切、"
                        f"请考虑变位或增大齿数。")
        if ch["i_total"] > 1.0 + 1e-9:
            out.append(f"整链为增速（i = {ch['i_total']:.4f} > 1），"
                       f"请确认是否与方案意图一致。")
        return out

    def _export(self):
        save_report(self, "传动链与整机速度计算报告", "传动链与速度报告",
                    [("传动级数", str(len(self._stages))),
                     ("行走速度", f"{self.in_v.value()} {self.in_unit.current()}")],
                    getattr(self, "_sections", []), [], [])


# =====================================================================
# 四、规格库
# =====================================================================

class StandardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # ---- 齿形表 ----
        c0 = Card("同步带齿形数据表", "节顶距取行业通行值")
        bar = QHBoxLayout()
        bar.setSpacing(10)
        bar.addWidget(QLabel("齿形族"))
        self.cb_fam = QComboBox()
        self.cb_fam.addItems(BELT_FAMILIES)
        bar.addWidget(self.cb_fam)
        bar.addWidget(QLabel("关键字"))
        self.ed_kw = QLineEdit()
        self.ed_kw.setPlaceholderText("如 S8M / 圆弧 / 8")
        self.ed_kw.setMaximumWidth(200)
        bar.addWidget(self.ed_kw)
        bar.addStretch(1)
        self.lbl_cnt = QLabel("")
        self.lbl_cnt.setObjectName("CardHint")
        bar.addWidget(self.lbl_cnt)
        c0.body.addLayout(bar)

        self.tbl_prof = QTableWidget(0, 6)
        self.tbl_prof.setHorizontalHeaderLabels(
            ["齿形代号", "节距 P (mm)", "节顶距 δ (mm)", "齿形族",
             "推荐最少齿数", "OD = PD − 2δ 关系"])
        self.tbl_prof.verticalHeader().setVisible(False)
        self.tbl_prof.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_prof.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_prof.setMinimumHeight(240)
        hh = self.tbl_prof.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        for i in (1, 2, 3):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_prof.itemDoubleClicked.connect(self._copy_profile)
        c0.body.addWidget(self.tbl_prof)
        root.addWidget(c0, 3)

        # ---- 带轮速查 ----
        c1 = Card("带轮尺寸速查", "双击任意一行复制")
        bar2 = QHBoxLayout()
        bar2.setSpacing(10)
        bar2.addWidget(QLabel("齿形"))
        self.cb_p = QComboBox()
        self.cb_p.addItems([b["code"] for b in BELT_PROFILES])
        self.cb_p.setCurrentText("S8M")
        bar2.addWidget(self.cb_p)
        bar2.addWidget(QLabel("齿数范围"))
        self.ed_z1 = QLineEdit("12")
        self.ed_z1.setMaximumWidth(60)
        bar2.addWidget(self.ed_z1)
        bar2.addWidget(QLabel("~"))
        self.ed_z2 = QLineEdit("72")
        self.ed_z2.setMaximumWidth(60)
        bar2.addWidget(self.ed_z2)
        b = QPushButton("生成")
        b.setObjectName("Primary")
        b.clicked.connect(self._build_pulley_table)
        bar2.addWidget(b)
        bar2.addStretch(1)
        c1.body.addLayout(bar2)

        self.tbl_pul = QTableWidget(0, 6)
        self.tbl_pul.setHorizontalHeaderLabels(
            ["齿数 Z", "节圆直径 PD (mm)", "齿顶圆直径 OD (mm)",
             "齿根圆直径 (mm)", "节圆周长 (mm)", "每齿弧长 (mm)"])
        self.tbl_pul.verticalHeader().setVisible(False)
        self.tbl_pul.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_pul.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_pul.setMinimumHeight(190)
        for i in range(6):
            self.tbl_pul.horizontalHeader().setSectionResizeMode(
                i, QHeaderView.ResizeMode.Stretch)
        self.tbl_pul.itemDoubleClicked.connect(self._copy_pulley)
        c1.body.addWidget(self.tbl_pul)
        root.addWidget(c1, 2)

        # ---- 模数系列 ----
        c2 = Card("GB/T 1357 渐开线圆柱齿轮模数系列", "单位 mm")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._series_label("第一系列（优先选用）", MODULE_FIRST, OK))
        row.addWidget(self._series_label("第二系列（尽量不用）", MODULE_SECOND, WARN))
        c2.body.addLayout(row)
        zrow = QHBoxLayout()
        zrow.setSpacing(10)
        zl = QLabel("常用齿数：" + "、".join(str(z) for z in TEETH_PRESETS))
        zl.setObjectName("CardHint")
        zl.setWordWrap(True)
        zrow.addWidget(zl)
        c2.body.addLayout(zrow)
        root.addWidget(c2)

        self._fill_profiles()
        self.cb_fam.currentIndexChanged.connect(self._fill_profiles)
        self.ed_kw.textChanged.connect(self._fill_profiles)
        self.cb_p.currentIndexChanged.connect(self._build_pulley_table)
        self._build_pulley_table()

    @staticmethod
    def _series_label(title: str, vals, color: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        lay.addWidget(t)
        v = QLabel("　".join(f"{x:g}" for x in vals))
        v.setWordWrap(True)
        v.setStyleSheet(f"color:{color};font-size:12.5px;font-weight:600;")
        lay.addWidget(v)
        return w

    def _fill_profiles(self):
        fam = self.cb_fam.currentText()
        kw = self.ed_kw.text().strip().lower()
        rows = []
        for b in BELT_PROFILES:
            if fam != "全部" and b["family"] != fam:
                continue
            hay = f"{b['code']} {b['family']} {b['p']:g}".lower()
            if kw and kw not in hay:
                continue
            rows.append(b)
        self.tbl_prof.setRowCount(len(rows))
        for i, b in enumerate(rows):
            vals = [b["code"], f"{b['p']:g}", f"{b['delta']:.3f}", b["family"],
                    str(min_teeth(b["code"])),
                    f"齿顶圆 = 节圆 − {2 * b['delta']:.3f}"]
            for j, s in enumerate(vals):
                c = QTableWidgetItem(s)
                if j in (1, 2, 4):
                    c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 0:
                    c.setForeground(QColor(ACCENT))
                    f = QFont()
                    f.setBold(True)
                    c.setFont(f)
                    c.setData(Qt.ItemDataRole.UserRole, b["code"])
                self.tbl_prof.setItem(i, j, c)
        self.lbl_cnt.setText(f"共 {len(rows)} 种齿形")

    def _build_pulley_table(self):
        code = self.cb_p.currentText()
        b = belt_profile(code)
        try:
            lo = int(float(self.ed_z1.text() or 12))
            hi = int(float(self.ed_z2.text() or 72))
        except ValueError:
            return
        lo, hi = max(6, min(lo, hi)), min(400, max(lo, hi))
        n = hi - lo + 1
        self.tbl_pul.setRowCount(n)
        for i, z in enumerate(range(lo, hi + 1)):
            pd = pulley_pitch_dia(z, b["p"])
            od = pulley_outside_dia(pd, b["delta"])
            df = pulley_root_dia(pd, b["delta"])
            circ = math.pi * pd
            vals = [str(z), f"{pd:.3f}", f"{od:.3f}", f"{df:.3f}",
                    f"{circ:.3f}", f"{circ / z:.4f}"]
            for j, s in enumerate(vals):
                c = QTableWidgetItem(s)
                c.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 0:
                    f = QFont()
                    f.setBold(True)
                    c.setFont(f)
                    if z < min_teeth(code):
                        c.setForeground(QColor(BAD))
                    else:
                        c.setForeground(QColor(OK))
                self.tbl_pul.setItem(i, j, c)

    def _copy_profile(self, item):
        code = item.data(Qt.ItemDataRole.UserRole)
        if not code:
            item = self.tbl_prof.item(item.row(), 0)
            code = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not code:
            return
        b = belt_profile(code)
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(
            f"{b['code']}：节距 {b['p']:g} mm，节顶距 {b['delta']:g} mm")
        QMessageBox.information(self, "已复制",
                                f"{b['code']}　P={b['p']:g} mm　δ={b['delta']:g} mm")

    def _copy_pulley(self, item):
        r = item.row()
        vals = [self.tbl_pul.item(r, c).text() for c in range(6)]
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(
            f"{self.cb_p.currentText()} 带轮 Z={vals[0]}："
            f"PD={vals[1]} OD={vals[2]} mm")
        QMessageBox.information(self, "已复制",
                                f"Z={vals[0]}　PD={vals[1]} mm　OD={vals[2]} mm")


# =====================================================================
# 五、使用说明
# =====================================================================

HELP_HTML = """
<style>
 body { font-family:"Microsoft YaHei UI","Microsoft YaHei",sans-serif;
        color:#1F2933; font-size:13.5px; line-height:1.85; }
 h2 { font-size:15px; color:#2F6FED; border-left:3px solid #2F6FED;
      padding-left:9px; margin-top:22px; }
 h3 { font-size:13.5px; margin-top:16px; color:#2B3A4A; }
 code { background:#F1F4F8; padding:2px 6px; border-radius:4px;
        font-family:Consolas,monospace; color:#1B4DA0; }
 table { border-collapse:collapse; width:100%; margin:8px 0; font-size:13px; }
 td, th { border:1px solid #E3E7ED; padding:6px 10px; }
 th { background:#F7F9FC; text-align:left; font-weight:600; color:#4A5A6A; }
 .warn { background:#FFF9F0; border-left:3px solid #E8901A; padding:9px 13px;
         border-radius:5px; color:#8A5A12; margin:10px 0; }
</style>

<h2>一、本软件与参考表格的对应关系</h2>
<p>界面的「同步带传动」页对应表格里的 <b>S8M 同步带计算</b> 部分，
「齿轮传动」页对应 <b>齿轮齿形与中心距</b> 部分，
「传动链与速度」页对应表格里的 <b>多级齿轮链 + 履带 + 滚刷速度</b> 部分。
三个页签各自独立，也可以按表格原来的串联方式一起用：
先在「传动链与速度」里把各级齿数填一遍，传动比与整机速度就全出来了。</p>

<h2>二、同步带传动</h2>
<h3>1. 齿形与节距</h3>
<p>齿形下拉框给出 23 种常用齿形：S 系列（S2M ~ S14M）、HTD（2M ~ 20M）、
T / AT 梯形齿（T2.5 ~ T20）与英制（MXL / XL / L / H / XH / XXH）。
选定齿形后自动带入节距 P 与节顶距 δ，两个值都可以手动覆盖。</p>

<h3>2. 带轮几何</h3>
<p><code>节圆直径 PD = Z · P / π</code></p>
<p><code>齿顶圆直径 OD = PD − 2δ</code>　（δ 为节顶距，即齿顶相对节圆的单边缩减量）</p>
<p>以 S8M 为例，P = 8 mm、δ = 0.686 mm。Z = 47 齿时：
PD = 47 × 8 / π = <b>119.685 mm</b>，OD = 119.685 − 2 × 0.686 = <b>118.313 mm</b>。</p>

<h3>3. 带长与中心距</h3>
<p><code>带长 L = Z<sub>b</sub> · P</code>　　<code>带圆形直径 = L / π</code></p>
<p><code>中心距 CD = (L − (Z₁ + Z₂) · P / 2) / 2</code></p>
<p>这个简化式等价于 <code>L ≈ 2·CD + π(PD₁ + PD₂)/2</code>，两轮齿数相同时是精确的；
齿数差较大时会有偏差，此时请参考程序同时给出的<b>精确解</b>
（严格求解 <code>L = 2C·cos φ + π(D₁+D₂)/2 + φ(D₂−D₁)</code>，
其中 <code>φ = asin((D₂−D₁)/2C)</code>）。出图建议采用精确解。</p>
<p>反过来也可以：填「已知中心距」，程序会反算需要的带齿数，取整到整数齿后
给出实际带长与对应的实际中心距 —— 装配时靠张紧机构吃掉这点误差即可。</p>

<h3>4. 包角与啮合齿数</h3>
<p><code>小轮包角 θ = 180° − 2·asin((PD₂ − PD₁) / (2·CD))</code></p>
<p><code>啮合齿数 Z<sub>m</sub> = Z · θ / 360</code></p>
<p>包角建议 ≥ 120°，啮合齿数建议 ≥ 6。低于这两个值会出现跳齿与带齿异常磨损，
解决办法是增大中心距、减小两轮齿数差，或加装张紧惰轮。</p>

<h2>三、齿轮传动</h2>
<h3>1. 基本几何</h3>
<table>
<tr><th>项目</th><th>公式</th></tr>
<tr><td>分度圆直径</td><td>d = m<sub>n</sub> · z / cos β</td></tr>
<tr><td>齿顶圆直径</td><td>d<sub>a</sub> = d + 2m<sub>n</sub>(h<sub>a</sub>* + x)</td></tr>
<tr><td>齿根圆直径</td><td>d<sub>f</sub> = d − 2m<sub>n</sub>(h<sub>a</sub>* + c* − x)</td></tr>
<tr><td>基圆直径</td><td>d<sub>b</sub> = d · cos α<sub>t</sub></td></tr>
<tr><td>标准中心距</td><td>a = m<sub>n</sub>(z₁ + z₂) / (2 cos β)</td></tr>
</table>
<p>默认取 h<sub>a</sub>* = 1、c* = 0.25、α = 20°（正常齿标准齿条）。</p>

<h3>2. 变位齿轮</h3>
<p>填了变位系数后，中心距按无侧隙啮合方程求解：</p>
<p><code>inv α<sub>w</sub> = inv α + 2(x₁ + x₂)·tan α / (z₁ + z₂)</code></p>
<p><code>中心距变动系数 y = (z₁ + z₂)/2 · (cos α / cos α<sub>w</sub> − 1)</code>，
实际中心距 <code>a = a<sub>标准</sub> + y·m<sub>n</sub></code>。</p>
<p>程序会给出该齿数下的<b>不根切最小变位系数</b>
<code>x<sub>min</sub> = h<sub>a</sub>* − z·sin²α / 2</code>（α=20° 时 z<sub>min</sub> ≈ 17.1），
变位不足会直接报警。</p>

<h3>3. 斜齿轮</h3>
<p>填入螺旋角 β 后按端面参数计算。注意 β 会带来轴向力
<code>F<sub>a</sub> ∝ tan β</code>，选轴承时要一并考虑。</p>

<h2>四、传动链与整机速度</h2>
<h3>1. 传动链</h3>
<p>表格里每一行是一级传动，可自由增删、改齿数与模数（或节距）。
每一级的传动比 <code>i = Z₁ / Z₂</code>，
累计传动比 <code>i<sub>总</sub> = Π(Z₁/Z₂)</code>。</p>
<div class="warn">本软件的 <b>i 定义为「输出转速 / 输入转速」</b>：
i &lt; 1 是减速，i &gt; 1 是增速。减速比 u = 1/i。<br>
这一口径与参考表格一致（表里 D6 = B6/C6，用的是「电机齿轮齿数 / 从动齿轮齿数」）。</div>

<h3>2. 驱动轮与执行机构</h3>
<p>由行走速度反算驱动轮转速：</p>
<p><code>ω = v / R</code>（rad/s，v 单位 mm/s、R 单位 mm）　　
<code>n = 60v / (2πR)</code>（r/min）</p>
<p>再由传动比反推电机：<code>ω<sub>电机</sub> = ω<sub>驱动轮</sub> / i<sub>驱动轮前</sub></code>。</p>
<p>执行机构（滚刷、输送带等）：</p>
<p><code>ω<sub>执行</sub> = ω<sub>驱动轮</sub> × (i<sub>执行</sub> / i<sub>驱动轮</sub>)</code>　　
<code>v<sub>执行</sub> = ω<sub>执行</sub> · R<sub>执行</sub></code></p>
<p>其中「驱动轮前累计 i」与「执行机构累计 i」留空时会自动取值：
前者取传动链中<b>第一个同步带级之前</b>的齿轮级累计（即电机到驱动轮的传动比），
后者取<b>整条链</b>的累计。这两个自动值与表格里的
<code>F12</code>、<code>F28</code> 完全对应，<code>i<sub>执行</sub>/i<sub>驱动轮</sub></code>
就是表格里的「行走滚刷比」。</p>

<h2>五、结果怎么读</h2>
<p>1. 指标卡：绿色为落在推荐区间，橙色为临界，红色为超出，请优先复核红色项。</p>
<p>2. 校核结论区：「!」为警告（必须处理），「·」为提示（说明取值来源与口径）。</p>
<p>3. 传动链框图：蓝色方块为齿轮级，绿色方块为同步带级，
方块内是该级的单级传动比。</p>
<p>4. 「导出报告」可生成 HTML 或 TXT 设计报告，含全部输入输出与校核结论。</p>

<h2>六、口径与免责</h2>
<div class="warn">
<b>节顶距 δ</b>：GB/T 11361 与 ISO 5294 未强制规定该值，各品牌齿槽略有差异，
本软件取行业通行值（与盖茨 / 优霓塔 / 米思米样本口径一致）用于计算与示意。
<b>精加工前请以所选品牌样本的齿槽图复核。</b><br>
<b>中心距简化式</b>：与参考表格一致；两轮齿数差较大时请采用程序给出的精确解。<br>
<b>同步带本身的强度校核</b>（许用功率、带宽、齿根剪切）不在本软件范围内，
需按 GB/T 11362 或供应商选型手册另行计算。
</div>
"""


class HelpPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        c = Card()
        from PySide6.QtWidgets import QTextBrowser
        tb = QTextBrowser()
        tb.setOpenExternalLinks(False)
        tb.setFrameShape(QFrame.Shape.NoFrame)
        tb.setStyleSheet("background:transparent;border:none;")
        tb.setHtml(HELP_HTML)
        c.add(tb)
        root.addWidget(c, 1)
