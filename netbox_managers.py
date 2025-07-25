"""
Netbox API management
"""

import logging
import pynetbox
import random
from ipaddress import ip_network


class NetboxManager:
    
    def __init__(self, config):
        """Verbindung herstellen und Konfig initialisieren."""
        self.config = config
        self.nb = self._connect_to_netbox()
        
        # Alle manager hochfahren
        self.device_manager = DeviceManager(self.nb, config)
        self.interface_manager = InterfaceManager(self.nb, config)
        self.vlan_manager = VLANManager(self.nb, config)
        self.ip_manager = IPManager(self.nb, config)
        self.cable_manager = CableManager(self.nb, config)
        self.inventory_manager = InventoryManager(self.nb, config)
        
    def _connect_to_netbox(self):
        logging.info("Connecting to Netbox")
        nb = pynetbox.api(url=self.config.netbox_url, token=self.config.netbox_token)
        nb.http_session.verify = False
        return nb


class DeviceManager:
    
    def __init__(self, nb, config):
        self.nb = nb
        self.config = config
        self.used_colors = []
        
    def get_switches(self):
        """Alle Geräte mit 'Switch'-Rolle aus Netbox ziehen."""
        logging.info("Getting devices with role 'switch' from Netbox")
        switch_role = self.nb.dcim.device_roles.get(slug='switch')
        if not switch_role:
            raise ValueError("Switch role not found in Netbox")
        return self.nb.dcim.devices.filter(role_id=switch_role.id)
    
    def create_or_update_device(self, device_data):
        device = self.nb.dcim.devices.get(name=device_data['name'])
        
        if device:
            logging.info(f"Device {device_data['name']} exists - updating information")
            self._update_device(device, device_data)
        else:
            logging.info(f"Creating device {device_data['name']}")
            device = self._create_device(device_data)
            
        return device
    
    def _create_device(self, device_data):
        try:
            logging.debug(f"Creating device with data: {device_data}")
            try:
                device = self.nb.dcim.devices.create(
                    name=device_data['name'],
                    device_type=device_data['device_type_id'],
                    platform=device_data['platform_id'],
                    serial=device_data.get('serial', ''),
                    role=device_data['role_id'],
                    status='active',
                    site=device_data['site_id'],
                    custom_fields=device_data.get('custom_fields', {}),
                    primary_ip4=device_data.get('primary_ip4'),
                    primary_ip6=device_data.get('primary_ip6')
                )
            except pynetbox.RequestError as e:
                logging.error(f"NetBox API error: {e.error}")

            if not device:
                logging.error(f"Device creation returned None for {device_data['name']}")
            return device
        except Exception as e:
            logging.exception(f"Exception while creating device {device_data['name']}: {e}")
            return none

    
    def _update_device(self, device, device_data):
        device.device_type = device_data['device_type_id']
        device.platform = device_data['platform_id']
        device.serial = device_data['serial'] if 'serial' in device_data and device_data['serial'] else device.serial
        device.site = device_data['site_id']
        device.custom_fields = device_data.get('custom_fields', {})
        device.save()
    
    def ensure_device_type(self, model, slug):
        """Sichergehen dass das Gerätetyp in Netbox existiert. Selbe mit Platform und Geräterolle."""
        device_type = self.nb.dcim.device_types.get(slug=slug)
        if not device_type:
            logging.info(f"Creating device type: {model}")
            device_type = self.nb.dcim.device_types.create(
                model=model,
                slug=slug,
                manufacturer=self.config.cisco_manufacturer_id
            )
        return device_type.id
    
    def ensure_platform(self, name, slug):
        platform = self.nb.dcim.platforms.get(slug=slug)
        if not platform:
            logging.info(f"Creating platform: {name}")
            platform = self.nb.dcim.platforms.create(name=name, slug=slug)
        return platform.id
    
    def ensure_device_role(self, name, slug):
        role = self.nb.dcim.device_roles.get(slug=slug.lower())
        if not role:
            logging.info(f"Creating device role: {name}")
            role = self.nb.dcim.device_roles.create(
                name=name,
                slug=slug.lower(),
                color=self._pick_color()
            )
        return role.id
    
    def _pick_color(self):
        """Die Farben die zufällig für neue Geräterollen benutzt werden können."""
        colors = [
            'FF6F61', 'FFB07C', 'FFD700', 'FFEF96', 'BEEB9F', 'A7D8AD',
            '77D8D8', 'AEC6CF', 'B39EB5', 'D7B9D5', 'FFC3A0', 'FFABAB',
            'FFC3A0', 'FF677D', 'FFD3B5', 'FFD3B5'
        ]
        available_colors = [color for color in colors if color not in self.used_colors]
        if not available_colors:
            self.used_colors = []
            available_colors = colors
        
        color = random.choice(available_colors).lower()
        self.used_colors.append(color)
        return color
    
    def get_site_id(self, ip_address):
        """Die Site-ID durch den Prefix des Geräts ermitteln, wenn die IP in eine ist."""
        ip_obj = self.nb.ipam.ip_addresses.get(address=ip_address)
        device = ip_obj.assigned_object.device if ip_obj and ip_obj.assigned_object else None
        
        if device is not None and device.site is not None and device.site.id is not None:
            return device.site.id
        else:
            try:
                prefix_str = str(ip_network(ip_address + "/24", strict=False).supernet().network_address) + "/24"
                logging.info(f"Checking prefix {prefix_str}")
                prefix = self.nb.ipam.prefixes.get(prefix=prefix_str)
                if prefix and prefix.scope_id:
                    logging.info(f"Site found for prefix {prefix_str}: {prefix.scope['name']}")
                    return prefix.scope_id
                else:
                    logging.info(f"No site found for prefix {prefix_str}, using default")
                    return self.config.default_site_id
            except Exception as e:
                logging.warning(f"Error determining site for {ip_address}: {e}")
                return self.config.default_site_id


