import sys
from itertools import groupby
from meraki_dashboard_connect import dashboard_connection
from meraki_exception import meraki_exception
from rich.console import Console
from rich.theme import Theme

# Rich configuration
custom_theme = Theme({"good": "green", "bad": "bold red", "info": "magenta"})
console = Console(theme=custom_theme)


def all_equal(iterable):
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


class MerakiRma:
    """Class to manage device replacement on Meraki"""

    def __init__(self, organization_id, network_name, source_serial, target_serial):
        self.dashboard = dashboard_connection()
        self.organization_id = organization_id
        self.network_name = network_name
        self.organization = self.Organization(self.dashboard, self.organization_id)
        self.network = self.Network(self.dashboard, self.organization_id, self.network_name)
        self.switch = self.Switch(self.dashboard, self.organization_id, self.network.network_id,
                                  source_serial, target_serial)
        self.ap = self.Ap(self.dashboard, self.organization_id, self.network.network_id,
                          source_serial, target_serial)

    class Organization:
        """ Subclass to handle organization related operations"""

        def __init__(self, dashboard, organization_id):
            self.dashboard = dashboard
            self.organization_id = organization_id

        @meraki_exception
        def claim_order_from_rma(self, order):
            """This is currently useless as the function does not return any serials/licences"""
            self.dashboard.organizations.claimIntoOrganization(organizationId=self.organization_id,
                                                               orders=[order])
            console.print(f"Order {order} added to the organization.", style="good")

        @meraki_exception
        def claim_serial_from_rma(self, serial):
            self.dashboard.organizations.claimIntoOrganization(organizationId=self.organization_id,
                                                               serials=[serial])
            console.print(f"Serial {serial} added to the organization.", style="good")

        @meraki_exception
        def remove_serial_from_organization(self, serial):
            """This is not possible at the moment, feature request done to Meraki."""
            self.dashboard.organizations.unclaimIntoOrganization(organizationId=self.organization_id,
                                                                 serials=[serial])
            console.print(f"Serial {serial} removed from the organization.", style="good")

        @meraki_exception
        def get_inventory_device(self, serial):
            return self.dashboard.organizations.getOrganizationInventoryDevice(organizationId=self.organization_id,
                                                                               serial=serial)

    class Network:
        """ Subclass to handle network related operations"""

        def __init__(self, dashboard, organization_id, network_name):
            self.dashboard = dashboard
            self.organization_id = organization_id
            self.network_name = network_name
            self.network_id = self.network_name_to_network_id()

        @meraki_exception
        def network_name_to_network_id(self):
            all_networks = self.dashboard.organizations.getOrganizationNetworks(organizationId=self.organization_id)
            for network in all_networks:
                if network['name'] == self.network_name:
                    return network['id']
            else:
                console.print('Non existing network, quitting !', style="bad")
                sys.exit(1)

        @meraki_exception
        def add_serial_to_network(self, serial):
            self.dashboard.networks.claimNetworkDevices(networkId=self.network_id,
                                                        serials=[serial])
            console.print(f"Serial {serial} added to the network {self.network_name}.", style="good")

        @meraki_exception
        def remove_serial_from_network(self, serial):
            self.dashboard.networks.removeNetworkDevices(networkId=self.network_id,
                                                         serial=serial)
            console.print(f"Serial {serial} removed from the network {self.network_name}.", style="good")

    class Switch:
        """ Subclass to handle switch related operations"""

        def __init__(self, dashboard, organization_id, network_id, source_serial, target_serial):
            self.dashboard = dashboard
            self.organization_id = organization_id
            self.network_id = network_id
            self.source_serial = source_serial
            self.target_serial = target_serial

        @meraki_exception
        def match_serial_to_stack(self):
            stacks = self.dashboard.switch.getNetworkSwitchStacks(networkId=self.network_id)
            for stack in stacks:
                for st_serial in stack['serials']:
                    if st_serial == self.source_serial:
                        return stack['id']
            return "no-stack"

        @meraki_exception
        def add_serial_to_stack(self, stack_id):
            if stack_id != "no-stack":
                self.dashboard.switch.addNetworkSwitchStack(networkId=self.network_id,
                                                            switchStackId=stack_id,
                                                            serial=self.target_serial)
                console.print(f"Adding switch {self.target_serial} to the stack {stack_id}.", style="good")

        @meraki_exception
        def remove_serial_from_stack(self, stack_id):
            if stack_id != "no-stack":
                self.dashboard.switch.removeNetworkSwitchStack(networkId=self.network_id,
                                                               switchStackId=stack_id,
                                                               serial=self.source_serial)
                console.print(f"Removing switch {self.source_serial} from the stack {stack_id}", style="good")

        @meraki_exception
        def clone_switch(self):
            self.dashboard.switch.cloneOrganizationSwitchDevices(organizationId=self.organization_id,
                                                                 sourceSerial=self.source_serial,
                                                                 targetSerials=[self.target_serial])
            console.print(f"New switch {self.target_serial} cloned with config from broken switch {self.source_serial}",
                          style="good")

        @meraki_exception
        def update_aggregates(self):
            link_aggregations = self.dashboard.switch.getNetworkSwitchLinkAggregations(networkId=self.network_id)
            for aggregate in link_aggregations:
                sp_list = [switchport['serial'] for switchport in aggregate['switchPorts']]
                if all_equal(sp_list):
                    self.dashboard.switch.deleteNetworkSwitchLinkAggregation(networkId=self.network_id,
                                                                             linkAggregationId=aggregate['id'])
                    console.print(f"Removing aggregate {aggregate['id']} as it is useless now.",
                                  style="info")
                else:
                    for switchport in aggregate['switchPorts']:
                        if switchport['serial'] == self.source_serial:
                            switchport['serial'] = self.target_serial
                            self.dashboard.switch.updateNetworkSwitchLinkAggregation(networkId=self.network_id,
                                                                                     linkAggregationId=aggregate['id'],
                                                                                     switchPorts=aggregate[
                                                                                         'switchPorts'])
                            console.print(f"Replacing switch {self.source_serial} with switch {self.target_serial} in "
                                          f"aggregate {aggregate['id']}",
                                          style="good")

        @meraki_exception
        def update_misc(self):
            broken_switch = self.dashboard.devices.getDevice(serial=self.source_serial)
            if broken_switch['name']:
                self.dashboard.devices.updateDevice(serial=self.target_serial,
                                                    name=broken_switch['name'],
                                                    address=broken_switch['address'],
                                                    moveMapMarker=True,
                                                    tags=broken_switch['tags'])
                console.print(f"Adding name, address and tags from switch {self.source_serial} "
                              f"to switch {self.target_serial}",
                              style="good")
                self.dashboard.devices.updateDevice(serial=self.source_serial,
                                                    name=broken_switch['name'] + "_broken")
                console.print(f"Renaming switch {self.source_serial} to {broken_switch['name']}_broken", style="good")
            else:
                self.dashboard.devices.updateDevice(serial=self.target_serial,
                                                    address=broken_switch['address'],
                                                    moveMapMarker=True,
                                                    tags=broken_switch['tags'])
                console.print(f"Adding address and tags from switch {self.source_serial} "
                              f"to switch {self.target_serial}, name was empty so keeping the mac address as name",
                              style="info")
                self.dashboard.devices.updateDevice(serial=self.source_serial,
                                                    name=broken_switch['mac'] + "_broken")
                console.print(f"Renaming switch {self.source_serial} to {broken_switch['mac']}_broken", style="good")

    class Ap:
        """ Subclass to handle access point related operations"""

        def __init__(self, dashboard, organization_id, network_id, source_serial, target_serial):
            self.dashboard = dashboard
            self.organization_id = organization_id
            self.network_id = network_id
            self.source_serial = source_serial
            self.target_serial = target_serial
            self.device = self.dashboard.devices.getDevice(serial=self.source_serial)
            self.device_radio_settings = self.dashboard.wireless.getDeviceWirelessRadioSettings(serial=source_serial)

        @meraki_exception
        def add_rf_profile(self):
            rf_profile_id = self.device_radio_settings['rfProfileId']
            self.dashboard.wireless.updateDeviceWirelessRadioSettings(serial=self.target_serial,
                                                                      rfProfileId=rf_profile_id)

        @meraki_exception
        def update_misc(self):
            broken_ap = self.device
            if broken_ap['name']:
                self.dashboard.devices.updateDevice(serial=self.target_serial,
                                                    name=broken_ap['name'],
                                                    address=broken_ap['address'],
                                                    moveMapMarker=True,
                                                    tags=broken_ap['tags'])
                console.print(f"Adding name, address and tags from ap {self.source_serial} "
                              f"to ap {self.target_serial}",
                              style="good")
                self.dashboard.devices.updateDevice(serial=self.source_serial,
                                                    name=broken_ap['name'] + "_broken")
                console.print(f"Renaming ap {self.source_serial} to {broken_ap['name']}_broken", style="good")
            else:
                self.dashboard.devices.updateDevice(serial=self.target_serial,
                                                    address=broken_ap['address'],
                                                    moveMapMarker=True,
                                                    tags=broken_ap['tags'])
                console.print(f"Adding address and tags from ap {self.source_serial} "
                              f"to ap {self.target_serial}, name was empty so keeping the mac address as name",
                              style="info")
                self.dashboard.devices.updateDevice(serial=self.source_serial,
                                                    name=broken_ap['mac'] + "_broken")
                console.print(f"Renaming ap {self.source_serial} to {broken_ap['mac']}_broken", style="good")
