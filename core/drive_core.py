# -*- coding: utf-8 -*-
"""齿轮 · 同步带传动设计计算内核
=====================================================================
覆盖范围
  · 同步带传动 —— 带轮节圆 / 齿顶圆、带长、中心距、包角、啮合齿数、带速
  · 齿轮传动   —— 直齿 / 斜齿 / 变位齿轮的几何尺寸与齿轮对啮合中心距
  · 多级传动链 —— 齿轮级 + 同步带级混合串联，累计传动比
  · 整机速度   —— 驱动轮转速、电机转速与角速度、执行机构（滚刷等）转速与线速度

计算内容
  同步带：PD = Z·P/π    OD = PD − 2δ    L = Zb·P    CD = (L − (Z1+Z2)·P/2)/2
          包角 θ = 180° − 2·asin((PD2−PD1)/2CD)   啮合齿数 Zm = Z·θ/360
  齿  轮：d = mn·z/cosβ   da = d + 2mn(ha* + x)   df = d − 2mn(ha* + c* − x)
          db = d·cosαt    a = mn(z1+z2)/(2cosβ) + y·mn（变位时按无侧隙啮合方程求）
  传动链：i = Π(Z主动 / Z从动)    （i 为「输出/输入」转速比，i<1 即减速）

标准参考
  GB/T 11361   同步带传动 梯形齿带轮
  GB/T 11616   同步带 尺寸系列
  ISO 5294 / ISO 5296  同步带与带轮国际系列
  GB/T 1357    渐开线圆柱齿轮 模数
  GB/T 10095   渐开线圆柱齿轮 精度制
  GB/T 3480    渐开线圆柱齿轮承载能力计算方法
  机械设计手册 / 米思米 · 盖茨 · 优霓塔样本（带轮最小齿数、节顶距取值）

⚠ 本内核给出的是工程通用设计值。量产前请以最新版标准原文与供应商样本复核，
  尤其是带轮最小齿数、节顶距实测值以及有安全强制要求的场合。
"""

from __future__ import annotations

import math

# =====================================================================
# 一、同步带齿形数据表
# =====================================================================
# p     节距 (mm)
# delta 节顶距 —— 齿顶圆相对节圆的单边缩减量 (mm)，OD = PD − 2·delta
# family 齿形族：T 梯形齿(公制) / HTD / S 圆弧齿 / ST 圆弧齿 / 英制
#
# 说明：delta 取行业通行值（盖茨 / 优霓塔 / 米思米样本一致口径）。
#      GB/T 11361 与 ISO 5294 未强制规定该值，实际供货略有差异，
#      精确建模时请以所选品牌样本为准。
BELT_PROFILES = [
    # ---- S 系列（圆弧齿，日系，平顶）----
    {"code": "S2M",  "p": 2.0,   "delta": 0.254, "family": "S 圆弧齿"},
    {"code": "S3M",  "p": 3.0,   "delta": 0.381, "family": "S 圆弧齿"},
    {"code": "S5M",  "p": 5.0,   "delta": 0.508, "family": "S 圆弧齿"},
    {"code": "S8M",  "p": 8.0,   "delta": 0.686, "family": "S 圆弧齿"},
    {"code": "S14M", "p": 14.0,  "delta": 1.016, "family": "S 圆弧齿"},
    # ---- HTD（圆弧齿，欧美常用）----
    {"code": "3M",   "p": 3.0,   "delta": 0.254, "family": "HTD 圆弧齿"},
    {"code": "5M",   "p": 5.0,   "delta": 0.381, "family": "HTD 圆弧齿"},
    {"code": "8M",   "p": 8.0,   "delta": 0.686, "family": "HTD 圆弧齿"},
    {"code": "14M",  "p": 14.0,  "delta": 1.016, "family": "HTD 圆弧齿"},
    {"code": "20M",  "p": 20.0,  "delta": 1.524, "family": "HTD 圆弧齿"},
    # ---- T 系列（梯形齿，公制节距）----
    {"code": "T2.5", "p": 2.5,   "delta": 0.254, "family": "T 梯形齿"},
    {"code": "T5",   "p": 5.0,   "delta": 0.381, "family": "T 梯形齿"},
    {"code": "T10",  "p": 10.0,  "delta": 0.508, "family": "T 梯形齿"},
    {"code": "T20",  "p": 20.0,  "delta": 0.762, "family": "T 梯形齿"},
    {"code": "AT5",  "p": 5.0,   "delta": 0.381, "family": "AT 梯形齿"},
    {"code": "AT10", "p": 10.0,  "delta": 0.508, "family": "AT 梯形齿"},
    # ---- 2M / 3M 小型 ----
    {"code": "2M",   "p": 2.0,   "delta": 0.254, "family": "HTD 圆弧齿"},
    # ---- 英制系列（节距为英寸折算）----
    {"code": "MXL",  "p": 2.032, "delta": 0.254, "family": "英制梯形齿"},
    {"code": "XL",   "p": 5.080, "delta": 0.254, "family": "英制梯形齿"},
    {"code": "L",    "p": 9.525, "delta": 0.381, "family": "英制梯形齿"},
    {"code": "H",    "p": 12.700, "delta": 0.508, "family": "英制梯形齿"},
    {"code": "XH",   "p": 22.225, "delta": 1.016, "family": "英制梯形齿"},
    {"code": "XXH",  "p": 31.750, "delta": 1.524, "family": "英制梯形齿"},
]

