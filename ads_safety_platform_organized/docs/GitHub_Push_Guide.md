# GitHub 推送指南

## 当前状态

Git 仓库已初始化并提交了代码，但由于网络原因无法自动推送。

## 手动推送到 GitHub 的步骤

### 1. 在 GitHub 上创建新仓库

访问 https://github.com/new 创建仓库：
- Repository name: `ads_safety_platform`
- Description: 自动驾驶安全评测平台，基于 CARLA 0.9.16 + 知识图谱架构
- 选择 **Public** 或 **Private**
- **不要**勾选 "Add a README file"（我们已有）
- **不要**勾选 "Add .gitignore"（我们已有）

### 2. 添加远程仓库

```bash
cd /home/aisecurity/01_ZHB/ads_safety_platform

# 方式一：HTTPS（推荐，需要 GitHub token 或密码）
git remote add origin https://github.com/YOUR_USERNAME/ads_safety_platform.git

# 方式二：SSH（需要配置 SSH key）
git remote add origin git@github.com:YOUR_USERNAME/ads_safety_platform.git
```

### 3. 推送代码

```bash
# 首次推送
git push -u origin main

# 后续推送
git push
```

## 备份方案（本地）

如果无法访问 GitHub，可以创建本地备份：

```bash
# 创建 tar.gz 备份
cd /home/aisecurity/01_ZHB
tar -czf ads_safety_platform_backup_$(date +%Y%m%d).tar.gz \
    ads_safety_platform/.git \
    ads_safety_platform/ \
    --exclude='ads_safety_platform/__pycache__' \
    --exclude='ads_safety_platform/scene_evidence' \
    --exclude='ads_safety_platform/safety_logs'

# 恢复备份
tar -xzf ads_safety_platform_backup_YYYYMMDD.tar.gz
cd ads_safety_platform
git checkout main
```

## Git 使用技巧

### 常用命令

```bash
# 查看提交历史
git log --oneline

# 查看详细改动
git show HEAD

# 创建新分支
git checkout -b feature/xxx

# 合并分支
git checkout main
git merge feature/xxx

# 撤销最后一次提交（保留改动）
git reset HEAD~1

# 撤销最后一次提交（丢弃改动）
git reset HEAD~1 --hard

# 查看差异
git diff
```

### 版本回退

```bash
# 回退到指定 commit
git reset --hard <commit_hash>

# 强制推送到远程（危险！）
git push -f origin main
```

## 当前提交历史

```
45ac0da docs: add README.md with project overview
e5807b7 feat: add ads_safety_platform core modules
7ff225b chore: initialize git repository with .gitignore
```
