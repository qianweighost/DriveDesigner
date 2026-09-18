# -*- coding: utf-8 -*-
"""自检脚本：数值校验 + 界面冒烟 + 截图。

同源项目 OringDesigner 的 selftest 也已用同一套路径跑通。

数值校验的期望值取自参考表 L20齿轮同步带计算.xlsx 的公式计算结果，
逐位对齐，确保软件与原始表格口径一致。

⚠ 截图**不要**用 QT_QPA_PLATFORM=offscreen：offscreen 平台没有字体数据库，
中文会渲染成豆腐块，会让人误判排版有问题。正确做法是用
WA_DontShowOnScreen 属性 + 默认平台，拿到真实字体渲染的画面。
"""
from __future__ import annotations

import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.drive_core import (MODULES_ALL, belt_profile, chain_compute,  # noqa: E402
                             design_belt, design_gears, gear_pair,
                             pulley_outside_dia, pulley_pitch_dia,
                             system_compute)

OUT_DIR = os.path.join(_ROOT, "tools", "out")
LOG: list[str] = []
PASS = 0
FAIL = 0


def log(s: str = ""):
    LOG.append(str(s))


def check(title: str, got, want, tol: float = 1e-6):
    global PASS, FAIL
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        ok = abs(got - want) <= tol * max(1.0, abs(want))
    else:
        ok = got == want
    if ok:
        PASS += 1
        log(f"  ✓ {title}: {got}")
    else:
        FAIL += 1
        log(f"  ✗ {title}: got {got!r}, want {want!r}")
    return ok


# =====================================================================
# 一、数值校验（对照参考表格）
# =====================================================================

def test_belt_s8m():
    log("【1】同步带 S8M · Z₁=Z₂=47 · Zb=120   （Sheet1 / 2525履带）")
    r = design_belt("S8M", 47, 47, 120)
    check("节距 P", r["input"]["p"], 8)
    check("节顶距 δ", r["input"]["delta"], 0.686, 1e-9)
    check("PD₁ = Z·P/π", r["pulley1"]["pd"], 119.68451720510529)
    check("OD₁ = PD − 2δ", r["pulley1"]["od"], 118.31251720510529)
    check("PD₂", r["pulley2"]["pd"], 119.68451720510529)
    check("OD₂", r["pulley2"]["od"], 118.31251720510529)
    check("带长 L = Zb·P", r["belt"]["length"], 960)
    check("带圆形直径 L/π", r["belt"]["circle_dia"], 305.57749073643907)
    check("中心距 CD", r["geom"]["cd"], 292)
    check("传动比 i = Z₂/Z₁", r["metrics"]["i"], 1)

    log("【2】同步带 S8M · Z=60 · Zb=134   （2525履带）")
    r = design_belt("S8M", 60, 60, 134)
    check("PD", r["pulley1"]["pd"], 152.78874536821954)
    check("OD", r["pulley1"]["od"], 151.41674536821952)
    check("L", r["belt"]["length"], 1072)
    check("圆直径", r["belt"]["circle_dia"], 341.22819798902361)
    check("CD", r["geom"]["cd"], 296)

    log("【3】同步带 S8M · Z=54 · Zb=126   （Z10履带 借用2111）")
    r = design_belt("S8M", 54, 54, 126)
    check("PD", r["pulley1"]["pd"], 137.50987083139756)
    check("L", r["belt"]["length"], 1008)
    check("圆直径", r["belt"]["circle_dia"], 320.85636527326102)
    check("CD", r["geom"]["cd"], 288)

    log("【4】由中心距反算带齿数（新增能力）")
    r = design_belt("S8M", 47, 47, belt_teeth=None, center_distance=292.0)
    check("反算带齿数", r["belt"]["teeth"], 120)
    check("实际中心距", r["geom"]["cd"], 292)


