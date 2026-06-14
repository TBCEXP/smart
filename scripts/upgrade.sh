# 一键从 GitHub 拉取最新代码并重建容器（程序更新，数据不动）
set -euo pipefail

OPT_DIR="${OPT_DIR:-/opt/smart-crm}"
DATA_DIR="${DATA_DIR:-/var/lib/smart-crm}"
BACKUP="$DATA_DIR/backups/pre-upgrade-$(date +%F-%H%M).tar.gz"
BRANCH="${DEPLOY_BRANCH:-main}"

echo "==> SMART CRM 升级开始 ($(date -Iseconds))"
echo "程序目录: $OPT_DIR"
echo "数据目录: $DATA_DIR (不覆盖)"
echo "分支: $BRANCH"

# 1. 备份数据
echo "==> [1/5] 备份数据目录"
mkdir -p "$DATA_DIR/backups"
tar czf "$BACKUP" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" 2>/dev/null || {
  echo "警告: 备份失败，继续升级（建议检查磁盘空间）"
}
echo "备份: $BACKUP"

cd "$OPT_DIR"

# 2. 拉取最新代码
echo "==> [2/5] git pull origin $BRANCH"
if [ -d .git ]; then
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
  GIT_SHA=$(git rev-parse --short HEAD)
  echo "当前版本: $GIT_SHA"
else
  echo "警告: 非 git 仓库，跳过 pull"
  GIT_SHA="unknown"
fi

# 3. 重建镜像
echo "==> [3/5] docker compose build smart-crm"
export VERSION="${VERSION:-$GIT_SHA}"
docker compose build smart-crm

# 4. 滚动重启（仅 smart-crm 服务，postgres/nginx 不动）
echo "==> [4/5] docker compose up -d smart-crm"
docker compose up -d smart-crm

# 5. 健康检查
echo "==> [5/5] 健康检查"
sleep 5
if curl -sf http://127.0.0.1:8000/api/health; then
  echo ""
  echo "✓ 升级成功 — 版本 $VERSION"
  echo "==> 快速验收"
  if bash scripts/phase15_verify.sh http://127.0.0.1:8000 --quick; then
    echo "✓ phase15_verify --quick 通过"
  else
    echo "⚠ phase15_verify 有未达标项（Mock 模式可忽略）"
  fi
  if bash scripts/phase1_verify.sh http://127.0.0.1:8000; then
    echo "✓ phase1_verify 通过"
  else
    echo "⚠ phase1_verify 有失败项"
  fi
  if bash scripts/phase2_verify.sh http://127.0.0.1:8000; then
    echo "✓ phase2_verify 通过"
  else
    echo "⚠ phase2_verify 有失败项"
  fi
  if bash scripts/phase3_verify.sh http://127.0.0.1:8000; then
    echo "✓ phase3_verify 通过"
  else
    echo "⚠ phase3_verify 有失败项"
  fi
  if bash scripts/phase4_verify.sh http://127.0.0.1:8000; then
    echo "✓ phase4_verify 通过"
  else
    echo "⚠ phase4_verify 有失败项"
  fi
  if bash scripts/phase5_verify.sh http://127.0.0.1:8000; then
    echo "✓ phase5_verify 通过"
  else
    echo "⚠ phase5_verify 有失败项"
  fi
else
  echo "✗ 健康检查失败，请执行: docker compose logs smart-crm --tail 50"
  exit 1
fi
