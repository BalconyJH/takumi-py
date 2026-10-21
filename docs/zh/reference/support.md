# 支持矩阵

## 运行时 { #runtime }

| 组件 | 支持范围 |
| --- | --- |
| Python | 3.10+ |
| ABI | CPython abi3，最低 cp310 |
| Linux wheel | x86_64 与 aarch64，manylinux2014 |
| macOS wheel | Apple Silicon，macOS 11+ |
| Windows wheel | x64 |

其他平台可以从源码分发包构建，但不在已发布的 wheel 矩阵之内。[^sdist]

## 输入与输出 { #inputs-and-outputs }

| 类别 | 支持范围 |
| --- | --- |
| 输入 | 节点树、原始 RGBA 像素、HTML、Jinja 模板、已编译节点 |
| 位图 | PNG、JPEG、WebP、ICO、原始 RGBA |
| 矢量 | SVG |
| 动画 | WebP 与 APNG 最高 90 fps，GIF 最高 50 fps |
| 布局 | 对节点、HTML 和已编译节点进行测量 |

## 资源模型 { #resource-model }

- 扩展中编译进了一个拉丁文字的 Geist 最后回退字体。
- 其他所有字体和图片字节均由调用方提供。字体按渲染器注册，可以拆分为 `unicode_range`
  子集，也可以再次释放。
- `resource_urls()` 在不访问网络的情况下发现 URL。
- 图片接受单次渲染的缓存提示；绑定不提供 HTTP 客户端。
- 每个渲染器都有资源缓存预算；字形缓存使用单独的进程级预算，须在首次使用前配置。

## 明确排除 { #explicit-exclusions }

- Playwright 或浏览器回退
- 远程资源抓取
- `AbortSignal` 或异步取消协议
- data URL 便捷 API
- Node.js 旁路进程
- 对 Takumi 内部布局、缓存或字形实现类型的直接映射

!!! info "在应用边界组合基础设施"

    这些排除项让绑定的职责与 Takumi 核心保持一致。远程抓取、持久缓存或任务取消应当在
    应用中组合实现，而不是深入渲染器内部。

[^sdist]: 源码构建需要 Rust 1.91 或更高版本、Python 开发环境以及目标平台的原生依赖。

*[ABI]: 应用二进制接口（Application Binary Interface）
