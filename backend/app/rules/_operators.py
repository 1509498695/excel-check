"""向后兼容 shim：转发到 :mod:`backend.app.rules.domain.operators`。

仅为渐进迁移而保留一个发布周期；新代码请直接使用新路径。
"""

from backend.app.rules.domain.operators import *  # noqa: F401, F403