BELT_BY_CODE = {b["code"]: b for b in BELT_PROFILES}
BELT_CODES = [b["code"] for b in BELT_PROFILES]
BELT_FAMILIES = ["全部"] + sorted({b["family"] for b in BELT_PROFILES})

# 带轮最小齿数经验值（避免啮合齿数不足与齿根应力过大）
_MIN_TEETH_HINT = {
    "S2M": 12, "S3M": 14, "S5M": 14, "S8M": 18, "S14M": 22,
    "2M": 12, "3M": 14, "5M": 14, "8M": 18, "14M": 22, "20M": 26,
    "T2.5": 12, "T5": 14, "T10": 16, "T20": 20, "AT5": 14, "AT10": 16,
    "MXL": 10, "XL": 10, "L": 12, "H": 14, "XH": 18, "XXH": 24,
}


def belt_profile(p_code: str) -> dict:
    b = BELT_BY_CODE.get(p_code)
    if b is None:
        raise DesignError(f"未知齿形：{p_code}")
    return b


def min_teeth(p_code: str) -> int:
    """该齿形推荐的最少带轮齿数。"""
    return _MIN_TEETH_HINT.get(p_code, 14)


# =====================================================================
# 二、同步带传动几何
# =====================================================================

def pulley_pitch_dia(z: float, p: float) -> float:
    """节圆直径 PD = Z·P/π。"""
    return z * p / math.pi


def pulley_outside_dia(pd: float, delta: float) -> float:
    """齿顶圆直径 OD = PD − 2δ。"""
    return pd - 2.0 * delta


def pulley_root_dia(pd: float, delta: float) -> float:
    """齿根圆直径（工程近似）：Df = PD − 2·(δ + h_t)，齿高按节距经验取值。

    同步带带轮齿高没有统一公式，这里按行业常用值估算，仅用于示意与
    结构参考；正式出图请查所选齿形的标准齿槽图。
    """
    ht = _tooth_height(pd, delta)
    return pd - 2.0 * (delta + ht)


def _tooth_height(pd: float, delta: float) -> float:
    """齿高近似：按节顶距线性外推的常用经验关系 ht ≈ 2.35·δ（参考值）。"""
    return 2.35 * delta


def belt_teeth_to_length(zb: float, p: float) -> float:
    """带长 L = Zb·P。"""
    return zb * p


def length_to_belt_teeth(L: float, p: float) -> float:
    return L / p


def belt_circle_dia(L: float) -> float:
    """带圆形直径 = L/π（把带摊平成一个圆时的直径，用于快速估算）。"""
    return L / math.pi


def belt_length_simple(cd: float, pd1: float, pd2: float) -> float:
    """简化带长公式：L ≈ 2·CD + π(PD1+PD2)/2。"""
    return 2.0 * cd + math.pi * (pd1 + pd2) / 2.0


def center_distance_simple(L: float, p: float, z1: float, z2: float) -> float:
    """由带长反算中心距（参考表格口径）：CD = (L − (Z1+Z2)·P/2) / 2。

    等价于 L ≈ 2·CD + π(PD1+PD2)/2，两轮齿数相等时是精确解，
    齿数差较大时略有偏差，此时可参考程序给出的「精确解」。
    """
    return (L - (z1 + z2) * p / 2.0) / 2.0


