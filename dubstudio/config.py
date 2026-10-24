"""Configuration management for dubstudio using Pydantic Settings and TOML."""
from pathlib import Path
from typing import Any, Dict, Optional
import os
import tomllib
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dubstudio.paths import get_models_dir, get_workspace_dir, get_out_dir, get_app_dir


def get_api_port() -> int:
    """Return the active HTTP port for DubStudio FastAPI backend."""
    return int(os.environ.get("DUBSTUDIO_API_PORT", "8765"))


def get_api_base_url() -> str:
    """Return the base URL of the local FastAPI backend (e.g. http://127.0.0.1:8765)."""
    return f"http://127.0.0.1:{get_api_port()}"


class GeneralConfig(BaseModel):
    app_name: str = "dubstudio"
    models_dir: Path = Field(default_factory=get_models_dir)
    workspace_dir: Path = Field(default_factory=get_workspace_dir)
    out_dir: Path = Field(default_factory=get_out_dir)


class AudioConfig(BaseModel):
    sample_rate: int = 44100
    channels: int = 2


class SeparationConfig(BaseModel):
    model_name: str = "Kim_Vocal_2.onnx"
    force_cpu: bool = False


class TranslationConfig(BaseModel):
    provider: str = "groq"
    model: str = "qwen/qwen3.8-27b"
    groq_api_key: Optional[str] = None
    fallback_models: list[str] = []
    auto_fallback: bool = False
    rate_limit_rpm: int = 30
    style: str = "Tự nhiên, đời thường"
    backup_gemini_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "google/gemini-2.0-flash-exp:free"
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"
    cdp_port: int = 9222


class TTSConfig(BaseModel):
    default_male_voice: str = "Minh Đức"
    default_female_voice: str = "Quỳnh Anh"



class ASRConfig(BaseModel):
    model_size: str = "sensevoice-small"
    vad_min_silence_duration_ms: int = 500
    split_silence_gap_s: float = 0.35
    max_segment_duration_s: float = 8.0


class FitConfig(BaseModel):
    max_speedup: float = 1.1
    min_slowdown: float = 0.9
    neutral_zone_low: float = 0.95
    neutral_zone_high: float = 1.05


class RenderConfig(BaseModel):
    encoder: str = "h264_nvenc"
    fallback_encoder: str = "libx264"
    crf: int = 18


class ComponentsConfig(BaseModel):
    components_feed_url: Optional[str] = None
    force_min_version: Optional[str] = None


class SystemConfig(BaseModel):
    min_nvidia_driver_version: str = "528.33"
    use_cpu_mode: bool = False


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    general: GeneralConfig = Field(default_factory=GeneralConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    separation: SeparationConfig = Field(default_factory=SeparationConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)
    translation: TranslationConfig = Field(default_factory=TranslationConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    fit: FitConfig = Field(default_factory=FitConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    components: ComponentsConfig = Field(default_factory=ComponentsConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)

    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    backup_gemini_api_key: Optional[str] = Field(default=None, alias="BACKUP_GEMINI_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")

    @classmethod
    def load(cls, config_path: Optional[Path] = None, overrides: Optional[Dict[str, Any]] = None) -> "AppConfig":
        """Load configuration from TOML file, environment, and optional runtime overrides."""
        if config_path:
            cfg_path = config_path
        else:
            candidates = [
                get_app_dir() / "config" / "default.toml",
                get_app_dir() / "_internal" / "config" / "default.toml",
            ]
            cfg_path = next((c for c in candidates if c.exists()), candidates[0])

        data: Dict[str, Any] = {}
        if cfg_path.exists():
            with open(cfg_path, "rb") as f:
                data = tomllib.load(f)

        # Resolve path strings into absolute paths using centralized helpers
        if "general" in data and isinstance(data["general"], dict):
            g = data["general"]
            ws_val = g.get("workspace_dir")
            if ws_val == "workspace" or not ws_val:
                g["workspace_dir"] = get_workspace_dir()
            elif not Path(ws_val).is_absolute():
                g["workspace_dir"] = (get_app_dir() / ws_val).resolve()

            out_val = g.get("out_dir")
            if out_val == "out" or not out_val:
                g["out_dir"] = get_out_dir()
            elif not Path(out_val).is_absolute():
                g["out_dir"] = (get_app_dir() / out_val).resolve()

            mod_val = g.get("models_dir")
            if mod_val == "models" or not mod_val:
                g["models_dir"] = get_models_dir()
            elif not Path(mod_val).is_absolute():
                g["models_dir"] = (get_app_dir() / mod_val).resolve()

        # Apply environment and .env overrides for user preferences
        import os
        from dotenv import load_dotenv
        from dubstudio.paths import get_env_file
        load_dotenv(dotenv_path=get_env_file(), override=False)

        asr_model = os.getenv("WHISPER_MODEL") or os.getenv("ASR_MODEL")
        if asr_model:
            if "asr" not in data:
                data["asr"] = {}
            data["asr"]["model_size"] = asr_model

        male_voice = os.getenv("DEFAULT_MALE_VOICE")
        if male_voice:
            if "tts" not in data:
                data["tts"] = {}
            data["tts"]["default_male_voice"] = male_voice

        female_voice = os.getenv("DEFAULT_FEMALE_VOICE")
        if female_voice:
            if "tts" not in data:
                data["tts"] = {}
            data["tts"]["default_female_voice"] = female_voice

        trans_provider = os.getenv("TRANSLATION_PROVIDER")
        if trans_provider:
            if "translation" not in data:
                data["translation"] = {}
            data["translation"]["provider"] = trans_provider

        trans_model = os.getenv("TRANSLATION_MODEL")
        if trans_model in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"):
            # Migrate to Groq Qwen by default when user switched to Groq
            if os.getenv("GROQ_API_KEY"):
                trans_model = "qwen/qwen3.8-27b"
        if trans_model:
            if "translation" not in data:
                data["translation"] = {}
            data["translation"]["model"] = trans_model

        auto_fb = os.getenv("AUTO_FALLBACK_MODELS")
        if auto_fb is not None:
            if "translation" not in data:
                data["translation"] = {}
            data["translation"]["auto_fallback"] = auto_fb.strip().lower() not in ("0", "false", "no")

        backup_key = os.getenv("BACKUP_GEMINI_API_KEY")
        if backup_key:
            if "translation" not in data:
                data["translation"] = {}
            data["translation"]["backup_gemini_api_key"] = backup_key

        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            if "translation" not in data:
                data["translation"] = {}
            data["translation"]["openrouter_api_key"] = openrouter_key

        if overrides:
            for k, v in overrides.items():
                if isinstance(v, dict) and k in data and isinstance(data[k], dict):
                    data[k].update(v)
                else:
                    data[k] = v

        return cls(**data)