def test_gears():
    log("【5】齿轮 m2 · 17 / 51   （2526齿轮）")
    r = design_gears(17, 51, 2.0)
    gp = r["pair"]
    check("d₁ = m·z₁", gp["g1"]["d"], 34)
    check("d₂ = m·z₂", gp["g2"]["d"], 102)
    check("中心距 a", r["metrics"]["a"], 68)
    check("传动比 i = z₁/z₂", r["metrics"]["i"], 0.33333333333333331)
    check("齿顶圆 da₁", gp["g1"]["da"], 38)
    check("齿根圆 df₁", gp["g1"]["df"], 29)

    log("【6】齿轮 m2 · 17 / 17")
    r = design_gears(17, 17, 2.0)
    check("d", r["pair"]["g1"]["d"], 34)
    check("a", r["metrics"]["a"], 34)
    check("i", r["metrics"]["i"], 1)

    log("【7】齿轮 m2 · 51 / 14   （2526齿轮V3 滚刷）")
    r = design_gears(51, 14, 2.0)
    check("d₁", r["pair"]["g1"]["d"], 102)
    check("d₂", r["pair"]["g2"]["d"], 28)
    check("a", r["metrics"]["a"], 65)
    check("i", r["metrics"]["i"], 3.6428571428571428)

    log("【8】变位齿轮：αw 与中心距")
    r = design_gears(17, 51, 2.0, x1=0.3, x2=0.3)
    check("中心距增大", r["metrics"]["a"] > 68, True)
    check("啮合角 > 20°", r["metrics"]["alpha_w"] > 20, True)
    check("不根切消除", r["pair"]["g1"]["undercut"], False)

    log("【9】斜齿轮 β=15°")
    r = design_gears(17, 51, 2.0, beta_deg=15.0)
    check("d = mn·z/cosβ", r["pair"]["g1"]["d"],
          2.0 * 17 / 0.9659258262890683)
    check("mt", r["pair"]["g1"]["mt"], 2 / 0.9659258262890683)


def test_chain_v31():
    """对照 2526齿轮修改v3.1 的完整传动链。"""
    log("【10】传动链（2526齿轮修改v3.1）："
        "17→20 → 20→51 → 履带47/47 → 31→18 → 18→11")
    stages = [
        {"kind": "gear", "name": "主动轮过渡", "z1": 17, "z2": 20, "m": 2.0},
        {"kind": "gear", "name": "主动轮", "z1": 20, "z2": 51, "m": 2.0},
        {"kind": "belt", "name": "履带", "z1": 47, "z2": 47, "p": 8.0,
         "p_code": "S8M"},
        {"kind": "gear", "name": "滚刷过渡", "z1": 31, "z2": 18, "m": 1.5},
        {"kind": "gear", "name": "滚刷", "z1": 18, "z2": 11, "m": 1.5},
    ]
    ch = chain_compute(stages)
    check("第1级 i", ch["stages"][0]["i"], 0.85)
    check("第2级 i", ch["stages"][1]["i"], 0.39215686274509803)
    check("第1级中心距", ch["stages"][0]["a_ref"], 37)
    check("第2级中心距", ch["stages"][1]["a_ref"], 71)
    check("履带节圆 PD", ch["stages"][2]["pd1"], 119.68451720510529)
    check("滚刷过渡中心距", ch["stages"][3]["a_ref"], 36.75)
    check("滚刷中心距", ch["stages"][4]["a_ref"], 21.75)
    check("累计 i（= 表 F28）", ch["i_total"], 0.93939393939393945)

    # 驱动轮前累计 = 第一个同步带级之前的齿轮级累计（= 表 F12）
    acc = 1.0
    for st in ch["stages"]:
        if st["kind"] == "belt":
            break
        acc *= st["i"]
    check("驱动轮前累计 i（= 表 F12）", acc, 0.33333333333333331)

    log("【11】整机速度（行走 150 mm/s，轮半径 65.3563，滚刷半径 39.5）")
    s = system_compute(v=150.0, unit="mm/s", wheel_radius=65.3563,
                       i_drive=acc, brush_radius=39.5,
                       i_brush_from_wheel=ch["i_total"] / acc)
    check("驱动轮角速度 ω（= 表 C32）", s["omega_wheel"], 2.2951115653731926)
    check("行走滚刷比（= 表 D32）", s["ratio_brush_wheel"],
          2.8181818181818183)
    check("滚刷角速度（= 表 E32）", s["omega_brush"], 6.4680416842335431)
    check("驱动电机角速度（= 表 C34）", s["omega_motor"], 6.8853346961195783)
    check("滚刷线速度（= 表 D34）", s["v_brush"], 255.48764652722494)
    check("行走滚刷速比（= 表 E34）", s["k_walk_brush"], 1.7032509768481663)

    log("【12】速度单位换算")
    s2 = system_compute(v=9.0, unit="m/min", wheel_radius=65.3563,
                        i_drive=1.0, brush_radius=0.0,
                        i_brush_from_wheel=0.0)
    check("9 m/min = 150 mm/s", s2["v_mm_s"], 150.0)


