# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""
Tracing package entry point.

Provides end-to-end execution tracing: ORM model definitions, the
TraceStore persistence layer, and the TraceRecorder context manager
used by pipeline stages to record inputs / outputs / timings, etc.
"""
