# Phase 3 — 大文件中转与分享通知

## 功能

| 能力 | 说明 |
|------|------|
| `FileTransfer` 元数据 | 大文件信息存 DB，实体文件存 R2 |
| `GET/POST /api/files/transfers` | 列表与创建 |
| `POST /api/files/transfers/{id}/upload-url` | R2 预签名上传 |
| 分享 `resource_type=file` | `/s/{token}` 公开查看下载 |
| 分享邮件通知 | `POST /api/share/links` + `notify_email: true` |

## 邮件通知

- 配置 Tab2 `resend_api_key` 后走 Resend 实发
- 未配置时写入 `smart-crm/data/auth_emails.log`（与 OTP 相同）

## 验收

```bash
bash scripts/phase3_verify.sh http://127.0.0.1:8000
```

## 员工后台

`/admin/dashboard` → **大文件** Tab：列表、创建元数据、R2 上传 URL、分享+邮件通知。

## 生产依赖（可选）

- R2 凭据：真实大文件上传
- Resend API Key：分享链接邮件实发
