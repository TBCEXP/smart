# Phase 3 — 大文件中转（已禁用）

> **v2.1.0+ 低配置 VPS：** 大文件中转与 Tus 本地上传已移除，避免占满 VPS 磁盘。  
> 目录 PDF 请使用 **Phase 2** 的 R2 预签名直传（文件不进 VPS）。

## 仍可用

| 功能 | 说明 |
|------|------|
| 分享链接 + 邮件通知 | 订单、目录、工厂列表（`resource_type`: order / catalog / factories） |
| Phase 2 目录 PDF | `POST /api/catalog/documents/{id}/upload-url` → R2 直传 |

## 已移除

- `GET/POST /api/files/transfers`
- Tus 断点续传 `/api/files/tus/*`
- 员工后台「大文件」Tab

## VPS 清理（若曾上传过）

```bash
rm -rf /var/lib/smart-crm/smart-crm-data/tus/
```