def center_distance_exact(L: float, pd1: float, pd2: float,
                          lo: float = 1e-3, hi: float = 1e7) -> float:
    """精确中心距：数值求解 L = 2C·cosφ + π(D1+D2)/2 + φ(D2−D1)。

    其中 φ = asin((D2−D1)/(2C))（弧度）。用二分法，保证在齿数差较大时
    依然给出与带长严格对应的中心距。
    """
    d1, d2 = sorted((pd1, pd2))
    diff = d2 - d1

    def f(c: float) -> float:
        s = min(0.999999, (diff / 2.0) / c) if c > 0 else 1.0
        phi = math.asin(s)
        return 2.0 * c * math.cos(phi) + math.pi * (d1 + d2) / 2.0 + phi * diff

    lo = max(lo, diff / 2.0 + 1e-6)
    while f(hi) < L and hi < 1e8:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if f(mid) < L:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def wrap_angle(pd_small: float, pd_large: float, cd: float) -> float:
    """小轮包角（度）：θ = 180° − 2·asin((D大−D小)/(2·CD))。"""
    if cd <= 0:
        raise DesignError("中心距必须为正数")
    k = (pd_large - pd_small) / (2.0 * cd)
    k = max(-1.0, min(1.0, k))
    return 180.0 - 2.0 * math.degrees(math.asin(k))


def mesh_teeth(z_small: float, theta_deg: float) -> float:
    """小轮啮合齿数 Zm = Z·θ/360。"""
    return z_small * theta_deg / 360.0


def belt_speed(pd: float, n_rpm: float) -> float:
    """带速 v = π·PD·n / 60000  (m/s)，PD 单位 mm，n 单位 r/min。"""
    return math.pi * pd * n_rpm / 60000.0


def belt_linear_speed_to_rpm(v: float, unit: str, pd: float) -> float:
    """由带速反算带轮转速 (r/min)。v 单位：mm/s | m/min | km/h。"""
    mm_per_min = {
        "mm/s": v * 60.0,
        "m/min": v * 1000.0,
        "km/h": v * 1000.0 * 1000.0 / 60.0,
    }.get(unit)
    if mm_per_min is None:
        raise DesignError(f"未知速度单位：{unit}")
    if pd <= 0:
        raise DesignError("节圆直径必须为正数")
    return mm_per_min / (math.pi * pd)


SPEED_UNITS = {
    "mm/s": 1.0,          # → mm/s
    "m/min": 1000.0 / 60.0,
    "km/h": 1000.0 * 1000.0 / 3600.0,
}


def speed_to_mm_s(v: float, unit: str) -> float:
    k = SPEED_UNITS.get(unit)
    if k is None:
        raise DesignError(f"未知速度单位：{unit}")
    return v * k


# =====================================================================
# 三、齿轮几何
# =====================================================================

# GB/T 1357 渐开线圆柱齿轮模数系列 (mm)
MODULE_FIRST = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0,
                10.0, 12.0, 16.0, 20.0, 25.0, 32.0, 40.0, 50.0]
MODULE_SECOND = [1.125, 1.375, 1.75, 2.25, 2.75, 3.5, 4.5, 5.5, 7.0,
                 9.0, 11.0, 14.0, 18.0, 22.0, 28.0, 36.0, 45.0]
MODULES_ALL = sorted(MODULE_FIRST + MODULE_SECOND)
MODULE_MIN, MODULE_MAX = 0.1, 100.0

PRESSURE_ANGLES = [14.5, 20.0, 25.0]

# 常用齿轮齿数（便于快速选取）
TEETH_PRESETS = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                 24, 25, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 45, 48, 50,
                 52, 54, 56, 58, 59, 60, 64, 68, 72, 76, 80, 90, 100, 120]


def inv(alpha_rad: float) -> float:
    """渐开线函数 inv α = tan α − α。"""
    return math.tan(alpha_rad) - alpha_rad


