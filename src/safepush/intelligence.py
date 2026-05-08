from __future__ import annotations

from safepush.config import AppConfig


def generate_llm_commit_message(
    cfg: AppConfig,
    *,
    prompt_kind: str,
    context: str,
) -> str | None:
    """
    Optional LLM message generation scaffold.

    Current behavior is intentionally conservative:
    - if message_mode is deterministic: skip
    - if llm/hybrid mode is selected: return None for now and rely on deterministic fallback
    """
    if cfg.commit.message_mode == "deterministic":
        return None
    _ = (prompt_kind, context, cfg.commit.model_provider, cfg.commit.model_name, cfg.commit.api_key_env)
    return None