def test_tables():
    log("【13】数据表完整性")
    check("齿形数量", len(_belt_profiles()), 23)
    check("模数系列含 2 / 1.5", (2.0 in MODULES_ALL) and (1.5 in MODULES_ALL), True)
    for code in ("S8M", "5M", "T10", "XL"):
        b = belt_profile(code)
        check(f"{code} 节距 > 0", b["p"] > 0, True)
        check(f"{code} 节顶距 > 0", b["delta"] > 0, True)


def _belt_profiles():
    from core.drive_core import BELT_PROFILES
    return BELT_PROFILES


# =====================================================================
# 二、示意图几何自检
# =====================================================================

def test_diagram_geometry():
    """示意图必须：(a) 绘制不抛异常；(b) 轮体完整落在卡片内，不被裁切。

    paintEvent 里对异常做了兜底（画一行「示意图绘制失败」），
    所以界面冒烟发现不了绘制崩溃 —— 这里直接调 _paint 让异常抛出来。

    几何断言不用「按填充色找像素」：标注文字的反锯齿灰像素会把包围盒撑大，
    误判成越界。改为读图表自己记录的 self._geom（像素级真实几何）。
    """
    log("")
    log("【15】示意图几何自检（不抛异常 + 轮体不被卡片裁掉）")
    try:
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import QApplication

        from core.drive_core import chain_compute, design_belt, design_gears
        from ui.diagram import BeltDiagram, ChainDiagram, GearDiagram

        if QApplication.instance() is None:
            QApplication(sys.argv)

        def render(wdg, w: int, h: int):
            wdg.resize(w, h)
            img = QImage(w, h, QImage.Format.Format_ARGB32)
            img.fill(0xFFFFFFFF)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            try:
                wdg._paint(p)      # 直接调用：异常不被 paintEvent 的兜底吞掉
            finally:
                p.end()
            return img

        def assert_inside(wdg, w, h, tag, top_band=0.0, bottom_band=0.0):
            """轮体包围盒必须完整落在卡片内，且不侵入上下标注带。"""
            boxes = wdg._geom.get("wheels") or []
            if not check(f"{tag} 记录了几何", len(boxes) > 0, True):
                return
            for i, (x0, y0, x1, y1) in enumerate(boxes):
                ok = (0.0 <= x0) and (x1 <= w) and (0.0 <= y0) and (y1 <= h)
                check(f"{tag} 轮{i + 1}在卡片内", ok, True)
                check(f"{tag} 轮{i + 1}不压上标注带", y0 >= top_band, True)
                check(f"{tag} 轮{i + 1}不压下标注带", y1 <= h - bottom_band, True)
                log(f"      └ 轮{i + 1} 像素框 x[{x0:.0f},{x1:.0f}] "
                    f"y[{y0:.0f},{y1:.0f}] in {w}×{h}"
                    f"　尺寸线 y={wdg._geom.get('dim_y', -1):.0f}")
                dy = wdg._geom.get("dim_y")
                if dy is not None:
                    check(f"{tag} 尺寸线在轮下方", dy >= y1, True)

        # ---- 同步带：等径 & 异径，且覆盖宽扁 / 窄高两种窗口比例 ----
        for tag, z1, z2, zb in (("带 等径47/47", 47, 47, 120),
                                ("带 异径24/72", 24, 72, 150)):
            for w, h in ((700, 300), (560, 240), (900, 260)):
                wdg = BeltDiagram()
                wdg.set_result(design_belt("S8M", z1, z2, zb))
                render(wdg, w, h)
                assert_inside(wdg, w, h, f"{tag}@{w}x{h}", 50.0, 30.0)

        # ---- 齿轮：两轮半径差很大，大轮决定下缘 ----
        for tag, z1, z2, m in (("齿轮 2m 17/51", 17, 51, 2.0),
                               ("齿轮 1.5m 51/14", 51, 14, 1.5)):
            for w, h in ((700, 300), (560, 240)):
                wdg = GearDiagram()
                wdg.set_result(design_gears(z1, z2, m))
                render(wdg, w, h)
                assert_inside(wdg, w, h, f"{tag}@{w}x{h}", 46.0, 30.0)

        # ---- 传动链框图：多宽度下都不应溢出 ----
        stages = [
            {"kind": "gear", "name": "主动轮过渡", "z1": 17, "z2": 20, "m": 2.0},
            {"kind": "gear", "name": "主动轮", "z1": 20, "z2": 51, "m": 2.0},
            {"kind": "belt", "name": "履带", "z1": 47, "z2": 47, "p": 8.0,
             "p_code": "S8M"},
            {"kind": "gear", "name": "滚刷过渡", "z1": 31, "z2": 18, "m": 1.5},
            {"kind": "gear", "name": "滚刷", "z1": 18, "z2": 11, "m": 1.5},
        ]
        wdg = ChainDiagram()
        wdg.set_result(chain_compute(stages))
        for w in (560, 700, 900, 1200):
            render(wdg, w, 150)
            boxes = wdg._geom.get("blocks") or []
            ok = (len(boxes) == 5 and boxes[0][0] > 30.0
                  and boxes[-1][2] < w - 30.0 and boxes[0][1] > 0
                  and boxes[0][3] < 150)
            check(f"传动链 5 个方块在框内 w={w}", ok, True)
            log(f"      └ 首块 x[{boxes[0][0]:.0f},{boxes[0][2]:.0f}] "
                f"末块右缘 {boxes[-1][2]:.0f} / 宽 {w}")

        # ---- 极端工况：空链，不能崩 ----
        d = ChainDiagram()
        d.set_result({"stages": [], "i_total": 1.0, "u_total": 1.0,
                      "a_total": 0.0})
        render(d, 700, 150)
        check("空传动链不崩", True, True)

        # ---- 极端工况：极小窗口，不能崩、不能越界 ----
        wdg = BeltDiagram()
        wdg.set_result(design_belt("S8M", 24, 72, 150))
        render(wdg, 320, 200)
        check("小窗口带传动不崩", True, True)
    except Exception as exc:  # noqa: BLE001
        global FAIL
        FAIL += 1
        log(f"  ✗ 示意图几何自检失败：{exc}")
        log(traceback.format_exc())