def solve_inv(y: float) -> float:
    """由 inv 值反求压力角（弧度），二分法。"""
    lo, hi = 1e-6, math.radians(60.0)
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if inv(mid) < y:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def gear_geometry(z: float, mn: float, alpha_deg: float = 20.0,
                  beta_deg: float = 0.0, x: float = 0.0,
                  ha_star: float = 1.0, c_star: float = 0.25) -> dict:
    """单只齿轮的几何尺寸。

    z     齿数
    mn    法向模数 (mm)
    alpha 法向压力角 (°)
    beta  螺旋角 (°)，0 为直齿
    x     法向变位系数
    """
    if z <= 0:
        raise DesignError("齿数必须为正数")
    if mn <= 0:
        raise DesignError("模数必须为正数")
    beta = math.radians(beta_deg)
    alpha = math.radians(alpha_deg)
    if not (0.0 <= abs(beta_deg) < 45.0):
        raise DesignError("螺旋角应在 −45° ~ 45° 之间")

    cosb = math.cos(beta)
    if cosb <= 1e-6:
        raise DesignError("螺旋角过大")

    # 端面参数
    mt = mn / cosb                                  # 端面模数
    alpha_t = math.atan(math.tan(alpha) / cosb)     # 端面压力角

    d = mt * z                                      # 分度圆直径
    da = d + 2.0 * mn * (ha_star + x)               # 齿顶圆直径
    df = d - 2.0 * mn * (ha_star + c_star - x)      # 齿根圆直径
    db = d * math.cos(alpha_t)                      # 基圆直径
    h = (2.0 * ha_star + c_star) * mn               # 全齿高
    ha = mn * (ha_star + x)                         # 齿顶高
    hf = mn * (ha_star + c_star - x)                # 齿根高

    # 端面齿厚 / 法向弦齿厚（分度圆处）
    st = mt * (math.pi / 2.0 + 2.0 * x * math.tan(alpha))
    sn = st * cosb

    zmin = 2.0 * ha_star / (math.sin(alpha) ** 2)   # 不根切最小齿数（x=0）
    xmin = ha_star - z * math.sin(alpha) ** 2 / 2.0  # 该齿数下的最小变位系数

    return {
        "z": z, "mn": mn, "mt": mt,
        "alpha": alpha_deg, "alpha_t": math.degrees(alpha_t),
        "beta": beta_deg, "x": x,
        "d": d, "da": da, "df": df, "db": db,
        "h": h, "ha": ha, "hf": hf,
        "p": math.pi * mn,          # 法向齿距
        "pt": math.pi * mt,         # 端面齿距
        "st": st, "sn": sn,
        "zmin": zmin, "xmin": xmin,
        # 容差 0.01：z=17 时 xmin≈0.0057，属工程上可忽略的临界量，
        # 报根切反而会误导；真正缺量才提示。
        "undercut": (xmin - x) > 0.01,
    }


def gear_pair(z1: float, z2: float, mn: float, alpha_deg: float = 20.0,
              beta_deg: float = 0.0, x1: float = 0.0, x2: float = 0.0,
              ha_star: float = 1.0, c_star: float = 0.25) -> dict:
    """一对啮合齿轮：各自几何 + 中心距 + 传动比。

    返回的 i 为「输出转速 / 输入转速」= Z1 / Z2（Z1 为主动轮）；
    减速比 u = Z2 / Z1 = 1 / i。
    """
    g1 = gear_geometry(z1, mn, alpha_deg, beta_deg, x1, ha_star, c_star)
    g2 = gear_geometry(z2, mn, alpha_deg, beta_deg, x2, ha_star, c_star)

    beta = math.radians(beta_deg)
    alpha = math.radians(alpha_deg)
    cosb = math.cos(beta)

    x_sum = x1 + x2
    z_sum = z1 + z2

    if abs(x_sum) < 1e-12:
        alpha_w = alpha
        y = 0.0
    else:
        # 无侧隙啮合方程：inv αw = inv α + 2(x1+x2)·tanα / (z1+z2)
        y_inv = inv(alpha) + 2.0 * x_sum * math.tan(alpha) / z_sum
        alpha_w = solve_inv(y_inv)
        # 中心距变动系数 y = (z1+z2)/2 · (cosα/cosαw − 1)
        y = z_sum / 2.0 * (math.cos(alpha) / math.cos(alpha_w) - 1.0)

    a_std = mn * z_sum / (2.0 * cosb)               # 标准中心距
    a = a_std + y * mn                              # 实际中心距

    return {
        "g1": g1, "g2": g2,
        "z1": z1, "z2": z2, "mn": mn,
        "a_std": a_std, "a": a, "y": y,
        "alpha_w": math.degrees(alpha_w),
        "i": z1 / z2 if z2 else 0.0,
        "u": z2 / z1 if z1 else 0.0,
        "modulated": abs(x_sum) > 1e-12,
    }


