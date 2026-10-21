---
icon: lucide/book-open
---

# 指南

指南按渲染任务组织，而不是按 Python 模块边界组织。

<div class="grid cards" markdown>

-   :material-layers-triple:{ .lg .middle } **渲染模型**

    输入、节点树、编译、渲染选项、视口尺寸和参数约定。

    [:octicons-arrow-right-24: 打开指南](rendering.md)

-   :material-language-html5:{ .lg .middle } **HTML 与 CSS**

    解析、文档样式表、严格与容错的 CSS、解析器选项和资源发现。

    [:octicons-arrow-right-24: 打开指南](html.md)

-   :material-image-multiple:{ .lg .middle } **输出格式**

    位图编码器、原始 RGBA、设备像素比、SVG 和布局测量。

    [:octicons-arrow-right-24: 打开指南](output.md)

-   :material-folder-image:{ .lg .middle } **字体与图片**

    资源归属、字体子集、语言元数据和缓存预算。

    [:octicons-arrow-right-24: 打开指南](resources.md)

-   :simple-jinja:{ .lg .middle } **Jinja 模板**

    模板目录、渲染上下文、自定义过滤器和转义边界。

    [:octicons-arrow-right-24: 打开指南](templates.md)

-   :material-animation-play:{ .lg .middle } **动画**

    时间轴采样、场景序列、原始帧和动画编码器。

    [:octicons-arrow-right-24: 打开指南](animation.md)

</div>

!!! info "指南解释取舍，参考页定义签名"

    完整的参数签名由源码生成，见 [API 参考](../reference/index.md)。指南侧重于如何
    选择 API 以及如何保持其不变量，使参数列表只有一个权威来源。

每篇指南都链接了 [`examples/`](https://github.com/BalconyJH/takumi-py/tree/main/examples)
目录中的可运行脚本，测试套件会执行这些脚本。
