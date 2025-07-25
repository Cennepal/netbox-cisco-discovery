"""
Configurations management
"""

import os
import logging
from dotenv import load_dotenv


class Config:
    """Das ganze Konfig und Umgebungsvariablen."""
    
    def __init__(self):
        """Initialisierung von alles."""
        self._load_environment()
        self._validate_required_vars()
        
    def _load_environment(self):
        """Umgebung von .env oder das System laden."""
        if os.path.exists(".env"):
            load_dotenv(".env")
        elif os.getenv("NETBOX_URL") is None:
            raise ValueError("Environment variables not found. Please create .env file or set system variables.")
    
    def _validate_required_vars(self):
        """Validieren dass die Variablen vorhanden sind, wenn nicht dann Fehler schmeißen."""
        required_vars = ["NETBOX_URL", "NETBOX_TOKEN", "SWITCH_USER", "SWITCH_PASS"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    @property
    def netbox_url(self):
        return os.getenv("NETBOX_URL")
    
    @property
    def netbox_token(self):
        return os.getenv("NETBOX_TOKEN")
    
    @property
    def switch_user(self):
        return os.getenv("SWITCH_USER")
    
    @property
    def switch_pass(self):
        return os.getenv("SWITCH_PASS")
    
    @property
    def log_level(self):
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        return getattr(logging, level, logging.INFO)
    
    @property
    def default_site_id(self):
        """Die Standard 'site' das alles Switche ohne eine zugewiesene Site bekommen."""
        return int(os.getenv("DEFAULT_SITE_ID", "5"))
    
    @property
    def cisco_manufacturer_id(self):
        """Das ID vom Herstellerobjekt welches Cisco in Netbox für dich ist."""
        return int(os.getenv("CISCO_MANUFACTURER_ID", "1"))
    
    @property
    def generic_manufacturer_id(self):
        """Das ID für ein generisches Hersteller die die Module bekommen werden."""
        return int(os.getenv("GENERIC_MANUFACTURER_ID", "2"))
       
    @property
    def nexus_vtp(self):
        """Wenn VTP auf Nexus aus ist, VLAN's wegen möglicher missmatch nicht ziehen"""
        return bool(os.getenv("NX_VTP", False))