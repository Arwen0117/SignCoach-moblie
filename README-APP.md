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

cat >> README-APP.md <<'EOF'

## 手机 App 目标与当前进度

目标是发布可安装的 iOS 和 Android 应用，让用户直接在 App 内完成手语练习，而不是要求用户打开浏览器链接。目前采用 Capacitor 打包前端，Python 服务负责联网评分。

截至 2026-09-28，已完成：

- 在 `web-app` 接入 Capacitor，并生成 `web-app/ios` 工程。
- 设置 `webDir` 为 `build`；`npm run build` 已成功。
- 前端 API 地址已集中配置：未设置 `VITE_API_BASE_URL` 时，现有网页继续请求 `/api/...`。
- 已在 iOS 工程中添加相机用途说明。
- iPhone 浏览器已能访问 Python 服务的 `/api/health`；这验证的是网页访问，尚未验证安装版 App。

接下来需要：

1. 为 Python 评分服务提供安装版可访问的 HTTPS 地址，并处理访问控制与跨域请求。Codespaces 的 Private 端口地址不能直接用作安装版 API。
2. 配置 `VITE_API_BASE_URL`，重新运行 `npm run build` 和 `npx cap sync ios`。
3. 构建并在 iPhone 上测试相机、连续取帧、评分、示范视频和历史记录。iOS 构建需要 Mac/Xcode 或云端构建服务。
4. 添加 Android 工程，并在 Android 设备上完成同样的功能测试。
5. 完成签名、商店资料和审核后，才可在 App Store 与 Google Play 提供下载。
EOF