def gear_ratio_from_teeth(z_driver: float, z_driven: float) -> float:
    """单级传动比（输出/输入转速比）= Z主动 / Z从动。"""
    if z_driven <= 0:
        raise DesignError("从动轮齿数必须为正数")
    return z_driver / z_driven


# =====================================================================
# 四、多级传动链
# =====================================================================
# 每一级是一个 dict：
#   kind : "gear" 齿轮级 | "belt" 同步带级
#   name : 级名称
#   z1   : 主动侧齿数
#   z2   : 从动侧齿数
#   m    : 模数（齿轮级）
#   p    : 节距（同步带级）
#   reverse : 是否换向（仅记录 1 或 −1）
#
# 传动比 i = Π(z1/z2)，即「输出转速 / 输入转速」。i < 1 表示减速。


def chain_compute(stages: list[dict]) -> dict:
    """串联传动链：逐级累计传动比与累计中心距。"""
    out = []
    i_total = 1.0
    a_total = 0.0
    for idx, s in enumerate(stages):
        kind = s.get("kind", "gear")
        z1 = float(s["z1"])
        z2 = float(s["z2"])
        if z1 <= 0 or z2 <= 0:
            raise DesignError(f"第 {idx + 1} 级「{s.get('name', '')}」齿数必须为正数")
        i = z1 / z2
        i_total *= i

        item = {
            "index": idx + 1,
            "name": s.get("name") or f"第 {idx + 1} 级",
            "kind": kind,
            "z1": z1, "z2": z2,
            "i": i, "u": z2 / z1 if z1 else 0.0,
            "i_cum": i_total,
        }

        if kind == "belt":
            prof = belt_profile(s.get("p_code") or "S8M")
            p = float(s.get("p", prof["p"]))
            delta = float(s.get("delta", prof["delta"]))
            pd1 = pulley_pitch_dia(z1, p)
            pd2 = pulley_pitch_dia(z2, p)
            item.update({
                "p": p, "delta": delta, "profile": prof["code"],
                "pd1": pd1, "pd2": pd2,
                "od1": pulley_outside_dia(pd1, delta),
                "od2": pulley_outside_dia(pd2, delta),
                "a_ref": (pd1 + pd2) / 2.0,
                "label": f"{prof['code']} 同步带级",
            })
        else:
            mn = float(s.get("m", 2.0))
            if mn <= 0:
                raise DesignError(f"第 {idx + 1} 级模数必须为正数")
            beta = float(s.get("beta", 0.0))
            gp = gear_pair(z1, z2, mn, beta_deg=beta)
            item.update({
                "m": mn, "beta": beta,
                "d1": gp["g1"]["d"], "d2": gp["g2"]["d"],
                "da1": gp["g1"]["da"], "da2": gp["g2"]["da"],
                "a_ref": gp["a"], "a_std": gp["a_std"],
                "label": f"m{mn:g} 齿轮级",
            })
        a_total += item["a_ref"]
        out.append(item)

    return {
        "stages": out,
        "i_total": i_total,
        "u_total": (1.0 / i_total) if i_total else 0.0,
        "a_total": a_total,
    }


# =====================================================================
# 五、整机速度换算
# =====================================================================

def wheel_from_linear_speed(v_mm_s: float, radius: float) -> dict:
    """由线速度与轮半径求角速度与转速。

    ω = v / R   (rad/s)      n = 60·v / (2π·R)   (r/min)
    """
    if radius <= 0:
        raise DesignError("驱动轮半径必须为正数")
    omega = v_mm_s / radius
    n = omega * 60.0 / (2.0 * math.pi)
    return {"omega": omega, "rpm": n}


def radial_speed(pd: float, v_mm_s: float) -> dict:
    """按节圆直径求角速度 / 转速（等价于半径 = PD/2）。"""
    return wheel_from_linear_speed(v_mm_s, pd / 2.0)


