"""Write first-time Oracle VM settings without overwriting an existing deployment."""
import argparse
import ipaddress
from pathlib import Path
import re


def settings(domain, admin_ip, remote_clients=False, lab_networks=()):
    domain = domain.lower()
    labels = domain.split('.')
    if (len(domain) > 253 or len(labels) < 2 or
            any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels) or
            labels[-1].isdigit() or domain.endswith(('.example', '.invalid', '.localhost', '.test')) or
            domain == 'example.org' or domain.endswith('.example.org')):
        raise ValueError('Use your real DNS hostname, without https:// or a path')
    address = ipaddress.ip_address(admin_ip)
    if address.version != 4 or not address.is_global:
        raise ValueError('Admin IP must be the public IPv4 address of your admin network')
    networks = [ipaddress.ip_network(value, strict=True) for value in lab_networks]
    if remote_clients and networks:
        raise ValueError('Choose remote clients or lab networks, not both')
    if not remote_clients and not networks:
        raise ValueError('Set --lab-network or explicitly allow --remote-clients')
    if any(not network.is_global or network.prefixlen == 0 for network in networks):
        raise ValueError('Lab networks must be specific public IP ranges')
    return (f'LOGBOOK_DOMAIN={domain}\nLOGBOOK_ADMIN_ADDRESS={address}\n'
            f'LOGBOOK_ALLOW_REMOTE_CLIENTS={int(remote_clients)}\n'
            f'LOGBOOK_LAB_NETWORKS={",".join(map(str, networks))}\n')


def configure(destination, domain, admin_ip, remote_clients=False, lab_networks=()):
    content = settings(domain, admin_ip, remote_clients, lab_networks)
    with Path(destination).open('x', encoding='utf-8', newline='\n') as output:
        output.write(content)


def main():
    parser = argparse.ArgumentParser(description='Set up the logbook on your Oracle Ubuntu VM')
    parser.add_argument('--domain', required=True)
    parser.add_argument('--admin-ip', required=True)
    parser.add_argument('--remote-clients', action='store_true')
    parser.add_argument('--lab-network', action='append', default=[])
    args = parser.parse_args()
    try:
        configure(Path(__file__).resolve().parent / '.env', args.domain, args.admin_ip,
                  args.remote_clients, args.lab_network)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Setup stopped: {error}\n')
    print('Server settings saved. No cloud resources were created.')


if __name__ == '__main__':
    main()
