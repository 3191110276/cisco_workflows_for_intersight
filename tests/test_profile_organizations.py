"""Organization boundaries in the exported profile scripts; no API/hardware calls.

Run with: python3 -m unittest discover -s tests -p test_profile_organizations.py
Uses only the standard library and the two checked-in workflow exports.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DERIVE = json.loads(next((ROOT/'Atomics').glob('CiscoIntersightDeriveprofilefromtemplate__*/*.json')).read_text())['workflow']
PARENT = json.loads(next((ROOT/'Workflows').glob('*DeploynewServerProfilefromtemplate*/*.json')).read_text())['workflow']
SOURCE = 'UCSX-LAB-RESOURCES'
DESTINATION = 'X-Series-Configuration'


def activities(node):
    if isinstance(node, dict):
        if node.get('object_type') == 'definition_activity':
            yield node
        for key, value in node.items():
            if key != 'properties':
                yield from activities(value)
    elif isinstance(node, list):
        for value in node:
            yield from activities(value)


def action(title):
    return next(a for a in activities(DERIVE) if a['title'] == title and a['type'] == 'python3.script')


def execute(title, arguments):
    argv = ['fixture'] + [json.dumps(v) if isinstance(v, (dict, list, bool)) else str(v) for v in arguments]
    result = {}
    with patch.object(sys, 'argv', argv):
        exec(compile(action(title)['properties']['script'], title, 'exec'), result)
    return result


def organization(name, moid):
    return {'Name': name, 'Moid': moid, 'ObjectType': 'organization.Organization', 'ClassId': 'organization.Organization'}


def resolve(rows, source=SOURCE, destination=DESTINATION, count=None, status=200, succeeded=True):
    return execute('Validate typed organization envelope and identity', [
        {'Count': len(rows) if count is None else count, 'Results': rows},
        source, 'URL-safe', status, succeeded, destination])


def prepare(destination, source=SOURCE):
    return execute('Validate inputs, escape OData values, and prepare profile routes', [
        'Server', source, 'LAB-RESOURCE', 'TEST', '', '', True, 600,
        'Server', source, 'LAB-RESOURCE', 'TEST', source, 'LAB-RESOURCE', 'TEST', 'true', '600', destination])


def template():
    return {'Moid': 'template-1', 'Name': 'LAB-RESOURCE', 'ObjectType': 'server.ProfileTemplate',
            'ClassId': 'server.ProfileTemplate', 'Organization': {'Moid': 'source-org', 'ObjectType': 'organization.Organization'},
            'TargetPlatform': 'FIAttached'}


def clone(item):
    return execute('Inspect source template and build MoCloner request', [
        {'Results': [item]}, 'Server', 'source-org', 'TEST', '', '',
        'server.ProfileTemplate', 'server.Profile', '', '', '{}', '500', '', 'destination-org'])


class ProfileOrganizationTests(unittest.TestCase):
    def test_optional_destination_preserves_same_organization_calls(self):
        for destination in ('', SOURCE):
            with self.subTest(destination=destination):
                prepared = prepare(destination)
                self.assertEqual(prepared['preparationStatus'], 'ready')
                self.assertEqual(prepared['destinationOrganizationName'], SOURCE)
                self.assertEqual(prepared['organizationLookupFilter'], "Name eq 'UCSX-LAB-RESOURCES'")
                resolved = resolve([organization(SOURCE, 'source-org')], destination=SOURCE)
                self.assertEqual(resolved['statusCode'], 200)
                self.assertEqual(resolved['destinationOrganizationMoid'], resolved['organizationMoid'])

    def test_cross_organization_lookup_is_bounded_and_order_independent(self):
        prepared = prepare(DESTINATION)
        self.assertEqual(prepared['preparationStatus'], 'ready')
        self.assertEqual(prepared['organizationLookupFilter'], "(Name eq 'UCSX-LAB-RESOURCES' or Name eq 'X-Series-Configuration')")
        rows = [organization(DESTINATION, 'destination-org'), organization(SOURCE, 'source-org')]
        for items in (rows, list(reversed(rows))):
            resolved = resolve(items)
            self.assertEqual(resolved['statusCode'], 200)
            self.assertTrue(resolved['inspectionComplete'])
            self.assertEqual(resolved['organizationMoid'], 'source-org')
            self.assertEqual(resolved['destinationOrganizationMoid'], 'destination-org')
            self.assertEqual(json.loads(resolved['organizationJson'])['Name'], SOURCE)

    def test_unsafe_destination_is_rejected_before_lookup(self):
        for name in ("bad' or true", 'name with spaces', 'x'*65, 'org/other'):
            with self.subTest(name=name):
                prepared = prepare(name)
                self.assertEqual(prepared['preparationStatus'], 'invalid')
                self.assertIn('Destination Organization', prepared['preparationMessage'])

    def test_missing_and_duplicate_names_never_publish_destination_identity(self):
        for rows, expected in (([], 404), ([organization(SOURCE, 'source-org')], 404),
                               ([organization(DESTINATION, 'destination-org')], 404),
                               ([organization(SOURCE, 'a'), organization(SOURCE, 'b'), organization(DESTINATION, 'c')], 409)):
            resolved = resolve(rows)
            self.assertEqual(resolved['statusCode'], expected)
            self.assertEqual(resolved['destinationOrganizationMoid'], '')
            self.assertTrue(resolved['inspectionComplete'])
        self.assertIn('Destination', resolve([organization(SOURCE, 'source-org')])['message'])
        self.assertIn('Template', resolve([organization(DESTINATION, 'destination-org')])['message'])

    def test_malformed_incomplete_and_contradictory_identity_is_rejected(self):
        valid = [organization(SOURCE, 'source-org'), organization(DESTINATION, 'destination-org')]
        cases = [(valid, True), (valid, 3), ([organization(SOURCE, 'same'), organization(DESTINATION, 'same')], 2),
                 ([organization('unrequested', 'source-org'), valid[1]], 2)]
        for key, value in (('Moid', {}), ('Moid', ''), ('ClassId', 'wrong.Type'), ('ObjectType', 'wrong.Type')):
            rows = copy.deepcopy(valid)
            rows[1][key] = value
            cases.append((rows, 2))
        for rows, count in cases:
            with self.subTest(rows=rows, count=count):
                resolved = resolve(rows, count=count)
                self.assertEqual(resolved['statusCode'], 502)
                self.assertEqual(resolved['destinationOrganizationMoid'], '')

    def test_organization_http_failure_retains_status_and_no_destination(self):
        resolved = resolve([], status=403, succeeded=False)
        self.assertEqual(resolved['statusCode'], 403)
        self.assertEqual(resolved['lookupStatus'], 'api-failure')
        self.assertEqual(resolved['destinationOrganizationMoid'], '')

    def test_source_template_stays_in_source_and_clone_targets_destination(self):
        result = clone(template())
        self.assertEqual(result['templateStatus'], 'exact')
        body = json.loads(result['cloneRequestJson'])
        self.assertEqual(body['Sources'][0]['Moid'], 'template-1')
        self.assertEqual(body['Organization']['Moid'], 'destination-org')
        self.assertEqual(body['Targets'][0]['Organization']['Moid'], 'destination-org')
        self.assertEqual(body['Targets'][0]['Name'], 'TEST')
        self.assertEqual(body['Targets'][0]['TargetPlatform'], 'FIAttached')
        wrong = template()
        wrong['Organization']['Moid'] = 'destination-org'
        rejected = clone(wrong)
        self.assertEqual(rejected['templateStatus'], 'invalid')
        self.assertEqual(rejected['cloneRequestJson'], '')

    def test_final_identity_requires_destination_and_exact_source_template(self):
        profile = {'Name': 'TEST', 'Moid': 'profile-1', 'ObjectType': 'server.Profile', 'ClassId': 'server.Profile',
                   'Organization': {'Moid': 'destination-org', 'ObjectType': 'organization.Organization'},
                   'SrcTemplate': {'Moid': 'template-1', 'ObjectType': 'server.ProfileTemplate'}, 'TargetPlatform': 'FIAttached'}
        for moid, status in (('destination-org', 'exact'), ('source-org', 'mismatch')):
            current = copy.deepcopy(profile)
            current['Organization']['Moid'] = moid
            result = execute('Verify exact created profile identity', [
                {'Results': [current]}, 'Server', 'destination-org', 'server.Profile', 'FIAttached', '',
                'template-1', 'server.ProfileTemplate', 'TEST', {}, {}, 'true', '', 'true', '', '{}', '500', ''])
            self.assertEqual(result['finalStatus'], status)

    def test_parent_routes_template_and_server_organizations_independently(self):
        variables = {v['properties']['name']: v for v in PARENT['variables']}
        source_ref = f"$workflow.{PARENT['unique_name']}.input.{variables['Template Organization']['unique_name']}$"
        dest_ref = f"$workflow.{PARENT['unique_name']}.input.{variables['Server Organization']['unique_name']}$"
        calls = [a for a in activities(PARENT) if a['type'] == 'workflow.atomic_workflow']
        derive = next(a for a in calls if a['properties']['workflow_id'] == DERIVE['unique_name'])
        child_inputs = {v['properties']['name']: derive['properties']['input'][v['unique_name']]
                        for v in DERIVE['variables'] if v['properties']['scope'] == 'input' and v['unique_name'] in derive['properties']['input']}
        self.assertEqual(child_inputs['Template Organization'], source_ref)
        self.assertEqual(child_inputs['Destination Organization'], dest_ref)
        for other in calls:
            if other is not derive:
                self.assertIn(dest_ref, other['properties']['input'].values())
                self.assertNotIn(source_ref, other['properties']['input'].values())


if __name__ == '__main__':
    unittest.main()