# =====================================================================
# 三、界面冒烟
# =====================================================================

def test_ui():
    log("")
    log("【14】界面冒烟 + 截图")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        from ui import theme
        from app import MainWindow

        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet(theme.stylesheet())
        win = MainWindow()
        # 真实字体渲染但不真弹窗：offscreen 平台没有字体库会出豆腐块
        win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        win.resize(1420, 900)
        win.show()
        for _ in range(8):
            app.processEvents()

        os.makedirs(OUT_DIR, exist_ok=True)
        names = ["belt", "gear", "chain", "standards", "help"]
        pages = [win.tabs.widget(i) for i in range(win.tabs.count())]
        check("页签数量", len(pages), 5)
        for i, pg in enumerate(pages):
            win.tabs.setCurrentIndex(i)
            for _ in range(4):
                app.processEvents()
            if hasattr(pg, "recalc"):
                pg.recalc()
            win.layout().activate()
            for _ in range(8):
                app.processEvents()
            shot = os.path.join(OUT_DIR, f"shot_{i}_{names[i]}.png")
            ok = win.grab().save(shot)
            check(f"截图 {names[i]}", ok, True)

        # 传动链页：导出结构自检
        chain = pages[2]
        check("传动链默认 5 级", len(chain._stages), 5)
        chain._add("gear")
        check("增加一级后 6 级", len(chain._stages), 6)
        chain._del_last()
        check("删除末级后 5 级", len(chain._stages), 5)

        # 报告生成
        from ui.pages import report_html, report_text
        h = report_html("测试", [("a", "b")], [("一", [("k", "v")])], [], [])
        t = report_text("测试", [("a", "b")], [("一", [("k", "v")])], [], [])
        check("HTML 报告非空", len(h) > 500, True)
        check("TXT 报告非空", len(t) > 200, True)

        win.close()
    except Exception as exc:  # noqa: BLE001
        global FAIL
        FAIL += 1
        log(f"  ✗ 界面冒烟失败：{exc}")
        log(traceback.format_exc())


# =====================================================================

def main():
    only_num = "--no-ui" in sys.argv
    log("=" * 70)
    log("齿轮同步带传动设计计算器 —— 自检")
    log("=" * 70)
    for fn in (test_belt_s8m, test_gears, test_chain_v31, test_tables):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            global FAIL
            FAIL += 1
            log(f"  ✗ {fn.__name__} 抛异常：{exc}")
            log(traceback.format_exc())
    if not only_num:
        test_diagram_geometry()
        test_ui()

    log("")
    log("=" * 70)
    log(f"结果：通过 {PASS} 项，失败 {FAIL} 项")
    log("=" * 70)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "selftest.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    print("\n".join(LOG))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
