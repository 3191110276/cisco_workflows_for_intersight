# Template and server organizations

The **Cisco Intersight - Deploy new Server Profile from template** workflow uses
separate organizations for the source template and the target server:

| Input | Purpose | Example |
| --- | --- | --- |
| Template Organization | Organization that owns the source Server Profile Template | `UCSX-LAB-RESOURCES` |
| Server Organization | Organization containing the server; also owns the new Server Profile | `X-Series-Configuration` |
| Template Name | Exact template name in Template Organization | `LAB-RESOURCE` |
| New Profile Name | New, unique profile name in Server Organization | `TEST` |
| Server Name or Serial | Exact server name or serial visible in Server Organization | Your target server's name or serial |

Both organization values may be equal. When they differ, Intersight must permit
use of the template and its referenced policies and pools in the server
organization. The workflow does not change sharing rules, roles, or permissions.
An Intersight rejection is returned through the workflow's status and error
outputs; assignment and deployment do not proceed after a derivation failure.

The template lookup uses Template Organization. Duplicate profile-name checks,
MoCloner ownership and target payload, created-profile verification, server
lookup, assignment, and deployment use Server Organization. A profile with the
same name in the template organization does not satisfy a destination lookup.
The final profile must reference the exact selected source template.

Starting this workflow includes profile creation, assignment, deployment, and
activation. Activation can reboot the target server. Success means acceptance of
the deployment/activation request, not monitored completion. Inspect partial
results before retrying; the workflow provides no automatic rollback or resume.

## Import the update

Import these two JSON exports in order, updating the existing definitions:

1. [Cisco Intersight - Derive profile from template](../Atomics/CiscoIntersightDeriveprofilefromtemplate__definition_workflow_02XOKCY8L727P2I1njlKiu2ypB4dBBGZlFn/definition_workflow_02XOKCY8L727P2I1njlKiu2ypB4dBBGZlFn.json)
2. [Cisco Intersight - Deploy new Server Profile from template](../Workflows/CiscoIntersightDeploynewServerProfilefromtemplate__definition_workflow_02XRJDF2FUHSO3HtFwPPkJV2NMJpxcIoiPS/definition_workflow_02XRJDF2FUHSO3HtFwPPkJV2NMJpxcIoiPS.json)

The workflow identities are preserved. The other three dependent atomics
(Resolve server identity, Assign profile, and Deploy profile) are unchanged.
Validate the imported definitions before starting a run.

The derivation atomic adds optional **Destination Organization**. Direct callers
that leave it empty retain the previous behavior: the new profile is created in
Template Organization. The parent workflow always supplies Server Organization
as the atomic's Destination Organization.

## Local validation

The standalone organization tests use only Python's standard library and the
checked-in exports:

```sh
python3 -m unittest discover -s tests -p test_profile_organizations.py
```

Local tests cover distinct and equal organizations, default destination behavior,
exact organization identity/cardinality, malformed or inaccessible organizations,
source-template ownership, destination payload ownership, and final-profile
identity. Integration fixtures additionally cover the complete create/assign/
deploy sequence, destination-name conflicts, and upstream permission failures.
These tests use local API stubs; no live profile creation or hardware deployment
was performed for this update.
