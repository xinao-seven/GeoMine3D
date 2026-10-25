"""GeoMine3D 钻孔地质建模引擎(移植自毕业论文细层化管线)。

输入: 14层汇总长表(钻孔名称/地层名称/深度/厚度) + 钻孔位置表(name/x/y/z);
输出: web 交付包(catalog.json + 分层 GLB/LOD/VTU + 20 倍竖向缩放副本)。

管线对应论文仓库的:
- chapter04 build_refined_surfaces.py → surfaces.py(共享趋势+逐界面ARD GP + 保序投影/尖灭折叠)
- chapter05 build_chapter05_web_package_refined.py → package_builder.py(TIN-GTP 建模 + 交付包导出)
- src/modeling/prism_model_builder.py、src/modeling/model_package_export.py → 原样移植

与论文脚本的差异(服务化改造):
- 全部输入输出路径参数化,不依赖论文仓库目录;
- 不生成论文图件/预览截图,不复制井巷 GLB(roadways/working_faces 为锦界专属数据);
- 网格节点数/界面数由数据动态决定,去掉 (15, 16641) 硬断言;
- 层序由上传分层表的层顶深度自动推导,替代人工维护的 strat_order_refined.json。
"""
