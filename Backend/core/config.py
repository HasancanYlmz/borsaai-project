# -*- coding: utf-8 -*-
"""Configuration loader for BorsaAI project.
Provides a simple `load_config` function that reads a JSON file
(`config.json`) from the project root and returns a dictionary.
All modules can import this and access needed settings.
"""
import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "config.json")

def load_config():
    """Load configuration from `config.json`.

    The file is expected to exist at the project root. If it does not,
    an empty dict is returned so the code can still run with defaults.
    Railway environment variables always override config.json values.
    """
    cfg = {}
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f) or {}
        except Exception as e:
            print(f"[ERROR] Failed to read config file: {e}")

    # Railway / cloud ortam değişkenleri config.json'ı override eder
    api_keys = cfg.setdefault("api_keys", {})
    if os.environ.get("GEMINI_API_KEY"):
        api_keys["gemini"] = os.environ["GEMINI_API_KEY"]
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        api_keys["telegram_bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
        api_keys["telegram"] = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        api_keys["telegram_chat_id"] = os.environ["TELEGRAM_CHAT_ID"]

    return cfg
