# -*- coding: utf-8 -*-
"""传动示意图组件（QPainter 实时绘制，按真实比例）。

  BeltDiagram  —— 两带轮 + 同步带包络 + 中心距 / 包角标注
  GearDiagram  —— 一对啮合齿轮（含齿形）+ 分度圆 / 中心距标注
  ChainDiagram —— 多级传动链框图（各级传动比与累计传动比）

坐标策略
  几何部分在「毫米坐标系」下绘制（QTransform 缩放，uniform=True 保证圆是圆），
  标注文字一律回到像素坐标系、贴着卡片四角摆放，
  这样无论轴距怎么变都不会出现文字压图或越界。

⚠ Qt 的 arcTo 角度约定：0° 在 3 点钟方向，90° 在 12 点钟方向，
  即 path 点为 (cx + rx·cosθ, cy − ry·sinθ)。我们的毫米坐标系 y 轴向上，
  两者差一个符号：**毫米角 α 对应 Qt 角 −α**。写弧线时必须换算，
  否则包络线会画成交叉的 X 形。
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter,
                           QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .theme import (ACCENT, BELT, BORDER, DIM, GEAR, HUB, MESH, METAL, OK,
                    PULLEY, TEXT, TEXT_DIM, TEXT_MID, WARN)


# =====================================================================
# 基础工具
# =====================================================================

class _View:
    """毫米 ↔ 像素坐标映射（y 轴向上）。

    uniform=True 时强制等比例缩放，保证圆在屏幕上仍是圆 —— 传动示意图必开。
    """

    def __init__(self, x0, x1, y0, y1, w, h,
                 pad_l=58, pad_r=30, pad_t=34, pad_b=46,
                 uniform=False, max_ratio=4.0):
        self.xc = (x0 + x1) / 2.0
        self.yc = (y0 + y1) / 2.0
        iw = max(20.0, w - pad_l - pad_r)
        ih = max(20.0, h - pad_t - pad_b)
        sx = iw / max(1e-9, (x1 - x0))
        sy = ih / max(1e-9, (y1 - y0))
        if uniform:
            s = min(sx, sy)
            sx = sy = s
        elif sx > 0:
            ratio = sy / sx
            if ratio > max_ratio:
                sy = sx * max_ratio
            elif ratio < 1.0 / max_ratio:
                sy = sx / max_ratio
        self.sx, self.sy = sx, sy
        self.cx = pad_l + iw / 2.0
        self.cy = pad_t + ih / 2.0
        self.pad_l, self.pad_r, self.pad_t, self.pad_b = pad_l, pad_r, pad_t, pad_b

    @property
    def ratio(self) -> float:
        return self.sy / self.sx if self.sx else 1.0

    def X(self, x):
        return self.cx + (x - self.xc) * self.sx

    def Y(self, y):
        return self.cy - (y - self.yc) * self.sy

    def P(self, x, y) -> QPointF:
        return QPointF(self.X(x), self.Y(y))

    def apply(self, p: QPainter):
        """把画笔切到毫米坐标系。"""
        p.translate(self.cx, self.cy)
        p.scale(self.sx, -self.sy)
        p.translate(-self.xc, -self.yc)


def _pen(color, width: float = 1.2, cosmetic: bool = True,
         style=Qt.PenStyle.SolidLine) -> QPen:
    pen = QPen(QColor(color), width, style)
    pen.setCosmetic(cosmetic)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _text(p: QPainter, x: float, y: float, s: str, color=TEXT, size=8.6,
          bold=False, anchor="mm", box=False, bg="#FFFFFFF0"):
    """在像素坐标 (x, y) 处写字。anchor: 横 l/m/r + 纵 t/m/b。"""
    f = QFont()
    f.setPointSizeF(size)
    f.setBold(bold)
    p.setFont(f)
    fm = QFontMetricsF(f)
    lines = s.split("\n")
    w = max(fm.horizontalAdvance(ln) for ln in lines) + (12 if box else 2)
    h = fm.height() * len(lines) + (8 if box else 1)
    rx = x if anchor[0] == "l" else (x - w if anchor[0] == "r" else x - w / 2.0)
    ry = y if anchor[1] == "t" else (y - h if anchor[1] == "b" else y - h / 2.0)
    rect = QRectF(rx, ry, w, h)
    if box:
        p.setBrush(QBrush(QColor(bg)))
        p.setPen(_pen(BORDER, 1))
        p.drawRoundedRect(rect, 5, 5)
    p.setPen(_pen(color, 1))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, s)


def _arrow(p: QPainter, tip: QPointF, ang: float, size: float = 5.0,
           color: str = DIM):
    a1, a2 = ang + math.radians(152), ang - math.radians(152)
    p1 = QPointF(tip.x() + size * math.cos(a1), tip.y() + size * math.sin(a1))
    p2 = QPointF(tip.x() + size * math.cos(a2), tip.y() + size * math.sin(a2))
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([tip, p1, p2]))


def _dim_h(p: QPainter, xa: float, ya: float, xb: float, yb: float, yd: float,
           label: str, color: str = DIM):
    """水平尺寸标注（像素坐标）：两条延长线 + 双箭头尺寸线 + 居中标签。

    xa / xb —— 两条延长线的横坐标（即两轮轴心）
    ya / yb —— 两条延长线的起点纵坐标（一般取轮子下缘，再外移几点）
    yd      —— 尺寸线纵坐标（必须落在卡片内的安全区，调用方负责夹取）
    """
    p.setPen(_pen(color, 0.8, style=Qt.PenStyle.DashLine))
    p.drawLine(QPointF(xa, ya), QPointF(xa, yd + 6.0))
    p.drawLine(QPointF(xb, yb), QPointF(xb, yd + 6.0))
    p.setPen(_pen(color, 1.1))
    p.drawLine(QPointF(xa, yd), QPointF(xb, yd))
    _arrow(p, QPointF(xa, yd), math.pi, 5.0, color)
    _arrow(p, QPointF(xb, yd), 0.0, 5.0, color)
    _text(p, (xa + xb) / 2.0, yd - 3.0, label, color, 8.6, True, "mb", True)


def _circle_box(v: _View, cx: float, r: float):
    """圆在像素坐标系下的包围盒 (x0, y0, x1, y1)，y0 为上边。"""
    return (v.X(cx - r), v.Y(r), v.X(cx + r), v.Y(-r))


def _tooth_outline(cx: float, cy: float, r_tip: float, r_root: float,
                   teeth: int, phase: float = 0.0,
                   h_tip: float = 0.30, h_root: float = 0.33) -> QPolygonF:
    """齿形外轮廓多边形（毫米坐标）：齿顶/齿根用梯形近似。"""
    step = 2.0 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a0 = phase + i * step
        for ang, r in ((a0 - step * h_tip, r_tip), (a0 + step * h_tip, r_tip),
                       (a0 + step * h_root, r_root),
                       (a0 + step - step * h_root, r_root)):
            pts.append(QPointF(cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return QPolygonF(pts)


def _rot_arrow(p: QPainter, v: _View, cx: float, r: float, cw: bool):
    """在轮上画一个旋转方向箭头。"""
    rect = QRectF(v.X(cx - r), v.Y(r), 2 * r * v.sx, 2 * r * v.sy)
    p.setPen(_pen(ACCENT, 1.3))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if cw:
        p.drawArc(rect, int(-30 * 16), int(-120 * 16))
        end = math.radians(-150)
    else:
        p.drawArc(rect, int(-150 * 16), int(120 * 16))
        end = math.radians(-30)
    tip = QPointF(v.X(cx + r * math.cos(end)), v.Y(r * math.sin(end)))
    _arrow(p, tip, end - (math.pi / 2 if cw else -math.pi / 2), 4.6, ACCENT)


def _base_card(p: QPainter, w: int, h: int, hint: str):
    p.fillRect(QRectF(0, 0, w, h), QColor("#FFFFFF"))
    p.setPen(_pen(BORDER, 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 8, 8)
    if hint:
        _text(p, w / 2, h - 6, hint, TEXT_DIM, 8.2, False, "mb")


# =====================================================================
# 同步带传动示意
# =====================================================================

class BeltDiagram(QWidget):
    """两带轮按真实比例 + 带包络 + 中心距与包角标注。"""

    CAPTION = "同步带传动示意（按真实比例 · 略去带厚）"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._res = None
        self.setMinimumSize(380, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_result(self, res):
        self._res = res
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # 底板必须先画，否则会把后面的图形盖掉
        _base_card(p, self.width(), self.height(), self.CAPTION)
        if not self._res:
            _text(p, self.width() / 2, self.height() / 2,
                  "输入参数后点击「开始计算」", TEXT_DIM, 11)
            return
        try:
            self._paint(p)
        except Exception as exc:  # noqa: BLE001 —— 示意图不应拖垮主流程
            _text(p, self.width() / 2, self.height() / 2,
                  f"示意图绘制失败：{exc}", WARN, 9)

    # ------------------------------------------------------------------
    def _paint(self, p: QPainter):
        r = self._res
        A, B = r["pulley1"], r["pulley2"]
        cd = r["geom"]["cd"]
        delta = r["input"]["delta"]
        r1, r2 = A["pd"] / 2.0, B["pd"] / 2.0

        # 带轮齿形：齿顶圆 = PD − 2δ，齿根再往下约 2.35δ（与内核同一口径）
        tip_i, root_i = r1 - delta, r1 - delta - 2.35 * delta
        tip_o, root_o = r2 - delta, r2 - delta - 2.35 * delta

        # 视图：margin 必须 ≥ 最大轮半径，否则轮子会被视图裁掉。
        # 尺寸线已改到像素坐标画，不再需要为它预留毫米空间，故只留一点点余量。
        margin = max(r1, r2) * 1.06 + max(delta * 6.0, 3.0)
        v = _View(-margin, cd + margin, -margin, margin,
                  self.width(), self.height(),
                  pad_l=76, pad_r=76, pad_t=56, pad_b=74,
                  uniform=True)
        # 自检用：记录像素级包围盒，供 selftest 验证轮子没被卡片裁掉
        self._geom = {"scale": v.sx, "wheels": [_circle_box(v, 0.0, r1),
                                                _circle_box(v, cd, r2)]}

        # ---- 包络切点：外切线法向角 φ，cos φ = (r₁ − r₂)/CD ----
        phi = math.acos(max(-1.0, min(1.0, (r1 - r2) / cd)))
        nx, ny = math.cos(phi), math.sin(phi)
        p1u, p1l = (r1 * nx, r1 * ny), (r1 * nx, -r1 * ny)
        p2u, p2l = (cd + r2 * nx, r2 * ny), (cd + r2 * nx, -r2 * ny)

        path = QPainterPath()
        path.moveTo(*p1u)
        path.lineTo(*p2u)
        # 带轮 2：毫米角从 +φ 经 0 到 −φ  →  Qt 角从 −φ 经 0 到 +φ
        path.arcTo(QRectF(cd - r2, -r2, 2 * r2, 2 * r2),
                   -math.degrees(phi), math.degrees(2 * phi))
        path.lineTo(*p1l)
        # 带轮 1：毫米角从 −φ 经 180 到 +φ  →  Qt 角从 +φ 经 180 到 −φ(+360)
        path.arcTo(QRectF(-r1, -r1, 2 * r1, 2 * r1),
                   math.degrees(phi), 360.0 - math.degrees(2 * phi))
        path.closeSubpath()

        p.save()
        v.apply(p)
        # 带本体
        p.setPen(_pen(BELT, 7.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        # 带内侧齿纹
        p.setPen(_pen("#CBD3DD", 0.9))
        total = path.length()
        if total > 0:
            step = max(0.8, total / 260.0)
            t = 0.0
            while t <= total:
                pt = path.pointAtPercent(t / total)
                pt2 = path.pointAtPercent(min(1.0, (t + step * 0.45) / total))
                dx, dy = pt2.x() - pt.x(), pt2.y() - pt.y()
                ln = math.hypot(dx, dy) or 1.0
                ux, uy = -dy / ln, dx / ln
                p.drawLine(QPointF(pt.x() - ux * 1.7, pt.y() - uy * 1.7),
                           QPointF(pt.x() + ux * 1.7, pt.y() + uy * 1.7))
                t += step

        for cx, tip, root, z, pdia in ((0.0, tip_i, root_i, A["z"], A["pd"]),
                                       (cd, tip_o, root_o, B["z"], B["pd"])):
            teeth = int(max(10, min(64, round(z))))
            poly = _tooth_outline(cx, 0.0, tip, root, teeth)
            p.setBrush(QBrush(QColor(PULLEY)))
            p.setPen(_pen("#8794A3", 0.5))
            p.drawPolygon(poly)
            p.setBrush(QBrush(QColor("#FFFFFF")))
            p.drawEllipse(QPointF(cx, 0.0), pdia * 0.17, pdia * 0.17)
            p.setBrush(QBrush(QColor(HUB)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, 0.0), pdia * 0.075, pdia * 0.075)
            # 节圆
            p.setPen(_pen(DIM, 0.6, style=Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, 0.0), pdia / 2.0, pdia / 2.0)

        p.restore()

        # ---- 中心距尺寸线（像素坐标：贴两轮下缘外侧，绝不越界、不压图）----
        ya, yb = v.Y(0.0) + r1 * v.sy, v.Y(0.0) + r2 * v.sy
        yd = min(max(ya, yb) + 22.0, self.height() - 46.0)
        self._geom["dim_y"] = yd
        _dim_h(p, v.X(0.0), ya + 5.0, v.X(cd), yb + 5.0, yd,
               f"中心距 CD = {cd:.2f} mm")

        # ---- 标注（像素坐标，贴四角，永不压图）----
        _text(p, 10, 10,
              f"带轮 1（主动）\nZ₁ = {A['z']:.0f}　PD₁ = {A['pd']:.2f}\n"
              f"OD₁ = {A['od']:.2f}",
              ACCENT, 8.4, True, "lt", True)
        _text(p, self.width() - 10, 10,
              f"带轮 2（从动）\nZ₂ = {B['z']:.0f}　PD₂ = {B['pd']:.2f}\n"
              f"OD₂ = {B['od']:.2f}",
              ACCENT, 8.4, True, "rt", True)

        th = r["geom"]["wrap_angle"]
        zm = r["geom"]["mesh_teeth"]
        good = th >= 120 and zm >= 6
        _text(p, 10, self.height() - 24,
              f"带长 L = {r['belt']['length']:.2f} mm（{r['belt']['teeth']:.0f} 齿）"
              f"　｜　i = Z₂/Z₁ = {r['metrics']['i']:.4f}"
              f"　｜　u = {r['metrics']['u']:.4f}",
              TEXT_MID, 8.4, False, "lb")
        _text(p, self.width() - 10, self.height() - 24,
              f"小轮包角 {th:.2f}°　啮合齿数 {zm:.2f}"
              f"（建议 ≥ 120° / ≥ 6）",
              OK if good else WARN, 8.4, True, "rb")

        _rot_arrow(p, v, 0.0, r1 * 0.62, cw=True)
        _rot_arrow(p, v, cd, r2 * 0.62, cw=False)


# =====================================================================
# 齿轮啮合示意
# =====================================================================

class GearDiagram(QWidget):
    """一对啮合齿轮：按真实分度圆比例绘制齿形与中心距。"""

    CAPTION = "齿轮啮合示意（按真实分度圆比例 · 啮合区橙色高亮）"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._res = None
        self.setMinimumSize(380, 250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_result(self, res):
        self._res = res
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _base_card(p, self.width(), self.height(), self.CAPTION)
        if not self._res:
            _text(p, self.width() / 2, self.height() / 2,
                  "输入参数后点击「开始计算」", TEXT_DIM, 11)
            return
        try:
            self._paint(p)
        except Exception as exc:  # noqa: BLE001
            _text(p, self.width() / 2, self.height() / 2,
                  f"示意图绘制失败：{exc}", WARN, 9)

    # ------------------------------------------------------------------
    def _paint(self, p: QPainter):
        r = self._res
        gp = r["pair"]
        g1, g2 = gp["g1"], gp["g2"]
        a = gp["a"]
        r1, r2 = g1["d"] / 2.0, g2["d"] / 2.0
        # margin 必须 ≥ 最大齿顶圆半径，否则齿轮会被视图裁掉
        margin = max(g1["da"], g2["da"]) / 2.0 * 1.05 + g1["mn"] * 0.6
        v = _View(-margin, a + margin, -margin, margin,
                  self.width(), self.height(),
                  pad_l=76, pad_r=76, pad_t=52, pad_b=64,
                  uniform=True)
        self._geom = {"scale": v.sx,
                      "wheels": [_circle_box(v, 0.0, g1["da"] / 2.0),
                                 _circle_box(v, a, g2["da"] / 2.0)]}

        p.save()
        v.apply(p)
        # 啮合区高亮
        p.setBrush(QBrush(QColor(232, 144, 26, 36)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(r1, 0.0), g1["mn"] * 1.6, g1["mn"] * 1.6)

        for cx, g, phase, fill in ((0.0, g1, 0.0, PULLEY),
                                   (a, g2, math.pi / g2["z"], GEAR)):
            tip = g["da"] / 2.0
            root = max(g["df"] / 2.0, tip * 0.70)
            poly = _tooth_outline(cx, 0.0, tip, root, int(round(g["z"])), phase)
            p.setBrush(QBrush(QColor(fill)))
            p.setPen(_pen("#788594", 0.55))
            p.drawPolygon(poly)
            p.setBrush(QBrush(QColor("#FFFFFF")))
            p.setPen(_pen(BORDER, 0.5))
            p.drawEllipse(QPointF(cx, 0.0), g["d"] * 0.15, g["d"] * 0.15)
            p.setBrush(QBrush(QColor(HUB)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, 0.0), g["d"] * 0.07, g["d"] * 0.07)
            p.setPen(_pen(DIM, 0.6, style=Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, 0.0), g["d"] / 2.0, g["d"] / 2.0)
            p.setPen(_pen("#C2CBD6", 0.5, style=Qt.PenStyle.DotLine))
            p.drawEllipse(QPointF(cx, 0.0), g["df"] / 2.0, g["df"] / 2.0)

        p.restore()

        # ---- 中心距尺寸线（像素坐标，同带传动）----
        ya = v.Y(0.0) + g1["da"] / 2.0 * v.sy
        yb = v.Y(0.0) + g2["da"] / 2.0 * v.sy
        yd = min(max(ya, yb) + 20.0, self.height() - 44.0)
        self._geom["dim_y"] = yd
        _dim_h(p, v.X(0.0), ya + 5.0, v.X(a), yb + 5.0, yd,
               f"中心距 a = {a:.3f} mm（标准 {gp['a_std']:.3f}）")

        _text(p, 10, 10,
              f"主动轮 Z₁ = {g1['z']:.0f}\nd₁ = {g1['d']:.2f}　"
              f"da₁ = {g1['da']:.2f}",
              ACCENT, 8.4, True, "lt", True)
        _text(p, self.width() - 10, 10,
              f"从动轮 Z₂ = {g2['z']:.0f}\nd₂ = {g2['d']:.2f}　"
              f"da₂ = {g2['da']:.2f}",
              ACCENT, 8.4, True, "rt", True)

        m = r["metrics"]
        _text(p, 10, self.height() - 24,
              f"m = {g1['mn']:g}　α = {g1['alpha']:g}°　β = {g1['beta']:g}°",
              TEXT_MID, 8.4, False, "lb")
        _text(p, self.width() - 10, self.height() - 24,
              f"i = Z₁/Z₂ = {m['i']:.4f}　u = {m['u']:.4f}",
              ACCENT, 8.4, True, "rb")
        # 啮合区标记
        _text(p, v.X(r1), v.Y(0), "啮合", "#8A5A12", 8.0, True, "mm")


# =====================================================================
# 传动链框图
# =====================================================================

class ChainDiagram(QWidget):
    """多级传动链：输入 → 各级方块（标注齿数与传动比）→ 输出。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._res = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(150)

    def set_result(self, res):
        self._res = res
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _base_card(p, self.width(), self.height(), "")
        if not self._res or not self._res.get("stages"):
            _text(p, self.width() / 2, self.height() / 2,
                  "增加传动级后自动生成传动链框图", TEXT_DIM, 10)
            return
        try:
            self._paint(p)
        except Exception as exc:  # noqa: BLE001
            _text(p, self.width() / 2, self.height() / 2,
                  f"示意图绘制失败：{exc}", WARN, 9)

    # ------------------------------------------------------------------
    def _paint(self, p: QPainter):
        r = self._res
        stages = r.get("stages") or []
        n = len(stages)
        if n <= 0:          # 空链：paintEvent 会拦，但 _paint 被直接调用时也要安全
            return
        by, bh = 30.0, 50.0
        gap = 9.0
        avail = self.width() - 92.0 - gap * (n - 1)
        bw = max(56.0, min(126.0, avail / n))
        total = bw * n + gap * (n - 1)
        x = max(46.0, (self.width() - total) / 2.0)

        _text(p, x - 10, by + bh / 2, "输入", TEXT_DIM, 9, True, "rm")

        boxes = []
        for st in stages:
            rect = QRectF(x, by, bw, bh)
            boxes.append((rect.x(), rect.y(), rect.right(), rect.bottom()))
            is_belt = st["kind"] == "belt"
            p.setBrush(QBrush(QColor("#EFF7F1" if is_belt else "#EAF1FE")))
            p.setPen(_pen(OK if is_belt else ACCENT, 1.1))
            p.drawRoundedRect(rect, 7, 7)

            name = st["name"] if len(st["name"]) <= 7 else st["name"][:7] + "…"
            _text(p, rect.center().x(), by + 10, name, TEXT, 8.0, True, "mt")
            _text(p, rect.center().x(), by + 23,
                  ("同步带级" if is_belt else "齿轮级")
                  + f"　{st['z1']:.0f}→{st['z2']:.0f}", TEXT_MID, 7.6, False, "mt")
            _text(p, rect.center().x(), by + 36,
                  f"i = {st['i']:.4f}", OK if is_belt else ACCENT, 8.0, True, "mt")

            if st is not stages[-1]:
                p.setPen(_pen("#B6C0CC", 1.2))
                p.drawLine(QPointF(x + bw, by + bh / 2),
                           QPointF(x + bw + gap - 3, by + bh / 2))
                _arrow(p, QPointF(x + bw + gap, by + bh / 2), 0.0, 4.0, "#B6C0CC")
            x += bw + gap

        _text(p, x - gap + 4, by + bh / 2, "输出", TEXT_DIM, 9, True, "lm")
        self._geom = {"blocks": boxes}

        i_t = r["i_total"]
        kind = "减速" if i_t < 1 else ("增速" if i_t > 1 else "等速")
        _text(p, self.width() / 2, by + bh + 12,
              f"累计传动比 i = Π(Z主动 / Z从动) = {i_t:.6f}"
              f"　｜　累计减速比 u = {r['u_total']:.6f}（{kind}）"
              f"　｜　各级中心距之和 = {r['a_total']:.2f} mm",
              ACCENT, 9.2, True, "mt")
        _text(p, self.width() / 2, by + bh + 32,
              "i 为「输出转速 / 输入转速」：i < 1 即减速，i > 1 即增速",
              TEXT_DIM, 8.2, False, "mt")
