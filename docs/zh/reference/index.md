---
icon: lucide/braces
---

# 参考

参考页定义精确的支持范围和 API 约定。需要面向决策的解释和完整示例时，请从
[指南](../guides/index.md) 开始。

<div class="grid cards" markdown>

-   :material-check-decagram:{ .lg .middle } **支持矩阵**

    运行时版本、已发布的 wheel、格式、资源归属和排除项。

    [:octicons-arrow-right-24: 支持矩阵](support.md)

-   :material-alert-circle-outline:{ .lg .middle } **异常**

    公共异常层级，以及调用方应当捕获的最窄边界。

    [:octicons-arrow-right-24: 异常](exceptions.md)

-   :material-code-braces:{ .lg .middle } **Renderer API**

    编译、测量、静态输出、SVG 和动画的生成签名。

    [:octicons-arrow-right-24: Renderer](api/renderer.md)

-   :material-shape-outline:{ .lg .middle } **辅助类型**

    渲染选项、资源、节点、结果和模板入口。

    [:octicons-arrow-right-24: 选项](api/options.md) ·
    [:octicons-arrow-right-24: 类型](api/types.md) ·
    [:octicons-arrow-right-24: HTML](api/html.md) ·
    [:octicons-arrow-right-24: 模板](api/templates.md)

</div>

!!! note "从公共包导入"

    `_core` 是原生扩展的实现模块。应用代码应当从 `takumi_py` 导入，不能把 `_core`
    当作兼容性边界。

API 参考页中生成的签名和文档字符串为英文，本站只翻译它们周围的说明文字。
