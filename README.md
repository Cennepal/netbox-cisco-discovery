# What now?
It's documented in german so either you know the language or you figure it out on your own. Basically implements following stuffs:
- VLAN scanning and updates to netbox
- Automatic device testbed creation with device creator script (Check version notes)
- Neighbouring device recognition and creation via cdp
- Device type, role and platform auto creation
- Automatic interface recognition and creation
- Automatic cable creation, again via cdp
- Inventory parsing and updates
- SFP Module Parsing and updates
- Stack recognition and support
- Supports IOS, IOS-XE and maybe NX-OS in the future
- Supports updating changed cable terminations

# Why do I need this?
Again, I'm not selling crack. So how should I know? But do be aware that this only works on IOS devices and that I hardcoded it to use /24 subnets because at some point I couldn't be bothered to implement how to get the subnet of an IP. (I tried with ipaddress, but it returned the wrong cidr)

# Netbox 4.x.x?
I can confirm it works on 4.3.2.

# Hey, isn't this a worse version of NB Diode?
Yes, but this was made before Diode came out. Plus, cloud-subscriptions make my skin crawl.

# Docker?
Have fun!

# Nom Nom, give me dependencies!
Fine:
- pyats[full]
- pynetbox
- urllib3
- dotenv

Before you go downloading the `dotenv` package and spend hours yapping about how wheel doesn't work, use `pip install python-dotenv`.
