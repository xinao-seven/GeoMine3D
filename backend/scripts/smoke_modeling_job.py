"""建模任务端到端冒烟脚本:上传真实 Excel → 轮询 → 校验注册结果。

用法: .venv/Scripts/python.exe scripts/smoke_modeling_job.py [--keep]
默认跑完删除冒烟项目;--keep 保留项目供人工检查。
"""
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
STRATA = Path("../server/data/boreholes/地层汇总14层.xlsx")
LOCATION = Path("../server/data/location/钻孔位置.xlsx")


def main() -> int:
    keep = "--keep" in sys.argv
    with httpx.Client(timeout=120) as client:
        health = client.get(f"{BASE}/health")
        health.raise_for_status()

        with STRATA.open("rb") as f_strata, LOCATION.open("rb") as f_location:
            response = client.post(
                f"{BASE}/api/v1/modeling-jobs",
                data={"name": "冒烟测试-上传建模", "description": "httpx 客户端端到端验证"},
                files={
                    "strata_file": ("地层汇总14层.xlsx", f_strata),
                    "location_file": ("钻孔位置.xlsx", f_location),
                },
            )
        response.raise_for_status()
        job = response.json()["data"]
        job_id, project_id = job["id"], job["project_id"]
        print(f"job={job_id} project={project_id} status={job['status']}")

        name_ok = client.get(f"{BASE}/api/v1/projects/{project_id}").json()["data"]["name"]
        assert name_ok == "冒烟测试-上传建模", f"项目名编码错误: {name_ok!r}"
        print("项目名 UTF-8 编码正确 ✓")

        deadline = time.time() + 300
        while time.time() < deadline:
            data = client.get(f"{BASE}/api/v1/modeling-jobs/{job_id}").json()["data"]
            print(f"  [{int(time.time() - (deadline - 300)):>3}s] {data['status']} | {data.get('message')}")
            if data["status"] in ("completed", "failed"):
                break
            time.sleep(5)

        if data["status"] != "completed":
            print("任务失败:", (data.get("error_message") or "")[:500])
            return 1

        result = data["result_json"]
        print(
            f"建模完成: {result['boreholes_used']} 孔, {len(result['layers'])} 层, "
            f"{result['shared_nodes']} 节点, 耗时 {result['timings']['total_s']:.1f}s"
        )

        registered = result["registered"]
        assert registered["boreholes"] == result["boreholes_used"], "钻孔注册数不一致"
        assert registered["model_assets"] == len(result["layers"]) + 1, "模型资产数不一致"
        print(
            f"注册校验 ✓ 钻孔 {registered['boreholes']} / 分层 {registered['borehole_segments']} / "
            f"资产 {registered['model_assets']}"
        )

        models = client.get(f"{BASE}/api/v1/projects/{project_id}/models").json()["data"]
        l01 = next(m for m in models if m["metadata_json"].get("catalog_code") == "L01")
        file_response = client.get(f"{BASE}/api/v1/models/{l01['id']}/file")
        assert file_response.status_code == 200 and len(file_response.content) > 1_000_000
        print(f"模型文件下载 ✓ ({len(file_response.content) / 1e6:.2f} MB)")
        assert file_response.headers.get("cache-control") == "no-cache, must-revalidate", \
            "模型下载缺少 no-cache"

        # 双轨产物:metadata 应同时给出渲染轨(source_file)与分析轨(shell_file)、LOD 地址
        meta = l01["metadata_json"]
        assert meta["source_file"].endswith("/L01.glb"), meta["source_file"]
        assert meta["shell_file"].endswith("/shells/L01_shell.glb"), meta["shell_file"]
        assert meta["lod_urls"]["lod50"].startswith("/uploads/"), meta["lod_urls"]
        shell_response = client.get(f"{BASE}/api/v1/models/{l01['id']}/file?variant=shell")
        assert shell_response.status_code == 200, shell_response.text
        assert len(shell_response.content) < len(file_response.content), \
            "闭合壳应比重渲染网格小"
        print(
            f"双轨产物 ✓ 渲染 {len(file_response.content) / 1e6:.2f} MB / "
            f"壳 {len(shell_response.content) / 1e6:.2f} MB;LOD {meta['lod_urls']['lod50']}"
        )

        if not keep:
            delete = client.delete(f"{BASE}/api/v1/projects/{project_id}")
            assert delete.status_code == 204
            print("冒烟项目已删除(含文件清理) ✓")
        else:
            print(f"项目保留: /workspace/{project_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
