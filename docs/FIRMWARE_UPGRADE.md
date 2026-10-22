# Firmware upgrade

**Cisco Intersight - Firmware upgrade** starts an upgrade for one Server,
UCS-X Chassis or IMM Domain. It has no Action selector or status-check action.

Supply **Target Type**, **Target Name**, **Device Organization** and
**Firmware Version**. Target Type and Target Name are the first two inputs. Optional inputs are **Server Upgrade Mode** and
**Enable Fabric Evacuation**.
Keep options for other target types at their defaults.
The workflow always sets **Skip Wait for I/O Connectivity** to **false**, so
it waits for I/O connectivity; this setting is not exposed as an input.
Server Upgrade Mode remains a text input with the default **Start Immediately**.

**Enable PSU Upgrade** (`EnablePsuUpgrade`) and **Enable PDB FPGA Upgrade**
(`EnablePdbFpgaUpgrade`) are fixed to **false**, matching their defaults in the
[Cisco firmware.SwitchUpgrade API schema](https://developer.cisco.com/docs/intersight/firmware-switchupgrade/).
Neither option is exposed as a workflow input.

The workflow validates the target and image, skips submission when installed
firmware is verified, or returns an existing active upgrade. Otherwise, it
submits one request. A 202 result means the request was accepted; it does not
mean the upgrade has completed. Monitor progress in Intersight. The outputs
retain **Upgrade ID**, **Upgrade Resource Type** and **Upgrade Status ID**,
alongside **Result**, **Status Code**, **Status Message** and **Error Message**.

The October 22 update removes **Upgrade ID to Check**, **Upgrade Resource Type
to Check**, **Upgrade Status ID to Check**, and the status-only progress outputs.
The upgrade workflow no longer depends on the status atomic.

## Import the update

Import these definitions in this order, updating their existing definitions:

1. [Cisco Intersight - Start firmware upgrade](../Atomics/CiscoIntersightStartfirmwareupgrade__definition_workflow_02XOKCY8L727N6XRbUaRIiFCevRevuGnIMH/definition_workflow_02XOKCY8L727N6XRbUaRIiFCevRevuGnIMH.json).
2. [Cisco Intersight - Firmware upgrade](../Workflows/CiscoIntersightFirmwareupgrade__definition_workflow_02XP097ZMQU745jOdPbsN5Aa8WP1nK8RtrE/definition_workflow_02XP097ZMQU745jOdPbsN5Aa8WP1nK8RtrE.json).

The reusable [Get firmware upgrade status atomic](../Atomics/CiscoIntersightGetfirmwareupgradestatus__definition_workflow_02Z9OCT19FIX0040ae20ce543829d5ec413/definition_workflow_02Z9OCT19FIX0040ae20ce543829d5ec413.json)
remains available for direct callers. Its wording is also updated; re-import it
only if you use it separately. It is not required by the upgrade workflow.

Local graph regression tests use API stubs and do not execute hardware upgrades.
The firmware workflow, Start firmware upgrade atomic and Get firmware upgrade
status atomic are marked validated at the user’s request on October 22, 2026.

For removal of the I/O wait, PSU and PDB FPGA inputs alone, re-import
**Firmware upgrade**. The submission atomic is unchanged.