def driven_speed(omega_in: float, i: float) -> float:
    """经传动比 i（输出/输入）后的角速度：ω_out = ω_in · i。"""
    return omega_in * i


def rpm_of(omega: float) -> float:
    return omega * 60.0 / (2.0 * math.pi)


def linear_speed(omega: float, radius: float) -> float:
    """线速度 (mm/s) = ω · R。"""
    return omega * radius


def system_compute(v: float, unit: str, wheel_radius: float,
                   i_drive: float, brush_radius: float,
                   i_brush_from_wheel: float) -> dict:
    """整机速度汇总。

    v                    行走速度（unit 指定单位）
    wheel_radius         驱动轮（履带驱动轮）半径 mm
    i_drive              驱动轮之前的累计传动比（输出/输入），由传动链给出
    brush_radius         执行机构（滚刷）半径 mm
    i_brush_from_wheel   滚刷相对驱动轮的传动比（输出/输入）
    """
    v_mm_s = speed_to_mm_s(v, unit)
    w = wheel_from_linear_speed(v_mm_s, wheel_radius)

    omega_wheel = w["omega"]
    omega_motor = omega_wheel / i_drive if i_drive else 0.0
    omega_brush = omega_wheel * i_brush_from_wheel
    v_brush = linear_speed(omega_brush, brush_radius)

    return {
        "v_input": v, "unit": unit, "v_mm_s": v_mm_s,
        "wheel_radius": wheel_radius,
        "omega_wheel": omega_wheel, "rpm_wheel": rpm_of(omega_wheel),
        "i_drive": i_drive,
        "omega_motor": omega_motor, "rpm_motor": rpm_of(omega_motor),
        "ratio_brush_wheel": i_brush_from_wheel,
        "omega_brush": omega_brush, "rpm_brush": rpm_of(omega_brush),
        "brush_radius": brush_radius,
        "v_brush": v_brush,
        "k_walk_brush": (v_brush / v_mm_s) if v_mm_s else 0.0,
    }


# =====================================================================
# 六、统一解算入口：同步带传动
# =====================================================================

class DesignError(ValueError):
    """输入参数不合法。"""


