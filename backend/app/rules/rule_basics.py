"""向后兼容 shim：转发到 :mod:`backend.app.rules.handlers.basics`。

`import *` 会触发新模块加载，进而完成 ``@register_rule`` 副作用，
保证旧路径调用方仍能拿到相同的 handler 注册行为。仅保留一个发布周期。
"""

from backend.app.rules.handlers.basics import *  # noqa: F401, F403
