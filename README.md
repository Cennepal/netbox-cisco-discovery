# What now?
It's documented in german so either you know the language or you figure it out on your own. Basically implements following stuffs:
- VLAN scanning and updates to netbox
- Automatic device testbed creation with device creator script (Check version notes)
- Neighbouring device recognition and creation via cdp
- Device type, role and platform auto creation
- OS and Version recognition (Add 'OS' and 'Version' custom fields to devices)
- Automatic interface recognition and creation
- Automatic cable creation, again via cdp
- Inventory parsing and updates
- SFP Module Parsing and updates
- Stack recognition and support
- Supports IOS, IOS-XE and as of now also NX-OS!
- Supports updating changed cable terminations

# Why do I need this?
I'm not selling crack, yet again, so how would I know? But do be aware that this only works on IOS devices and that I hardcoded it to use /24 subnets because at some point I couldn't be bothered to implement how to get the subnet of an IP. (Got too burnt out to care, plus all my nets are /24, so I gave up on it.)

# Netbox 4.x.x?
I can confirm it works on 4.3.4.

# Hey, isn't this a worse version of NB Diode?
Yes, but this was made before Diode came out. Plus, cloud-subscriptions make my skin crawl.

# Docker?
Have fun! (Other than having to make your own container for the Netbox stack, the script already supports logging and pulling preset env variables)

# Nom Nom, give me dependencies!
Fine:
- pyats[full]
- pynetbox
- urllib3
- dotenv

Before you go downloading the `dotenv` package and spend hours yapping about how wheel doesn't work, use `pip install python-dotenv`.