def design_belt(profile_code: str = "S8M",
                z1: float = 47,
                z2: float = 47,
                belt_teeth: float | None = 120,
                p: float | None = None,
                delta: float | None = None,
                center_distance: float | None = None) -> dict:
    """同步带传动解算。

    z1 / z2            主 / 从动带轮齿数
    belt_teeth         带齿数（与 center_distance 二者给一个）
    center_distance    已知中心距时反算所需带齿数并列标准带长推荐
    p / delta          可覆盖齿形数据表中的节距与节顶距
    """
    warnings: list[str] = []
    notes: list[str] = []

    prof = belt_profile(profile_code)
    P = float(p) if p else prof["p"]
    D = float(delta) if delta is not None else prof["delta"]
    if P <= 0 or D < 0:
        raise DesignError("节距必须为正数、节顶距不能为负数")
    if z1 <= 0 or z2 <= 0:
        raise DesignError("带轮齿数必须为正数")

    pd1 = pulley_pitch_dia(z1, P)
    pd2 = pulley_pitch_dia(z2, P)
    od1 = pulley_outside_dia(pd1, D)
    od2 = pulley_outside_dia(pd2, D)

    # ---- 带长与中心距 ----
    reverse_teeth = None
    if center_distance is not None:
        if center_distance <= abs(pd2 - pd1) / 2.0 + 1e-6:
            raise DesignError("中心距过小：两带轮无法容下（应大于两节圆半径差的一半）")
        L_need = belt_length_simple(center_distance, pd1, pd2)
        zb_need = L_need / P
        zb = float(round(zb_need))
        if zb < 1:
            raise DesignError("按该中心距计算的带齿数不合理，请检查输入")
        belt_teeth = zb
        reverse_teeth = {
            "zb_ideal": zb_need,
            "zb_std": zb,
            "L_std": zb * P,
            "cd_at_std": center_distance_simple(zb * P, P, z1, z2),
        }
        if abs(zb_need - zb) > 0.35:
            notes.append(
                f"按中心距 {center_distance:.2f} mm 算得需要 {zb_need:.2f} 齿，"
                f"标准带齿数为整数，已取 {zb:.0f} 齿（带长 {zb * P:.1f} mm），"
                f"对应中心距 {reverse_teeth['cd_at_std']:.2f} mm；"
                f"实际装配时通过张紧机构调整中心距即可。")

    if belt_teeth is None:
        raise DesignError("请填写带齿数，或填写中心距由程序反算")
    if belt_teeth <= 0:
        raise DesignError("带齿数必须为正数")

    L = belt_teeth_to_length(belt_teeth, P)
    cd = center_distance_simple(L, P, z1, z2)

    if cd <= abs(pd2 - pd1) / 2.0 + 1e-6:
        raise DesignError(
            "由该带齿数反算的中心距过小，两带轮会相碰，请增加带齿数或减小带轮齿数")

    cd_exact = center_distance_exact(L, pd1, pd2)
    theta = wrap_angle(pd1, pd2, cd)
    zm = mesh_teeth(min(z1, z2), theta)
    i = z2 / z1 if z1 else 0.0
    u = z1 / z2 if z2 else 0.0
    circle_dia = belt_circle_dia(L)
    speed_ratio = (pd2 / pd1) if pd1 else 0.0

    # ---- 校核 ----
    k = min_teeth(profile_code)
    if min(z1, z2) < k:
        warnings.append(
            f"小带轮齿数 {min(z1, z2):.0f} 小于 {profile_code} 的推荐最少齿数 {k}，"
            f"齿根应力与啮合噪音会明显上升，建议增大齿数或降低转速。")

    if z1 != z2 and theta < 120.0:
        warnings.append(
            f"小带轮包角 {theta:.1f}° 小于 120°，啮合齿数不足会导致跳齿与带齿磨损，"
            f"建议增大中心距、减小两轮齿数差，或加装张紧惰轮。")
    if zm < 6.0:
        warnings.append(
            f"小带轮啮合齿数仅 {zm:.2f}（建议 ≥ 6），请增大包角或带轮齿数。")

    if z1 != z2:
        notes.append(
            f"两带轮齿数不等，简化公式给出的中心距为 {cd:.2f} mm，"
            f"按带长精确求解为 {cd_exact:.2f} mm，差 {abs(cd_exact - cd):.2f} mm；"
            f"精确解已计入带在两轮上的包角差异，出图建议采用精确解。")

    notes.append(
        f"节顶距 δ = {D:.3f} mm 取行业通行值（OD = PD − 2δ）；"
        f"不同品牌齿槽略有差异，精加工前请核对所选品牌样本的齿槽图。")

    return {
        "input": {
            "profile": profile_code, "p": P, "delta": D,
            "z1": z1, "z2": z2, "belt_teeth": belt_teeth,
            "center_distance_input": center_distance,
        },
        "pulley1": {
            "z": z1, "pd": pd1, "od": od1,
            "df": pulley_root_dia(pd1, D),
            "circumference": math.pi * pd1,
        },
        "pulley2": {
            "z": z2, "pd": pd2, "od": od2,
            "df": pulley_root_dia(pd2, D),
            "circumference": math.pi * pd2,
        },
        "belt": {
            "teeth": belt_teeth, "length": L,
            "circle_dia": circle_dia,
        },
        "geom": {
            "cd": cd, "cd_exact": cd_exact,
            "wrap_angle": theta, "mesh_teeth": zm,
            "cd_a_ref": (pd1 + pd2) / 2.0,
        },
        "metrics": {
            "i": i, "u": u, "speed_ratio": speed_ratio,
            "theta": theta, "mesh_teeth": zm,
            "min_teeth": k,
        },
        "reverse": reverse_teeth,
        "warnings": warnings,
        "notes": notes,
    }


# =====================================================================
# 七、统一解算入口：单对齿轮
# =====================================================================