class InterfaceManager:
    
    def __init__(self, nb, config):
        self.nb = nb
        self.config = config
        
    def create_or_update_interface(self, device_id, interface_data):
        interface = self.nb.dcim.interfaces.get(
            name=interface_data['name'],
            device_id=device_id
        )
        
        if interface:
            logging.info(f"Updating interface {interface_data['name']}")
            self._update_interface(interface, interface_data)
        else:
            logging.info(f"Creating interface {interface_data['name']}")
            interface = self._create_interface(device_id, interface_data)
            
        return interface
    
    def _create_interface(self, device_id, interface_data):
        return self.nb.dcim.interfaces.create(
            name=interface_data['name'],
            device=device_id,
            type=interface_data['type'],
            enabled=interface_data.get('enabled', True),
            label=interface_data.get('label', ''),
            description=interface_data.get('description', '')
        )
    
    def _update_interface(self, interface, interface_data):
        interface.type = interface_data['type']
        interface.enabled = interface_data.get('enabled', True)
        interface.label = interface_data.get('label', '')
        interface.description = interface_data.get('description', '')
        interface.save()
    
    def get_interface_type(self, interface_spec, mode="device"):
        """Dumm aber muss sein, manuelles mapping für SFP zuweisungen in Netbox."""
        if mode == "device":
            type_mapping = {
                "10/100/1000BaseTX": "1000base-tx",
                "1000BaseSX SFP": "1000base-x-sfp",
                "10/100BaseTX": "100base-tx",
                "SFP-10GBase-LR": "10gbase-x-sfpp",
                "SFP-10GBase-SR": "10gbase-x-sfpp",
                "SFP-10GBase-LRM": "10gbase-x-sfpp",
                "QSFP-40G-CR": "40gbase-x-qsfpp",
                "unknown": "other",
                "Not Present": "other",
                "--": "other"
            }
            return type_mapping.get(interface_spec, "virtual")
        
        elif mode == "cdp":
            if "TenGigabitEthernet" in interface_spec:
                return "10gbase-t"
            elif "FastEthernet" in interface_spec:
                return "100base-tx"
            elif "GigabitEthernet" in interface_spec:
                return "1000base-tx"
            else:
                return "other"
        
        return "other"


class VLANManager:
    
    def __init__(self, nb, config):
        self.nb = nb
        self.config = config
        
    def create_or_update_vlan(self, vlan_data):
        vlan = self.nb.ipam.vlans.get(vid=vlan_data['vid'])
        
        if vlan:
            if vlan.name != vlan_data['name']:
                logging.info(f"Updating VLAN {vlan_data['vid']} name to {vlan_data['name']}")
                vlan.name = vlan_data['name']
                vlan.save()
        else:
            logging.info(f"Creating VLAN {vlan_data['name']} with ID {vlan_data['vid']}")
            vlan = self.nb.ipam.vlans.create(
                name=vlan_data['name'],
                vid=vlan_data['vid']
            )
        
        return vlan


