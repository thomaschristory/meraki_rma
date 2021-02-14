import sys
from meraki_dashboard_connect import dashboard_connection
from meraki_exception import meraki_exception
from rich.console import Console
from rich.theme import Theme

# Rich configuration
custom_theme = Theme({"good": "green", "bad": "bold red"})
console = Console(theme=custom_theme)


class MerakiRma:
    """Class to manage device replacement on Meraki"""

    def __init__(self, organization_id, network_name, source_serial, target_serial):
        self.dashboard = dashboard_connection()
        self.organization_id = organization_id
        self.network_name = network_name
        self.organization = self.Organization(self.dashboard, self.organization_id)
        self.network = self.Network(self.dashboard, self.organization_id, self.network_name)
        self.switch = self.Switch(self.dashboard, self.organization_id, self.network.network_id, source_serial, target_serial)

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
            self.dashboard.switch.addNetworkSwitchStack(networkId=self.network_id,
                                                        switchStackId=stack_id,
                                                        serial=self.target_serial)
            console.print(f"Adding switch {self.target_serial} to the stack {stack_id}.", style="good")

        @meraki_exception
        def remove_serial_from_stack(self, stack_id):
            self.dashboard.switch.removeNetworkSwitchStack(networkId=self.network_id,
                                                           switchStackId=stack_id,
                                                           serial=self.source_serial)
            console.print(f"Removing switch {self.source_serial} from the stack {stack_id}", style="good")

        @meraki_exception
        def clone_switch(self):
            self.dashboard.switch.cloneOrganizationSwitchDevices(organizationId=self.organization_id,
                                                                 sourceSerial=self.source_serial,
                                                                 targetSerials=[self.target_serial])
            console.print(f"New switch {self.target_serial} cloned with config from broken switch {self.source_serial}")

        @meraki_exception
        def update_aggregates(self):
            link_aggregations = self.dashboard.switch.getNetworkSwitchLinkAggregations(networkId=self.network_id)
            for aggregate in link_aggregations:
                for switchport in aggregate['switchPorts']:
                    if switchport['serial'] == self.source_serial:
                        switchport['serial'] = self.target_serial
                        self.dashboard.switch.updateNetworkSwitchLinkAggregation(networkId=self.network_id,
                                                                                 linkAggregationId=aggregate['id'],
                                                                                 switchPorts=aggregate['switchPorts'])
                        console.print(f"Replacing switch {self.source_serial} with switch {self.target_serial}",
                                      style="good")

        @meraki_exception
        def update_misc(self):
            broken_switch = self.dashboard.devices.getDevice(serial=self.source_serial)
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
