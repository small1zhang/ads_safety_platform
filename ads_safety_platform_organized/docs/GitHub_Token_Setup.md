# GitHub Token 配置指南

## 问题说明

HTTPS 推送需要 GitHub Personal Access Token (PAT) 认证。

## 配置步骤

### 1. 生成 GitHub Token

1. 访问 https://github.com/settings/tokens
2. 点击 **"Generate new token (classic)"**
3. 填写信息：
   - Note: `ads_safety_platform`
   - Expiration: 选择 `90 days` 或自定义
   - Scopes: 勾选 `repo` (Full control of private repositories)
4. 点击 **"Generate token"**
5. **复制并保存 token**（只显示一次！）

### 2. 配置 Git 使用 Token

```bash
# 方式一：临时配置（推荐）
git config --global credential.helper store

# 推送时输入用户名和 token
git push -u origin main
# Username: 你的 GitHub 用户名
# Password: 粘贴你的 token
```

### 3. 或者直接在 URL 中使用 Token

```bash
# 替换 YOUR_TOKEN 为你的实际 token
git remote set-url origin https://YOUR_TOKEN@github.com/small1zhang/ads_safety_platform.git

# 然后推送
git push -u origin main
```

### 4. 验证配置

```bash
# 查看远程仓库配置
git remote -v

# 应该显示（token 已隐藏）：
# origin https://github.com/small1zhang/ads_safety_platform.git (fetch)
# origin https://github.com/small1zhang/ads_safety_platform.git (push)
```

## 推送代码

```bash
cd /home/aisecurity/01_ZHB/ads_safety_platform

# 首次推送
git push -u origin main

# 验证推送成功
git log --oneline --graph
```

## 常见问题

### Q1: 如何安全地保存 token？

```bash
# 使用 credential helper（推荐）
git config --global credential.helper store

# Token 会保存在 ~/.git-credentials
# 注意：此文件权限应为 600
chmod 600 ~/.git-credentials
```

### Q2: 如何撤销 token？

1. 访问 https://github.com/settings/tokens
2. 找到对应的 token
3. 点击 **"Delete"**

### Q3: 推送失败怎么办？

```bash
# 检查远程仓库地址
git remote -v

# 测试连接
git ls-remote origin

# 如果是认证失败，重新设置 token
git remote set-url origin https://YOUR_TOKEN@github.com/small1zhang/ads_safety_platform.git
```

## 安全提示

⚠️ **不要将 Token 提交到 Git 仓库！**

```bash
# 如果不小心提交了 token，立即撤销
git reset HEAD~1
git commit -m "chore: remove accidentally committed token"

# 然后在 GitHub 上撤销该 token，生成新 token
```

## 推送后的验证

推送成功后，访问 https://github.com/small1zhang/ads_safety_platform 验证：
- ✅ README.md 显示正常
- ✅ 代码文件结构完整
- ✅ 提交历史显示正确