class IPManager:
    
    def __init__(self, nb, config):
        self.nb = nb
        self.config = config
        
    def create_or_get_ip(self, ip_address):
        ip = self.nb.ipam.ip_addresses.get(address=ip_address)
        
        if not ip:
            logging.info(f"Creating IP address {ip_address}")
            ip = self.nb.ipam.ip_addresses.create(
                address=ip_address,
                status='active'
            )
        
        return ip
    
    def assign_ip_to_interface(self, ip_address, interface_id, device_id, set_primary=False):
        """IP-Addresse auf interface setzen."""
        ip = self.create_or_get_ip(ip_address)
        
        if not ip.assigned_object_id:
            logging.info(f"Assigning IP {ip_address} to interface {interface_id}")
            ip.assigned_object_id = interface_id
            ip.assigned_object_type = "dcim.interface"
            ip.save()
            
            if set_primary:
                logging.info(f"Setting {ip_address} as primary IP for device {device_id}")
                device = self.nb.dcim.devices.get(id=device_id)
                device.primary_ip4 = ip.id
                device.save()
        
        return ip


class CableManager:
    
    def __init__(self, nb, config):
        self.nb = nb
        self.config = config
        
    def create_or_update_cable(self, interface_a_id, interface_b_id):
        """Die Kabel zwischen Interfaces verwalten."""

        # Checken ob die Kabel bidirektional da sind
        cable = self.nb.dcim.cables.get(
            termination_a_id=interface_a_id,
            termination_b_id=interface_b_id
        )
        
        if not cable:
            cable = self.nb.dcim.cables.get(
                termination_a_id=interface_b_id,
                termination_b_id=interface_a_id
            )
        
        if not cable:
            logging.info(f"Creating cable between interfaces {interface_a_id} and {interface_b_id}")
            cable = self.nb.dcim.cables.create(
                a_terminations=[{'object_type': 'dcim.interface', 'object_id': interface_a_id}],
                b_terminations=[{'object_type': 'dcim.interface', 'object_id': interface_b_id}],
                status='connected'
            )
        
        return cable
    
    def remove_loose_cables(self):
        """Hängende Kabel bereinigen, also löschen."""
        logging.info("Removing loose cables...")
        cables = self.nb.dcim.cables.all()
        
        for cable in cables:
            if not cable.a_terminations or not cable.b_terminations:
                logging.info(f"Removing cable {cable.id} with loose terminations")
                cable.delete()


