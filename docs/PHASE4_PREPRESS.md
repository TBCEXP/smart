# Phase 4 — 印刷前稿 AI

## 功能

| 能力 | 说明 |
|------|------|
| 条码引擎 | EAN-13 校验位、Code128 字符集；生成 SVG |
| 文本 diff | `difflib` 相似度 + unified diff 预览 |
| 图形 diff | Pillow 像素差异百分比（规则阈值） |
| OCR 提取 | Tesseract 自动提取标签文字（Docker 默认启用） |
| 条码识图 | ZBar 从图片解码 EAN/Code128（Docker 默认启用） |
| 规则引擎 | 综合判定 `passed` / `warnings` / `failed`（非 LLM） |

## API

| 端点 | 说明 |
|------|------|
| `POST /api/prepress/barcode/validate` | 条码校验 |
| `POST /api/prepress/barcode/generate` | 生成条码 SVG |
| `GET /api/prepress/barcode/scan/status` | ZBar 是否可用 |
| `POST /api/prepress/barcode/scan` | 从 fixture/本地图识别条码 |
| `POST /api/prepress/ocr/extract` | 从 fixture/本地图提取文字 |
| `GET/POST /api/prepress/reviews` | 比对任务列表/创建 |
| `POST /api/prepress/reviews/{id}/run` | 运行比对（需 admin 登录） |

## 验收

```bash
bash scripts/phase4_verify.sh http://127.0.0.1:8000
```

## 员工后台

`/admin/dashboard` → **印刷前稿** Tab：列表、创建任务、运行比对、查看 verdict。

## 演示数据

启动时种子任务使用 `data/fixtures/prepress/` 下的参考图/候选图（自动绘制）。

## 后续扩展

- tus 断点续传（大文件）
