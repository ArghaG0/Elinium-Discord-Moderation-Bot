"""Async PostgreSQL helpers; callers own the pool and Discord interactions.

Helpers propagate database failures rather than treating them as empty data.
Legacy JSON consumers remain unchanged until their migration phases.
"""
