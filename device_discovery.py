"""
Device discovery Klasse
"""

import logging, re
from ipaddress import ip_network

class CiscoDeviceDiscovery:

    def __init__(self, netbox_manager, config):
        self.netbox_manager = netbox_manager
        self.config = config

    def discover_device(self, testbed, device_name):
        device = testbed.devices[device_name]
        try:
            logging.info(f"Connecting to {device.name}...")
            device.connect(
                goto_enable=False,
                log_stdout=False,
                init_exec_commands=[],
                init_config_commands=[]
            )
        except Exception as e:
            logging.error(f"Failed to connect to {device.name}: {e}")
            return

        try:
            logging.info(f"Executing commands and parsing data from {device.name}...")

            verraw = device.execute('show version')
            vlanraw = device.execute('show vlan')
            if device.os == 'nxos':
                intraw = device.execute('show interface status')
            else:
                intraw = device.execute('show interfaces status')
            cdpraw = device.execute('show cdp neighbors detail')

            if device.os in ['ios', 'nxos']:
                logging.info(f"Device {device.name} is running {device.os.upper()}, using 'show inventory'")
                invraw = device.execute('show inventory')
            elif device.os == 'iosxe':
                logging.info(f"Device {device.name} is running IOSXE, using 'show inventory OID'")
                invraw = device.execute('show inventory OID')

            try:
                swraw = device.execute('show switch')
                sw_errored = False
            except Exception as e:
                logging.info(f"Command 'show switch' not found on {device.name}, skipping stack creation")
                sw_errored = True

            verpar = device.parse('show version', output=verraw)
            vlanpar = device.parse('show vlan', output=vlanraw)
            if device.os == 'nxos':
                intpar = device.parse('show interface status', output=intraw)
            else:
                intpar = device.parse('show interfaces status', output=intraw)
            try:
                cdppar = device.parse('show cdp neighbors detail', output=cdpraw)
                cdp_errored = False
            except:
                logging.info("No neighbors found via CDP.")
                cdp_errored = True

            if device.os in ['ios', 'nxos']:
                invpar = device.parse('show inventory', output=invraw)
            else:
                invpar = device.parse('show inventory OID', output=invraw)
            if not sw_errored:
                swpar = device.parse('show switch', output=swraw)

            device_obj = self._sync_device_details(device, verpar, verraw, invpar, swpar if not sw_errored else None)
            if not device_obj:
                logging.error(f"Could not create or find device {device.name} in Netbox.")
                return

            if self.config.nexus_vtp or device.os != 'nxos':
                self._sync_vlans(vlanpar)
            
            self._sync_interfaces(device_obj, intpar)
            self._sync_inventory(device_obj, invpar, device.os, swpar if not sw_errored else None)
            if not cdp_errored:
                self._sync_cdp_neighbors(device_obj, cdppar, device)

        except Exception as e:
            logging.error(f"An error occurred during discovery for {device.name}: {e}", exc_info=True)
        finally:
            logging.info(f"Disconnecting from {device.name}")
            device.disconnect()

    def _sync_device_details(self, device, verpar, verraw, invpar, swpar):
        logging.info(f"Syncing device details for {device.name}")
        
        if device.os == 'nxos':
            hostname = re.search(r"Device name:\s*(\S+)", verraw).group(1)
            os = verpar['platform']['os']
            os_ver = verpar['platform']['software']['system_version']
            serial_num = invpar['name']['Chassis']['serial_number']
            platform = verpar['platform']['hardware']['model']
            chassis = verpar['platform']['hardware']['chassis'].split(' ')[0]
        else:
            hostname = verpar['version']['hostname']
            os = verpar['version']['os']
            os_ver = verpar['version']['version']
            serial_num = verpar['version']['chassis_sn']
            platform = verpar['version']['platform']
            chassis = verpar['version']['chassis']

        if swpar:
            slot_count = len(swpar["switch"]["stack"])
            if slot_count > 1:
                logging.info(f"Stacked Device detected, setting Serial Number to None")
                serial_num = ''
        else:
            slot_count = 1

        ip_address_str = str(device.connections['cli'].ip) + "/24"

        if not self.netbox_manager.nb.ipam.ip_addresses.filter(address=ip_address_str):
            logging.info(f"IP Address not in Netbox, creating {ip_address_str}")
            self.netbox_manager.nb.ipam.ip_addresses.create(address=ip_address_str, status='online')

        prefix_str = str(ip_network(ip_address_str, strict=False).supernet().network_address) + "/24"
        logging.info(f"Checking Prefix {prefix_str}")
        prefix_nb = self.netbox_manager.nb.ipam.prefixes.get(prefix=prefix_str)

        if self.netbox_manager.nb.dcim.devices.filter(name=hostname):
            site_id = self.netbox_manager.nb.dcim.devices.get(name=hostname).site.id
        else:
            site_id = self._get_site_id(prefix_nb, prefix_str)

        device_type_id = self.netbox_manager.device_manager.ensure_device_type(chassis, chassis)
        platform_id = self.netbox_manager.device_manager.ensure_platform(platform, platform.replace(" ", "-"))
        role_id = self.netbox_manager.device_manager.ensure_device_role("Switch", "switch")

        device_data = {
            'name': hostname,
            'device_type_id': device_type_id,
            'platform_id': platform_id,
            'serial': serial_num,
            'role_id': role_id,
            'site_id': site_id,
            'custom_fields': {'OS': os.upper(), 'Version': os_ver}
        }

        return self.netbox_manager.device_manager.create_or_update_device(device_data)


    def _sync_vlans(self, vlan_info):
        if 'vlans' not in vlan_info:
            logging.info("No VLAN information found to sync.")
            return

        logging.info("Syncing VLANs...")
        for vlan_id, vlan_data in vlan_info['vlans'].items():
            if vlan_id == "1" and vlan_data.get('name') == 'default':
                continue

            self.netbox_manager.vlan_manager.create_or_update_vlan({
                'vid': int(vlan_id),
                'name': vlan_data.get('name', f'VLAN_{vlan_id}')
            })

    def _sync_interfaces(self, device_obj, interface_info):
        if not interface_info:
            logging.info("No interface information found to sync.")
            return

        logging.info("Syncing interfaces...")
        for if_name, if_data in interface_info['interfaces'].items():
            interface_payload = {
                'name': if_name,
                'type': self.netbox_manager.interface_manager.get_interface_type(if_name, mode="cdp"),
                'enabled': True,
                'label': if_data.get('status', ''),
                'description': if_data.get('name', '')
            }
            interface_obj = self.netbox_manager.interface_manager.create_or_update_interface(
                device_obj.id, interface_payload
            )

            if 'ipv4' in if_data:
                for ip, ip_data in if_data['ipv4'].items():
                    ip_with_prefix = f"{ip}/{ip_data['prefix_length']}"
                    self.netbox_manager.ip_manager.assign_ip_to_interface(
                        ip_with_prefix, interface_obj.id, device_obj.id
                    )

    def _sync_inventory(self, device_obj, invpar, device_os, swpar):
        is_stacked = False
        if swpar:
            slot_count = len(swpar["switch"]["stack"])
            is_stacked = slot_count > 1

        self.netbox_manager.inventory_manager.sync_inventory(
            device_obj.id,
            device_obj.name,
            invpar,
            device_os,
            is_stacked
        )

    def _sync_cdp_neighbors(self, local_device_obj, cdppar, device):
        if 'index' not in cdppar:
            logging.info(f"No CDP information found for {local_device_obj.name}.")
            return

        logging.info(f"Syncing CDP neighbors for {local_device_obj.name}...")
        self.netbox_manager.cable_manager.remove_loose_cables()

        for index, device_info in cdppar['index'].items():
            cdp_device_id = device_info.get('device_id', 'N/A') #.rstrip('.domain.local')
            cdp_device_role = device_info.get('capabilities', 'N/A')
            cdp_device_type = device_info.get('platform', 'N/A').replace('cisco ', '')
            cdp_platform = re.sub('^WS-', '', cdp_device_type).split('-')[0]
            cdp_local_interface = device_info.get('local_interface', 'N/A')
            cdp_port_id = device_info.get('port_id', 'N/A')
            cdp_native_vlan = device_info.get('native_vlan', 'N/A')
            cdp_sw_ver = device_info.get('software_version', 'N/A')

            management_addresses = device_info.get('management_addresses', {})
            if not management_addresses:
                logging.warning(f"No management address found for CDP neighbor {cdp_device_id}, skipping.")
                continue

            cdp_mgmt_ip = next(iter(management_addresses))
            ip_with_prefix = f"{cdp_mgmt_ip}/24"

            if "IOS-XE" in cdp_sw_ver:
                cdp_os = "IOS-XE"
            elif "NX-OS" in cdp_sw_ver:
                cdp_os = "NX-OS"
            elif "IOS" in cdp_sw_ver:
                cdp_os = "IOS"
            else:
                cdp_os = "N/A"

            if not self.netbox_manager.nb.ipam.ip_addresses.filter(address=ip_with_prefix):
                logging.info(f"IP Address {ip_with_prefix} not in Netbox, creating it now")
                self.netbox_manager.nb.ipam.ip_addresses.create(address=ip_with_prefix, status='online')

            site_id = self.netbox_manager.device_manager.get_site_id(cdp_mgmt_ip)

            device_type_id = self.netbox_manager.device_manager.ensure_device_type(cdp_device_type, cdp_device_type.replace(' ', '_'))
            platform_id = self.netbox_manager.device_manager.ensure_platform(cdp_platform, cdp_platform.replace(' ', '-'))
            if cdp_device_role.lower().split('_')[0] == 'switch':
                role_id = self.netbox_manager.device_manager.ensure_device_role("Switch", "switch")
            else:
                role_id = self.netbox_manager.device_manager.ensure_device_role(cdp_device_role, cdp_device_role.replace(' ', '_').lower())

            device_data = {
                'name': cdp_device_id,
                'device_type_id': device_type_id,
                'platform_id': platform_id,
                'role_id': role_id,
                'site_id': site_id,
                'custom_fields': {'OS': cdp_os},
                'primary_ip4': None,
                'primary_ip6': None
            }
            self.netbox_manager.device_manager.create_or_update_device(device_data)
            neighbor_device = self.netbox_manager.nb.dcim.devices.get(name=device_data['name'])

            cdp_ipint = self.netbox_manager.nb.ipam.ip_addresses.get(address=ip_with_prefix)
            if cdp_ipint and not cdp_ipint.assigned_object_id:
                if not cdp_native_vlan or cdp_native_vlan == 'N/A':
                    interface_payload = {
                        'name': 'Vlan1',
                        'type': 'virtual',
                        'enabled': True,
                        'description': ''
                    }
                    mgmt_interface = self.netbox_manager.interface_manager.create_or_update_interface(neighbor_device.id, interface_payload)
                else:
                    vlan_interface_name = f"Vlan{cdp_native_vlan}"
                    interface_payload = {
                        'name': vlan_interface_name,
                        'type': 'virtual',
                        'enabled': True,
                        'description': ''
                    }
                    vlan_interface = self.netbox_manager.interface_manager.create_or_update_interface(neighbor_device.id, interface_payload)

            local_interface = self.netbox_manager.nb.dcim.interfaces.get(name=cdp_local_interface, device_id=local_device_obj.id)
            if not local_interface:
                interface_payload = {
                    'name': cdp_local_interface,
                    'type': self.netbox_manager.interface_manager.get_interface_type(cdp_local_interface, "cdp"),
                    'enabled': True,
                    'description': ''
                }
                local_interface = self.netbox_manager.interface_manager.create_or_update_interface(local_device_obj.id, interface_payload)

            remote_interface = self.netbox_manager.nb.dcim.interfaces.get(name=cdp_port_id, device_id=neighbor_device.id)

            if not remote_interface:
                interface_payload = {
                    'name': cdp_port_id,
                    'type': self.netbox_manager.interface_manager.get_interface_type(cdp_port_id, "cdp"),
                    'enabled': True,
                    'description': ''
                }
                remote_interface = self.netbox_manager.interface_manager.create_or_update_interface(neighbor_device.id, interface_payload)
            self.netbox_manager.ip_manager.assign_ip_to_interface(ip_with_prefix, remote_interface.id, neighbor_device.id)

            self.netbox_manager.cable_manager.create_or_update_cable(local_interface.id, remote_interface.id)