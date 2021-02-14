# Meraki RMA Wrapper

This repo contains an early prototype to simplify replacing devices on the Meraki Dashboard.


## Insallation :
pip install meraki-rma / poetry add meraki-rma


## Usage :

from meraki_rma import MerakiRma

rma = MerakiRma("**organization_id**", "**network_name**", "**source_serial**", "**target_serial**")
rma.organization.X
rma.network.X
rma.switch.X