class InventoryManager:
    
    def __init__(self, nb, config):
        self.nb = nb
        self.config = config
        
    def sync_inventory(self, device_id, device_name, inventory_data, device_os, is_stacked):
        logging.info(f"Syncing inventory for {device_name}...")
        
        # In Netbox vorhandenes Inventar ziehen
        netbox_serials = self._get_netbox_serials(device_id)
        device_serials = self._get_device_serials(inventory_data, device_os)
        
        # Alte Module die nicht mehr im Gerät sind entfernen
        self._remove_obsolete_items(netbox_serials, device_serials)
        
        # Vorhandene Module erstellen/aktualisieren
        self._sync_device_inventory(device_id, device_name, inventory_data, device_os, is_stacked)
    
    def _get_netbox_serials(self, device_id):
        serials = []
        inventory_items = self.nb.dcim.inventory_items.filter(device_id=device_id)
        for item in inventory_items:
            if item.serial:
                serials.append(item.serial)
        return serials

    
    def _get_device_serials(self, inventory_data, device_os):
        serials = []

        if device_os == 'ios':
            for slot_data in inventory_data.get('slot', {}).values():
                for rp_data in slot_data.get('rp', {}).values():
                    # Add chassis serial
                    if 'sn' in rp_data:
                        serials.append(rp_data['sn'])

                    # Add SFP module serials
                    for subslot_data in rp_data.get('subslot', {}).values():
                        for sfp_data in subslot_data.values():
                            if 'sn' in sfp_data:
                                serials.append(sfp_data['sn'])
        elif device_os == 'iosxe':
            for item_data in inventory_data.get('name', {}).values():
                if 'sn' in item_data:
                    serials.append(item_data['sn'])

                if 'subslot' in item_data:
                    for subslot_data in item_data['subslot'].values():
                        for sfp_data in subslot_data.values():
                            if 'sn' in sfp_data:
                                serials.append(sfp_data['sn'])
        elif device_os == 'nxos':
            for item_data in inventory_data.get('name', {}).values():
                if 'serial_number' in item_data:
                    serials.append(item_data['serial_number'])
        return [s for s in serials if s]

    
    def _remove_obsolete_items(self, netbox_serials, device_serials):
        serials_to_delete = set(netbox_serials) - set(device_serials)
        
        for serial in serials_to_delete:
            item = self.nb.dcim.inventory_items.get(serial=serial)
            if item:
                logging.info(f"Removing obsolete inventory item with serial {serial}")
                item.delete()
    
    def _sync_device_inventory(self, device_id, device_name, inventory_data, device_os, is_stacked):
        if device_os == 'ios':
            self._sync_ios_inventory(device_id, device_name, inventory_data, is_stacked)
        elif device_os == 'iosxe':
            self._sync_iosxe_inventory(device_id, device_name, inventory_data, is_stacked)
        elif device_os == 'nxos':
            self._sync_nxos_inventory(device_id, device_name, inventory_data, is_stacked)
    
    def _sync_ios_inventory(self, device_id, device_name, inventory_data, is_stacked):
        """Sync IOS Inventar."""
        for slot_data in inventory_data.get('slot', {}).values():
            for rp_data in slot_data.get('rp', {}).values():
                inv_name = f"{device_name}-{rp_data['name']}"
                
                # SFP-Module 
                if 'subslot' in rp_data:
                    self._handle_sfp_modules(device_id, rp_data['subslot'])
                
                # Nichtgestackte Geräte überspringen
                if not is_stacked and inv_name == f"{device_name}-1":
                    continue
                
                # Inventarobjekt erstellen/aktualisieren
                elif not self.nb.dcim.inventory_items.filter(serial=rp_data['sn']):
                    logging.info(f"Creating inventory item {inv_name}")
                    self.nb.dcim.inventory_items.create(
                        device=device_id,
                        name=inv_name,
                        manufacturer=self.config.cisco_manufacturer_id,
                        serial=rp_data['sn'],
                        part_id=rp_data['pid']
                    )
    
    def _sync_iosxe_inventory(self, device_id, device_name, inventory_data, is_stacked):
        """Sync IOS-XE Inventar."""
        for name, data in inventory_data.get('name', {}).items():
            inv_name = f"{device_name}-{name}"
            
            if 'pid' in data and "SFP" in data['pid']:
                self._create_or_update_sfp_module(device_id, name, data)

            if not is_stacked and inv_name == f"{device_name}-1":
                continue

            elif 'Te' not in inv_name and not self.nb.dcim.inventory_items.filter(serial=data['sn']):
                logging.info(f"Creating inventory item {inv_name}")
                self.nb.dcim.inventory_items.create(
                    device=device_id,
                    name=inv_name,
                    manufacturer=self.config.cisco_manufacturer_id,
                    serial=data['sn'],
                    part_id=data['pid'] if 'pid' in data else 'N/A'
                )
    
    def _sync_nxos_inventory(self, device_id, device_name, inventory_data, is_stacked):
        """Sync NX-OS Inventar."""
        for name, data in inventory_data.get('name', {}).items():
            inv_name = f"{device_name}-{name}"
            serial = data.get('serial_number')
            pid = data.get('pid')

            if not serial or serial == 'N/A':
                continue

            if not self.nb.dcim.inventory_items.filter(serial=serial):
                logging.info(f"Creating inventory item {inv_name}")
                self.nb.dcim.inventory_items.create(
                    device=device_id,
                    name=inv_name,
                    manufacturer=self.config.cisco_manufacturer_id,
                    serial=serial,
                    part_id=pid
                )

    
    def _handle_sfp_modules(self, device_id, subslot_data):
        for subslot_name, subslot_content in subslot_data.items():
            for sfp_name, sfp_data in subslot_content.items():
                self._create_or_update_sfp_module(device_id, subslot_name, sfp_data)
    
    def _create_or_update_sfp_module(self, device_id, bay_name, module_data):
        """Modulebay ertsellen/aktualisieren für SFPs."""
        module_bay = self.nb.dcim.module_bays.get(name=bay_name, device_id=device_id)
        if not module_bay:
            logging.info(f"Creating module bay {bay_name}")
            module_bay = self.nb.dcim.module_bays.create(
                name=bay_name,
                device=device_id
            )
        
        # Wenn nötig, Modultypen erstellen
        module_type = self.nb.dcim.module_types.get(model=module_data['pid'])
        if not module_type:
            logging.info(f"Creating module type {module_data['pid']}")
            module_type = self.nb.dcim.module_types.create(
                model=module_data['pid'],
                manufacturer=self.config.generic_manufacturer_id
            )

        module = self.nb.dcim.modules.get(
            module_bay_id=module_bay.id,
            device_id=device_id
        )
        
        if not module:
            logging.info(f"Creating module {module_data['pid']}")
            self.nb.dcim.modules.create(
                serial=module_data['sn'],
                module_type=module_type.id,
                device=device_id,
                module_bay=module_bay.id
            )
        else:
            logging.info(f"Updating module {module_data['pid']}")
            module.serial = module_data['sn']
            module.module_type = module_type.id
            module.save()
