#! /usr/bin/env python3

import argparse
import configparser
import os
import re
import sys
from pathlib import Path

APP_ID = "Bluebooth"
APP_DESC = "Bluebooth is a tool to update Linux bluetooth pairing keys from a pre-exported Windows .reg file"
SEARCH_PATTERN = 'BTHPORT\\Parameters\\Keys\\'


def valid_mac(arg_value):
    if not re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", arg_value.lower()):
        raise argparse.ArgumentTypeError
    return arg_value


def format_mac(mac):
    return ':'.join(s for s in re.split(r'(\w{2})', mac.upper()) if s.isalnum())


parser = argparse.ArgumentParser(description=APP_DESC, epilog="Enjoy!")
parser.add_argument('-r', '--reg-file', type=argparse.FileType('r', encoding='utf-16'), dest='reg_file',
                    required=True, metavar='/path/to/keys.reg', nargs='?', help='Path to pre-exported .reg file')
parser.add_argument('-m', '--mac', metavar='XX:XX:XX:XX:XX', required=True, dest='mac', type=valid_mac,
                    nargs='?', help='Mac address of target host bluetooth device')
parser.add_argument('-c', '--config-file', metavar='/path/to/info', dest='config_file', type=argparse.FileType('r'),
                    nargs='?', help='Path to previously extracted bluetooth config file and avoid sudo usage')
parser.add_argument('-s', '--show-path', dest='show_path', action='store_true',
                    help='Shows the path where bluetooth info file is located and exit')
args = parser.parse_args()

target_mac = format_mac(args.mac)
trimmed_mac = target_mac.replace(':', '').lower()
host_mac = ''
key = ''

print('Parsing {} file...'.format(args.reg_file.name))
for count, line in enumerate(args.reg_file):
    if count > 3 and host_mac is '' and SEARCH_PATTERN in line:
        host_mac_text = line.split(SEARCH_PATTERN)[1][:12].upper()
        host_mac = format_mac(host_mac_text)
        print('Found host bluetooth mac address [{}]'.format(host_mac))

    if count > 4 and host_mac is not '' and trimmed_mac in line:
        key = line.split('=hex:')[1].replace(',', '').replace('\n', '').upper()
        print('Pairing key found [{}]'.format(key))

original_config_file_path = '/var/lib/bluetooth/{}/{}/info'.format(host_mac, target_mac)

if args.show_path:
    print('\nPath of target bluetooth info file is:\n{}'.format(original_config_file_path))
    sys.exit()

if not args.config_file and not os.geteuid() == 0:
    sys.exit("\n{} can only be run by root or with root (sudo) privileges.\nPermission denied\n".format(APP_ID))

if key is '':
    message = "\nPairing key not found in .reg file for given device's mac address [{}] [{}].\n"
    sys.exit(message.format(args.file.name, target_mac))

target_path = Path(args.config_file.name if args.config_file else original_config_file_path)
backup_path = Path(target_path.with_suffix('.bak'))
if not target_path.is_file():
    sys.exit("\nTarget bluetooth config file not found [{}].\n".format(target_path))

print('Creating backup file...')
target_path.rename(backup_path)

target_config = configparser.ConfigParser(allow_no_value=True)
target_config.read_file(backup_path.open('r'))
with target_path.open('w') as target_config_file:
    target_config['LinkKey']['Key'] = key
    print('Writing new config file...')
    target_config.write(target_config_file, space_around_delimiters=False)

print('Deleting backup file...')
backup_path.unlink()

finished_message = """
Successfully replaced pairing key.

If you extracted the bluetooth config file from
{}
You must replace the original file.

Bluetooth service needs to be restarted in order to use the new pairing key.
Your may run 'sudo systemctl restart bluetooth.service' or reboot host machine."""

print(finished_message.format(original_config_file_path))
