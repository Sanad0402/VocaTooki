"""The VocaTooki test framework, one module per domain.

    backend   which API host every call goes to (set_backend, get_class_map, ...)

Everything is still reachable through ``Utilities.utilsdemo`` — the front door
the tests, the runner and the solvers use — so nothing that imports it changes.
"""
