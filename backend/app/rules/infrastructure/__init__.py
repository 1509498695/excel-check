"""规则引擎 infrastructure 层：依赖 tag 提取与上下文查询等基础设施工具。

本包内部模块只读取 :mod:`backend.app.api.schemas` 中的请求模型，与 handler / domain
都没有运行期依赖，可以被 ``engine_core`` 安全地在顶层 import 而不引入循环依赖。
"""
