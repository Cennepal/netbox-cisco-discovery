"""
Testbed builder
"""

import logging


class TestbedBuilder:
    """Baut ein Genie-Testbed von Daten aus Netbox."""
    
    def __init__(self, config, netbox_manager):
        """Builder initialisieren."""
        self.config = config
        self.netbox_manager = netbox_manager
        
    def build_testbed(self):
        """Allgemeine Testbed bauen."""
        logging.info("Building testbed configuration")
        
        # Basisstruktur für alle Switche, also Login und Testbedname
        testbed_config = {
            "testbed": {
                "name": "NetboxTestbed",
                "credentials": {
                    "default": {
                        "username": self.config.switch_user,
                        "password": self.config.switch_pass
                    }
                }
            },
            "devices": {}
        }
        
        # Scanbare Switche aus Netbox ziehen
        switches = self.netbox_manager.device_manager.get_switches()
        logging.info(f"Found {len(switches)} switches in Netbox")
        
        # Die Switche zur Gesamtstruktur hinzufügen
        for switch in switches:
            device_config = self._create_device_config(switch)
            testbed_config["devices"][switch.name] = device_config
            
        return testbed_config
    
    def _create_device_config(self, switch):
        """Generiert die Konfig für einen Switch."""
        # Primäre Addresse holen
        primary_ip = self._get_primary_ip(switch)
        
        # OS feststellen
        os_type = self._get_os_type(switch)
        
        device_config = {
            "type": "switch",
            "os": os_type,
            "connections": {
                "cli": {
                    "protocol": "ssh",
                    "ip": primary_ip
                }
            }
        }
        
        logging.debug(f"Created device config for {switch.name}.")
        return device_config
        
    def _get_primary_ip(self, switch):
        """Die IP-Addresse des Switches ziehen, sonst generic."""
        primary_ip = switch.primary_ip4.address.split('/')[0] if switch.primary_ip4 else '0.0.0.0'
        
        return primary_ip
        
    def _get_os_type(self, switch):
        """Das OS abrufen."""
        os = switch.custom_fields['OS'].lower()
        os = os.replace("-", "")
        
        return os