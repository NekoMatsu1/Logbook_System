"""Run in the owner's PythonAnywhere Bash console; secrets are entered there, not in chat."""
import argparse
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--username',required=True)
    parser.add_argument('--admin-email',required=True)
    parser.add_argument('--lab-network',action='append',required=True)
    parser.add_argument('--force-https-confirmed',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.username):
        parser.error('Invalid hosting username')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',args.admin_email):
        parser.error('Invalid administrator email')
    networks=[str(ipaddress.ip_network(value)) for value in args.lab_network]
    home=Path.home()
    if home != Path('/home')/args.username:
        parser.error('Run this command in the actual PythonAnywhere account console')
    if not args.force_https_confirmed:
        parser.error('Enable Force HTTPS in the Web tab, then pass --force-https-confirmed')
    folder=home/'.config'/'lab-logbook'
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    folder.chmod(0o700)
    destination=folder/'server.json'
    if destination.exists():
        parser.error('Private configuration already exists; edit it deliberately instead of replacing identity/secrets')
    client_id=input('Google Web OAuth client ID: ').strip()
    client_secret=getpass.getpass('Google Web OAuth client secret (hidden): ').strip()
    if not client_id.endswith('.apps.googleusercontent.com') or not client_secret:
        parser.error('Google Web OAuth client credentials are required')
    hostname=args.username+'.pythonanywhere.com'
    database=home/'.local'/'share'/'lab-logbook'/'logbook.sqlite'
    database.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    configuration=dict(DATABASE=str(database),SECRET_KEY=secrets.token_hex(48),PRODUCTION=True,
                       ADMIN_AUTH_MODE='google',ADMIN_DIRECT_ONLY=False,ADMIN_ADDRESSES=[],
                       ADMIN_EMAIL=args.admin_email.lower(),GOOGLE_CLIENT_ID=client_id,GOOGLE_CLIENT_SECRET=client_secret,
                       GOOGLE_REDIRECT_URI=f'https://{hostname}/auth/callback',TRUSTED_HOSTS=[hostname],
                       SESSION_COOKIE_SECURE=True,LAB_NETWORKS=networks,PLATFORM_HTTPS_ENFORCED=True)
    descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as output:
        json.dump(configuration,output,indent=2)
    print(f'Private configuration created at {destination}. No secret values printed.')

if __name__=='__main__':
    main()
