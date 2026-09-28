import os


class Config:
    """アプリケーション設定。環境変数で上書き可能（本番では必ず SECRET_KEY を設定する）。"""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///clublink.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
