"""规则 handler 包。

导入本包即触发各 handler 模块加载，进而完成 ``@register_rule`` 副作用，
把 5 个 rule_type 注册到 :data:`backend.app.rules.engine_core.RULE_REGISTRY`。
"""

from backend.app.rules.handlers import basics, cross, fixed  # noqa: F401
