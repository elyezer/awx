# Generated by Django 2.2.11 on 2020-08-04 15:19

import logging

from awx.main.utils.encryption import encrypt_field, decrypt_field

from django.conf import settings
from django.utils.timezone import now

from awx.main.models import CredentialType as ModernCredentialType
from awx.main.utils.common import set_current_apps

logger = logging.getLogger('awx.main.migrations')


def migrate_galaxy_settings(apps, schema_editor):
    set_current_apps(apps)
    ModernCredentialType.setup_tower_managed_defaults()
    Organization = apps.get_model('main', 'Organization')
    CredentialType = apps.get_model('main', 'CredentialType')
    Credential = apps.get_model('main', 'Credential')
    Setting = apps.get_model('conf', 'Setting')

    galaxy_type = CredentialType.objects.get(kind='galaxy')
    private_galaxy_url = Setting.objects.filter(key='PRIMARY_GALAXY_URL').first()

    # by default, prior versions of AWX/Tower automatically pulled content
    # from galaxy.ansible.com
    public_galaxy_enabled = True
    public_galaxy_setting = Setting.objects.filter(key='PUBLIC_GALAXY_ENABLED').first()
    if public_galaxy_setting and public_galaxy_setting.value is False:
        # ...UNLESS this behavior was explicitly disabled via this setting
        public_galaxy_enabled = False

    for org in Organization.objects.all():
        if private_galaxy_url and private_galaxy_url.value:
            # If a setting exists for a private Galaxy URL, make a credential for it
            username = Setting.objects.filter(key='PRIMARY_GALAXY_USERNAME').first()
            password = Setting.objects.filter(key='PRIMARY_GALAXY_PASSWORD').first()
            if (username and username.value) or (password and password.value):
                logger.error(
                    f'Specifying HTTP basic auth for the Ansible Galaxy API '
                    f'({private_galaxy_url.value}) is no longer supported. '
                    'Please provide an API token instead after your upgrade '
                    'has completed',
                )
            inputs = {
                'url': private_galaxy_url.value
            }
            token = Setting.objects.filter(key='PRIMARY_GALAXY_TOKEN').first()
            if token and token.value:
                inputs['token'] = decrypt_field(token, 'value')
            auth_url = Setting.objects.filter(key='PRIMARY_GALAXY_AUTH_URL').first()
            if auth_url and auth_url.value:
                inputs['auth_url'] = auth_url.value
            name = f'Private Galaxy ({private_galaxy_url.value})'
            if 'cloud.redhat.com' in inputs['url']:
                name = f'Ansible Automation Hub ({private_galaxy_url.value})'
            cred = Credential(
                created=now(),
                modified=now(),
                name=name,
                organization=org,
                credential_type=galaxy_type,
                inputs=inputs
            )
            cred.save()
            if token and token.value:
                # encrypt based on the primary key from the prior save
                cred.inputs['token'] = encrypt_field(cred, 'token')
                cred.save()
            org.galaxy_credentials.add(cred)

        fallback_servers = getattr(settings, 'FALLBACK_GALAXY_SERVERS', [])
        for fallback in fallback_servers:
            url = fallback.get('url', None)
            auth_url = fallback.get('auth_url', None)
            username = fallback.get('username', None)
            password = fallback.get('password', None)
            token = fallback.get('token', None)
            if username or password:
                logger.error(
                    f'Specifying HTTP basic auth for the Ansible Galaxy API '
                    f'({url}) is no longer supported. '
                    'Please provide an API token instead after your upgrade '
                    'has completed',
                )
            inputs = {'url': url}
            if token:
                inputs['token'] = token
            if auth_url:
                inputs['auth_url'] = auth_url
            cred = Credential(
                created=now(),
                modified=now(),
                name=f'Ansible Galaxy ({url})',
                organization=org,
                credential_type=galaxy_type,
                inputs=inputs
            )
            cred.save()
            if token:
                # encrypt based on the primary key from the prior save
                cred.inputs['token'] = encrypt_field(cred, 'token')
                cred.save()
            org.galaxy_credentials.add(cred)

        if public_galaxy_enabled:
            # If public Galaxy was enabled, make a credential for it
            cred = Credential(
                created=now(),
                modified=now(),
                name='Ansible Galaxy',
                organization=org,
                credential_type=galaxy_type,
                inputs = {
                    'url': 'https://galaxy.ansible.com/'
                }
            )
            cred.save()
            org.galaxy_credentials.add(cred)