def design_gears(z1: float = 17, z2: float = 51, mn: float = 2.0,
                 alpha_deg: float = 20.0, beta_deg: float = 0.0,
                 x1: float = 0.0, x2: float = 0.0) -> dict:
    """齿轮副解算：几何 + 中心距 + 传动比 + 校核。"""
    warnings: list[str] = []
    notes: list[str] = []

    if not (MODULE_MIN <= mn <= MODULE_MAX):
        raise DesignError(f"模数应在 {MODULE_MIN} ~ {MODULE_MAX} mm 之间")
    if z1 <= 0 or z2 <= 0:
        raise DesignError("齿数必须为正数")
    if z1 < 6 or z2 < 6:
        warnings.append("齿数小于 6 的齿轮已接近极限，请确认加工与啮合可行性。")

    gp = gear_pair(z1, z2, mn, alpha_deg, beta_deg, x1, x2)
    g1, g2 = gp["g1"], gp["g2"]

    # 模数是否属于标准系列
    near = min(MODULES_ALL, key=lambda v: abs(v - mn))
    if abs(near - mn) > 1e-6:
        notes.append(
            f"模数 {mn:g} 不属于 GB/T 1357 标准系列，最接近的标准模数为 {near:g}，"
            f"非标模数需定制滚刀，成本与交期都会上升。")

    for tag, g in (("小齿轮", g1), ("大齿轮", g2)):
        if g["undercut"]:
            warnings.append(
                f"{tag}（z={g['z']:.0f}）在变位系数 x={g['x']:.2f} 下会根切："
                f"该齿数要求 x ≥ {g['xmin']:.3f}（不根切最小齿数 {g['zmin']:.1f}），"
                f"请增大变位系数或增加齿数。")

    if abs(beta_deg) > 1e-9:
        notes.append(
            f"斜齿轮 β = {beta_deg:g}°，端面模数 mt = {g1['mt']:.4f} mm，"
            f"端面压力角 αt = {g1['alpha_t']:.3f}°；轴向力 Fa ∝ tanβ，"
            f"请确认轴承能承受由此产生的轴向载荷。")

    if gp["modulated"]:
        notes.append(
            f"变位齿轮副 x₁+x₂ = {x1 + x2:g}：啮合角 αw = {gp['alpha_w']:.3f}°，"
            f"中心距变动系数 y = {gp['y']:.4f}，实际中心距 a = {gp['a']:.4f} mm"
            f"（标准中心距 {gp['a_std']:.4f} mm）。")
    else:
        notes.append("未使用变位（x₁ = x₂ = 0），中心距为标准中心距。")

    return {
        "input": {"z1": z1, "z2": z2, "mn": mn, "alpha": alpha_deg,
                  "beta": beta_deg, "x1": x1, "x2": x2},
        "pair": gp,
        "metrics": {
            "i": gp["i"], "u": gp["u"],
            "a": gp["a"], "a_std": gp["a_std"],
            "alpha_w": gp["alpha_w"],
            "center_shift": gp["a"] - gp["a_std"],
        },
        "warnings": warnings,
        "notes": notes,
    }


# =====================================================================
# 八、自检
# =====================================================================

if __name__ == "__main__":
    print("=" * 72)
    print("同步带 S8M · Z1=Z2=47 · Zb=120（对照参考表格）")
    r = design_belt("S8M", 47, 47, 120)
    p1, p2, b, g = r["pulley1"], r["pulley2"], r["belt"], r["geom"]
    print(f"  PD1 = {p1['pd']:.6f}  OD1 = {p1['od']:.6f}")
    print(f"  PD2 = {p2['pd']:.6f}  OD2 = {p2['od']:.6f}")
    print(f"  L   = {b['length']:.6f}   带圆直径 = {b['circle_dia']:.6f}")
    print(f"  CD  = {g['cd']:.6f}   传动比 i = {r['metrics']['i']:.6f}")
    for w in r["warnings"]:
        print("  ⚠", w)

    print("=" * 72)
    print("齿轮 m2 · Z1=17 · Z2=51（对照 2526 齿轮表）")
    r2 = design_gears(17, 51, 2.0)
    g1, g2 = r2["pair"]["g1"], r2["pair"]["g2"]
    print(f"  d1 = {g1['d']:.4f}   d2 = {g2['d']:.4f}   a = {r2['metrics']['a']:.4f}")
    print(f"  i  = {r2['metrics']['i']:.6f}   i 累计（电机→主动轮）= "
          f"{gear_ratio_from_teeth(17, 20) * gear_ratio_from_teeth(20, 51):.6f}")
    for w in r2["warnings"]:
        print("  ⚠", w)
