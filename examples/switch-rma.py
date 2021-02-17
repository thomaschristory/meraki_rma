# this needs to be copied in a new project.
import typer
from meraki_env import meraki_organization_id
from meraki_rma import MerakiRma

app = typer.Typer()


@app.command()
def classic_replacement(source_serial, target_serial, network_name):

    simple_rma = MerakiRma(organization_id=meraki_organization_id(),
                           network_name=network_name,
                           source_serial=source_serial,
                           target_serial=target_serial)
    simple_rma.organization.claim_serial_from_rma(serial=target_serial)
    simple_rma.network.add_serial_to_network(serial=target_serial)
    stack_id = simple_rma.switch.match_serial_to_stack()
    simple_rma.switch.add_serial_to_stack(stack_id=stack_id)
    simple_rma.switch.clone_switch()
    simple_rma.switch.update_aggregates()
    simple_rma.switch.update_misc()
    simple_rma.switch.remove_serial_from_stack(stack_id=stack_id)
    simple_rma.network.remove_serial_from_network(serial=source_serial)