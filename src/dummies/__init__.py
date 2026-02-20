# File: src/dummies/__init__.py
"""
Dummy hardware manager modules for isolated hardware testing.

These drop-in replacements mirror the real manager interfaces but perform
no hardware I/O. They are injected via sys.modules in code.py when a
hardware feature is disabled in config.json hardware_features.
"""
