"""建模引擎命令行入口:钻孔 Excel → 完整 web 交付包。

用法(由 app/services/modeling_service.py 以子进程调用):

    python -m modeling_engine.generate \
        --strata <14层汇总长表.xlsx> --location <钻孔位置.xlsx> \
        --out <web_package输出目录> --result-json <结果JSON路径> \
        [--grid-spacing 100] [--boundary-padding 200] \
        [--pinchout-threshold 0.5] [--z-scale 20] [--save-surfaces <npz路径>]

进度逐行打到 stdout;最终结果(孔数/层序/原点/体积/耗时/被跳过的孔)写入
--result-json 指向的文件,供后端注册数据库时消费。任何一步失败以非零码退出,
stderr 带完整堆栈。

产物为双轨几何(见 modeling_engine/__init__.py):根目录 ``L*.glb``/
``model_combined.glb``/``z20/``/``lods/`` 为含内部棱柱壁的渲染轨,
``shells/*_shell.glb`` 为闭合壳分析轨。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path

import numpy as np


# 进度事件行格式:`[progress] {"stage": ..., "percent": ..., "message": ...}`。
# 后端(app/services/modeling_service.py::_pump_stdout)逐行解析后写 Redis 快照并通过
# SSE 推送。为什么百分比由**引擎**给出而不是前端估算:建模耗时随网格/孔数变化
# 很大(25s vs 数分钟),看上去均匀递增的假进度会让人觉得“卡死了”。
INTERP_RE = re.compile(r"界面插值 (\d+)/(\d+)")


def _log(message: str) -> None:
    """普通日志行（后端写进 engine.log 并节流刷新任务 message）。"""
    print(f"[modeling] {message}", flush=True)


def _emit(stage: str, percent: float, message: str) -> None:
    """输出一条结构化进度事件行（后端解析后写 Redis 并经 SSE 推送）。"""
    payload = {
        "stage": stage,
        "percent": round(max(0.0, min(100.0, percent)), 1),
        "message": message,
    }
    print("[progress] " + json.dumps(payload, ensure_ascii=False), flush=True)


class _Reporter:
    """把建模各阶段的进度归一化到 0-100 并保证单调不回退。

    阶段权重(与 docs/Redis任务队列与进度推送.md 一致):
    解析 0-5、界面插值 5-40、保序投影 45、TIN-GTP 55、自洽校验 75、
    导出交付包 78-92、完成 95,最后的 100 由后端“注册数据”阶段补上。
    """

    def __init__(self) -> None:
        self.percent = 0.0
        self.layers_total = 0
        self.export_done = 0

    def mark(self, stage: str, percent: float, message: str) -> None:
        """推进百分比（只升不降）并发出一帧进度。"""
        self.percent = max(self.percent, float(percent))
        _emit(stage, self.percent, message)

    def report(self, message: str) -> None:
        """子模块(surfaces/package_builder)的文本进度 → 百分比。"""
        _log(message)
        match = INTERP_RE.search(message)
        if match:
            done, total = int(match.group(1)), int(match.group(2))
            self.mark("界面插值", 5 + 35 * done / max(1, total), message)
            return
        if message.startswith("向量化 TIN-GTP"):
            self.mark("TIN-GTP 建模", 55, message)
            return
        if message.startswith("自洽断言"):
            self.mark("自洽校验", 75, message)
            return
        if message.startswith("导出 "):
            self.export_done += 1
            ratio = min(1.0, self.export_done / max(1, self.layers_total))
            self.mark("导出交付包", 78 + 14 * ratio, message)
            return
        # 其余文本(如控制点数、网格规模)只刷新提示语,不推进百分比。
        self.mark("建模中", self.percent, message)


def run(
    strata_path: Path,
    location_path: Path,
    out_dir: Path,
    result_path: Path,
    grid_spacing_m: float = 100.0,
    boundary_padding_m: float = 200.0,
    pinchout_threshold_m: float = 0.5,
    z_scale: float = 20.0,
    z_origin_m: float | None = None,
    surfaces_npz_path: Path | None = None,
) -> dict:
    """执行完整建模管线，返回写入 ``result_path`` 的摘要 dict。

    阶段顺序：解析输入 → 界面点/共享网格 → 共享趋势+ARD GP 插值 → 保序投影/
    尖灭折叠（负厚度即失败）→ 组装交付包。``z_origin_m`` 为空时取孔口高程均值。
    """
    from modeling_engine import data_io, package_builder, surfaces

    reporter = _Reporter()
    timings: dict[str, float] = {}
    t_all = time.time()

    t0 = time.time()
    reporter.mark("解析输入", 0, "开始解析钻孔数据")
    _log(f"解析分层表 {strata_path.name}")
    strata = data_io.parse_strata(strata_path)
    _log(f"分层表: {strata.hole_count} 孔, 列语义 {strata.convention}")
    _log(f"解析位置表 {location_path.name}")
    locations = data_io.parse_locations(location_path)
    _log(f"位置表: {len(locations)} 孔")
    inputs = data_io.build_model_inputs(strata, locations)
    timings["parse_s"] = time.time() - t0
    reporter.layers_total = len(inputs.layers)
    reporter.mark(
        "解析输入",
        5,
        f"参与建模 {len(inputs.boreholes)} 孔, {len(inputs.layers)} 层",
    )

    t0 = time.time()
    interfaces, points, all_points = surfaces.build_interface_points(
        inputs.boreholes, inputs.intervals, inputs.layers
    )
    support = surfaces.expanded_support_grid(
        inputs.boreholes,
        grid_spacing_m=grid_spacing_m,
        boundary_padding_m=boundary_padding_m,
    )
    xy_global = support[["x", "y"]].to_numpy(float)
    reporter.mark("界面插值", 5, f"共享网格 {len(support)} 节点 ({len(interfaces)} 界面)")
    raw, std = surfaces.direct_elevation_surfaces(
        all_points, points, interfaces, support, progress=reporter.report
    )
    reporter.mark("保序投影", 45, "保序投影与尖灭折叠")
    _, corrected, masks = surfaces.zero_thickness_projection(
        raw, std, pinchout_threshold_m=pinchout_threshold_m
    )
    thickness = corrected[:-1] - corrected[1:]
    if np.min(thickness) < -1e-8:
        raise RuntimeError(f"保序投影失败: 最小层厚 {np.min(thickness):.4f} m")
    timings["surfaces_s"] = time.time() - t0

    if surfaces_npz_path is not None:
        surfaces_npz_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            surfaces_npz_path,
            x=xy_global[:, 0], y=xy_global[:, 1],
            corrected=corrected, latent_std=std, pinchout_masks=masks,
            boundary_padding_m=boundary_padding_m,
            pinchout_threshold_m=pinchout_threshold_m,
        )

    t0 = time.time()
    _log("构建交付包")
    result = package_builder.build_web_package(
        xy_global=xy_global,
        surfaces=corrected,
        pinchout_masks=masks,
        latent_std_arr=std,
        pinchout_threshold_m=pinchout_threshold_m,
        layer_names=inputs.layers,
        package_dir=out_dir,
        z_scale=z_scale,
        z_origin_m=z_origin_m,
        source_meta={
            "strata_file": strata_path.name,
            "location_file": location_path.name,
            "engine": "backend/modeling_engine",
        },
        progress=reporter.report,
    )
    timings["package_s"] = time.time() - t0
    timings["total_s"] = time.time() - t_all

    catalog = result["catalog"]
    summary = {
        "ok": True,
        "params": {
            "grid_spacing_m": grid_spacing_m,
            "boundary_padding_m": boundary_padding_m,
            "pinchout_threshold_m": pinchout_threshold_m,
            "z_scale": z_scale,
        },
        "boreholes_used": int(len(inputs.boreholes)),
        "boreholes_in_strata": strata.hole_count,
        "boreholes_in_location": len(locations),
        "skipped_boreholes": inputs.skipped,
        "display_codes": [inputs.display_codes[key] for key in inputs.boreholes["borehole_id"]],
        "layers": [
            {"code": entry["code"], "name_cn": entry["name_cn"], "color_hex": entry["color_hex"]}
            for entry in catalog["layers"]
        ],
        "n_interfaces": catalog["grid"]["interfaces"],
        "shared_nodes": catalog["grid"]["shared_nodes"],
        "origin_restore": catalog["origin_restore"],
        "total_volume_m3": catalog["totals"]["total_volume_m3"],
        "package_dir": str(out_dir),
        "timings": timings,
        "package_summary": result["summary"],
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    reporter.mark("完成", 95, f"引擎完成, 总耗时 {timings['total_s']:.1f}s")
    return summary


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：解析参数 → run()；任何异常打印堆栈并以 1 退出。"""
    parser = argparse.ArgumentParser(description="钻孔 Excel → 三维地质模型交付包")
    parser.add_argument("--strata", required=True, help="14层汇总长表 xlsx")
    parser.add_argument("--location", required=True, help="钻孔位置 xlsx")
    parser.add_argument("--out", required=True, help="web_package 输出目录")
    parser.add_argument("--result-json", required=True, help="结果 JSON 输出路径")
    parser.add_argument("--grid-spacing", type=float, default=100.0)
    parser.add_argument("--boundary-padding", type=float, default=200.0)
    parser.add_argument("--pinchout-threshold", type=float, default=0.5)
    parser.add_argument("--z-scale", type=float, default=20.0)
    parser.add_argument("--z-origin", type=float, default=None,
                        help="显式高程基准(米);替换既有交付包时传入原包基准以保持对齐")
    parser.add_argument("--save-surfaces", default=None, help="中间曲面 npz 输出路径")
    args = parser.parse_args(argv)

    try:
        run(
            strata_path=Path(args.strata),
            location_path=Path(args.location),
            out_dir=Path(args.out),
            result_path=Path(args.result_json),
            grid_spacing_m=args.grid_spacing,
            boundary_padding_m=args.boundary_padding,
            pinchout_threshold_m=args.pinchout_threshold,
            z_scale=args.z_scale,
            z_origin_m=args.z_origin,
            surfaces_npz_path=Path(args.save_surfaces) if args.save_surfaces else None,
        )
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
