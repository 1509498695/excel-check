"""规则引擎 domain 层：值规范化、统一异常结果、operator 判定。

本包内部模块均不依赖 ``backend.app.rules.handlers`` 与 ``backend.app.rules.engine_core``
的运行期符号（仅在类型注解中通过 ``TYPE_CHECKING`` 守护），可以被任意上层安全引用，
避免与 handler 注册流程产生循环依赖。
"""
