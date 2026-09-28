# SignCoach 手机端配置

本项目使用 Capacitor 将 `web-app` 打包为手机 App。网页代码在 `web-app`，评分功能仍由单独运行的 Python 服务提供。

## 已完成

- 安装 `@capacitor/core`、`@capacitor/cli` 和 `@capacitor/ios`
- 创建 `capacitor.config.json`
- 将 `webDir` 设为 `build`，与 `npm run build` 的输出目录一致
- 创建 `ios/` iOS 工程

App ID 是 `signcoach.eduspeck.com`。团队后续应保持这个 ID 一致。

## 队友克隆仓库后

进入 `web-app` 目录，运行：

    npm ci
    npm run build
    npx cap sync ios

`ios/` 工程已经在仓库中，不需要再次运行 `npx cap init` 或 `npx cap add ios`。每次修改网页代码后，重新运行 `npm run build` 和 `npx cap sync ios`，才能将最新网页文件复制进 iOS 工程。

## iPhone 安装与测试

Windows 和 GitHub Codespaces 可以准备网页代码及 iOS 工程，但不能直接构建并安装 iOS App。后续需要在 Mac 上使用 Xcode，或使用云端 iOS 构建服务。

目前尚未完成安装版的功能迁移：前端仍使用相对地址 `/api/...` 请求 Python 服务。安装版需要配置 iPhone 可访问的 HTTPS 服务地址，并验证相机权限、连续取帧、评分和历史记录。生成 iOS 工程不代表这些功能已经在安装版中通过测试。
