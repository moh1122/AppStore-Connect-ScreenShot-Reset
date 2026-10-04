#!/usr/bin/env python3
"""Inspect/reset screenshot sets for one draft App Store version and locale.
Script by Mohamad Masri: https://apps.apple.com/developer/mohammad-masri/id975614455
Requires Python 3.9+ and PyJWT[crypto]. Uses an App Store Connect TEAM API key.
Run without arguments to inspect; run with --delete to choose sets to remove.
The .p8 key stays local; only signed authentication tokens go to Apple's API.
Keep your original screenshot files: the JSON report is NOT an image backup.

Setup on macOS:
  python3 -m venv ~/asc-reset-env
  ~/asc-reset-env/bin/python -m pip install 'PyJWT[crypto]'
  ~/asc-reset-env/bin/python ~/Downloads/asc_screenshot_reset.py
  ~/asc-reset-env/bin/python ~/Downloads/asc_screenshot_reset.py --delete

Official API documentation:
https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api
https://developer.apple.com/documentation/appstoreconnectapi/generating-tokens-for-api-requests
https://developer.apple.com/documentation/appstoreconnectapi/delete-v1-appscreenshotsets-_id_

This is an attempted workaround, not a confirmed fix for Apple's processing bug.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = 'https://api.appstoreconnect.apple.com'


def ask(label, default=None):
    result = input(label + (f' [{default}]' if default else '') + ': ').strip()
    result = result or default
    if not result:
        raise ValueError(f'{label} is required.')
    return result


def resource(value):
    return urllib.parse.quote(str(value), safe='')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AppleAPI:
    def __init__(self, key_path, key_id, issuer):
        try:
            import jwt
        except ImportError:
            raise RuntimeError("Install the dependency: python -m pip install 'PyJWT[crypto]'") from None
        self.jwt = jwt
        self.key = Path(key_path).expanduser().read_text()
        self.key_id, self.issuer = key_id, issuer
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path):
        url = path if path.startswith('https://') else BASE + path
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'api.appstoreconnect.apple.com'
                or not parsed.path.startswith('/v1/')):
            raise RuntimeError('Refusing a request outside the Apple App Store Connect v1 API.')
        now = int(time.time())
        token = self.jwt.encode(
            {'iss': self.issuer, 'iat': now, 'exp': now + 600, 'aud': 'appstoreconnect-v1'},
            self.key, algorithm='ES256', headers={'kid': self.key_id, 'typ': 'JWT'})
        req = urllib.request.Request(url, method=method, headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
        try:
            with self.opener.open(req, timeout=45) as response:
                body = response.read()
                if method == 'DELETE' and response.status != 204:
                    raise RuntimeError(f'Unexpected deletion response: HTTP {response.status}')
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            try:
                errors = json.loads(raw).get('errors', [])
                detail = '; '.join(f"{e.get('code', '')}: {e.get('detail') or e.get('title', '')}" for e in errors)
            except (ValueError, AttributeError):
                detail = 'Apple returned a non-JSON error.'
            raise RuntimeError(f'Apple API HTTP {exc.code}: {detail}\nStopped. Do not assume deletion succeeded; rerun inspection.') from None

    def list(self, path):
        items, seen = [], set()
        while path:
            if path in seen:
                raise RuntimeError('Repeated pagination link; stopped.')
            seen.add(path)
            page = self.request('GET', path)
            items.extend(page['data'])
            path = page.get('links', {}).get('next')
        return items


def inventory(api, locale_id):
    result = []
    for group in api.list(f'/v1/appStoreVersionLocalizations/{resource(locale_id)}/appScreenshotSets'):
        shots = api.list(f"/v1/appScreenshotSets/{resource(group['id'])}/appScreenshots")
        result.append({'id': group['id'], 'display': group['attributes'].get('screenshotDisplayType'),
                       'screenshots': [{'id': s['id'], 'fileName': s['attributes'].get('fileName'),
                                        'delivery': s['attributes'].get('assetDeliveryState')} for s in shots]})
    return result


def require_draft(version):
    a = version['attributes']
    state = a.get('appVersionState') or a.get('appStoreState')
    if state != 'PREPARE_FOR_SUBMISSION':
        raise RuntimeError(f'Only Prepare for Submission is allowed by this script. Current state: {state}')


def choose_sets(groups, selection):
    if selection.lower() == 'all':
        return groups[:]
    try:
        indexes = sorted(set(int(x.strip()) for x in selection.split(',')))
    except ValueError:
        raise ValueError('Enter set numbers separated by commas, or all.') from None
    if not indexes or any(i < 1 or i > len(groups) for i in indexes):
        raise ValueError('Screenshot set selection is out of range.')
    return [groups[i - 1] for i in indexes]


def signature(group):
    return group['display'], tuple(sorted(s['id'] for s in group['screenshots']))


def run(api, app_id, version_number, locale, delete):
    app = api.request('GET', f'/v1/apps/{resource(app_id)}')['data']
    versions = api.list(f'/v1/apps/{resource(app_id)}/appStoreVersions')
    matches = [v for v in versions if v['attributes'].get('platform') == 'IOS'
               and v['attributes'].get('versionString') == version_number]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one iOS version {version_number}; found {len(matches)}.')
    version = matches[0]
    require_draft(version)
    version_path = f"/v1/appStoreVersions/{resource(version['id'])}"
    locales = api.list(version_path + '/appStoreVersionLocalizations')
    matches = [l for l in locales if l['attributes'].get('locale') == locale]
    if len(matches) != 1:
        raise RuntimeError(f'Locale {locale} not uniquely found. Available: ' + ', '.join(l['attributes']['locale'] for l in locales))
    locale_id = matches[0]['id']
    groups = inventory(api, locale_id)
    name = app['attributes']['name']
    print(f'\nApp: {name} | Apple ID: {app_id} | Bundle: {app["attributes"].get("bundleId")}')
    print(f'iOS version: {version_number} | Language: {locale} | Prepare for Submission')
    for n, group in enumerate(groups, 1):
        print(f'\nSet {n}: {group["display"]} | {len(group["screenshots"])} screenshots | ID: {group["id"]}')
        for s in group['screenshots']:
            delivery = s['delivery'] or {}
            print(f'  {s["fileName"]} | {delivery.get("state", "UNKNOWN")} | ID: {s["id"]}')
            if delivery.get('errors'):
                print('  Errors: ' + json.dumps(delivery['errors']))
    if not groups:
        print('No screenshot sets found for this version and locale.')
        return
    if not delete:
        print('\nInspection only: nothing changed. Run again with --delete to choose sets to remove.')
        return

    selected = choose_sets(groups, ask('Set numbers to delete (comma-separated), or all for this language'))
    print('\nSelected for deletion:')
    for g in selected:
        print(f'  {g["display"]}: {len(g["screenshots"])} screenshots')
    print('All screenshots in these sets, including working images, will be removed from this draft.')
    print('Have your original image files ready to reupload. The report contains metadata only.')
    phrase = f'DELETE {app_id} {version_number} {locale}'
    if input(f'Type exactly "{phrase}" to proceed: ').strip() != phrase:
        print('Cancelled. Nothing changed.')
        return

    # Recheck state and membership after user selection; never guess a stale target.
    require_draft(api.request('GET', version_path)['data'])
    fresh = {g['id']: g for g in inventory(api, locale_id)}
    if any(g['id'] not in fresh or signature(g) != signature(fresh[g['id']]) for g in selected):
        raise RuntimeError('Screenshot membership changed. Nothing deleted; rerun inspection.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report = Path.cwd() / f'asc-screenshot-reset-{app_id}-{stamp}.json'
    data = {'appId': app_id, 'appName': name, 'version': version_number, 'locale': locale,
            'inspectedSets': groups, 'selectedSetIds': [g['id'] for g in selected], 'deletedSetIds': []}
    report.write_text(json.dumps(data, indent=2) + '\n')
    print(f'Metadata report: {report}')
    for g in selected:
        require_draft(api.request('GET', version_path)['data'])
        api.request('DELETE', f'/v1/appScreenshotSets/{resource(g["id"])}')
        data['deletedSetIds'].append(g['id'])
        report.write_text(json.dumps(data, indent=2) + '\n')
        print(f'Deleted: {g["display"]} (HTTP 204)')
    remaining = {g['id'] for g in inventory(api, locale_id)}
    if remaining.intersection(data['selectedSetIds']):
        print('Apple accepted deletion, but some sets still appear. Reinspect before reuploading.')
    else:
        print('Selected sets are absent from the API. Refresh App Store Connect and reupload one image first.')
        print('Wait for processing to finish before adding the remaining images.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--delete', action='store_true', help='Choose screenshot sets and confirm their deletion.')
    args = parser.parse_args()
    print('App Store Connect screenshot reset — TEAM API key required. Keep your .p8 file local.')
    key_path = ask('Full path to your .p8 file').strip('\"\'')
    key_id = ask('Key ID')
    issuer = ask('Issuer ID (not Team ID)')
    app_id = ask('Numeric Apple ID of the App (App Information)')
    if not re.fullmatch(r'[0-9]+', app_id):
        raise ValueError('Apple ID must contain digits only.')
    version = ask('iOS version', '1.0')
    locale = ask('Locale', 'en-US')
    run(AppleAPI(key_path, key_id, issuer), app_id, version, locale, args.delete)


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nStopped. If deletion had started, rerun inspection to check its result.')
        sys.exit(1)
    except Exception as exc:
        print(f'\nError: {exc}', file=sys.stderr)
        sys.exit(1)
