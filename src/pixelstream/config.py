from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_bootstrap: str = "localhost:19092"
    default_model: str = "yolov11n"
    inference_device: str = "cpu"
    video_source: str = "data/sample.mp4"
    target_fps: int = 5
    delta_path: str = "data/detections"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = ConfigDict(env_file=".env", extra="ignore")


settings = Settings()
