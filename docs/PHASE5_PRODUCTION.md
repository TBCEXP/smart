# Phase 5 — 大货实拍 AI

## 功能

| 能力 | 说明 |
|------|------|
| OpenCV ORB 对齐 | 实拍图与确稿 homography 对齐（失败则 resize 回退） |
| 像素差异 | 对齐后计算 diff 百分比 |
| 人工终审 | `PATCH .../review` 通过/驳回 |
| 规则判定 | `passed` / `warnings` / `failed`（辅助人工，非 LLM） |

## API

| 端点 | 说明 |
|------|------|
| `GET/POST /api/inspections/production` | 检测任务 |
| `POST /api/inspections/production/{id}/run` | OpenCV 比对 |
| `PATCH /api/inspections/production/{id}/review` | 人工终审 |

## 验收

```bash
bash scripts/phase5_verify.sh http://127.0.0.1:8000
```

## 员工后台

`/admin/dashboard` → **大货实拍** Tab。

## 依赖

- `opencv-python-headless` — 对齐与 diff

## 演示数据

`data/fixtures/inspection/approved_box.png` + `production_photo.png`（启动种子自动绘制）。
