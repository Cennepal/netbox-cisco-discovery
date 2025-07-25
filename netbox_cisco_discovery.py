#!/usr/bin/env python3
"""
Netbox Cisco Discovery
"""

import logging
import os
from genie.testbed import load
import pynetbox
import urllib3
from dotenv import load_dotenv

from netbox_managers import NetboxManager
from device_discovery import CiscoDeviceDiscovery
from testbed_builder import TestbedBuilder
from config import Config


class NetboxCiscoDiscovery:
    """Veranwortliche Klasse für alle unsere Sachen"""
    
    def __init__(self):
        """Manager und Tools initialisieren."""
        self.config = Config()
        self.setup_logging()
        self.netbox_manager = NetboxManager(self.config)
        self.testbed_builder = TestbedBuilder(self.config, self.netbox_manager)
        self.device_discovery = CiscoDeviceDiscovery(self.netbox_manager, self.config)
        
    def setup_logging(self):
        """Logging anschalten."""
        logging.basicConfig(
            level=self.config.log_level,
            format="[{asctime}]-[{levelname}]: {message}",
            style="{",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Keine URLLib-Warnungen wegen http api calls
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        logging.debug("Environment variables loaded:")
        logging.debug(f"NETBOX_URL: {self.config.netbox_url}")
        logging.debug(f"NETBOX_TOKEN: {self.config.netbox_token}")
        logging.debug(f"SWITCH_USER: {self.config.switch_user}")
        logging.debug(f"SWITCH_PASS: {self.config.switch_pass}")
    
    def run_discovery(self):
        """Discovery Methode."""
        logging.info("Starting Netbox Cisco Discovery")
        
        # Testbed bauen
        testbed_config = self.testbed_builder.build_testbed()
        testbed = load(testbed_config)
        
        logging.info(f"Testbed loaded with {len(testbed.devices)} devices")
        
        # Geräte durchgehen
        for device_name, device in testbed.devices.items():
            if self._is_cisco_device(device):
                try:
                    logging.info(f"Processing device: {device_name}")
                    self.device_discovery.discover_device(testbed, device_name)
                except Exception as e:
                    logging.error(f"Error processing {device_name}: {str(e)}")
                    continue
            else:
                logging.info(f"Skipping non-Cisco device: {device_name}")
        
        logging.info("Discovery process completed")
    
    def _is_cisco_device(self, device):
        """Schauen ob wir OS unterstützen."""
        return any(os_type in device.os for os_type in ['ios', 'iosxe', 'nxos'])


def main():
    """Hauptmethode."""
    try:
        discovery = NetboxCiscoDiscovery()
        discovery.run_discovery()
    except Exception as e:
        logging.error(f"Discovery failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
