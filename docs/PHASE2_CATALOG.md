# Phase 2 — 工厂目录与分享

> PDF 文件存 **Cloudflare R2**（不进 VPS）；VPS/DB 仅存元数据与授权矩阵。

## 已实现

| 能力 | API / 页面 |
|------|------------|
| 目录元数据 | `GET/POST /api/catalog/documents` |
| 客户授权目录 | `GET /api/portal/catalogs`（按 `authorized_emails`） |
| 分享目录 | `POST /api/share/links` `resource_type=catalog` |
| 公开查看 | `/s/{token}` + `GET /api/share/{token}` |

## 目录字段

| 字段 | 说明 |
|------|------|
| `factory_id` | 关联工厂 |
| `title` / `title_en` | 目录名称 |
| `category_l3` | 品类 |
| `file_url` | `r2://bucket/path.pdf` 或 HTTPS |
| `pages` / `file_size_mb` | 元信息 |
| `authorized_emails` | 空列表 = 所有门户客户可见 |

## 种子数据

启动时 `seed_catalog_documents()` 创建 3 份演示目录，`customer@example.com` 可看到其中 2 份。

## R2 对接

1. Tab2 或 env 配置 `r2_account_id` / `r2_access_key_id` / `r2_secret_access_key` / `r2_bucket`
2. 上传脚本 `bash scripts/upload_catalog_r2.sh BASE_URL DOC_ID file.pdf SESSION_TOKEN`
3. API 自动解析 `r2://` 为签名下载 URL；门户与分享页显示「下载 PDF」

| API | 说明 |
|-----|------|
| `GET /api/catalog/documents/{id}/download-url` | 门户/员工获取签名下载链接 |
| `POST /api/catalog/documents/{id}/upload-url` | 员工生成预签名上传 URL |

未配置 R2 时 `storage=r2_pending`，`download_url=null`（Mock 验收仍可通过）。

## 验收

```bash
bash scripts/phase2_verify.sh http://127.0.0.1:8000
```
