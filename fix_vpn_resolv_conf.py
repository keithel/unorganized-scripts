#!/usr/bin/env python3
"""
Tool to add internal DNS servers to resolv.conf, since NetworkManager doesn't
get it right.
"""
from typing import Optional
from socket import socket, AF_INET, SOCK_DGRAM, inet_ntoa
from fcntl import ioctl
import struct
import sys
import os
import functools
import re


DEBUG: bool = True
RESOLV_CONF_PATH: str = "/etc/resolv.conf"
VPN_DNS_SERVERS: list[bytes] = [
    b"8.8.8.8",
    b"8.8.4.4"
]
VPN_DNS_SEARCH_LINE: str = f"search exa.example.com example.com"

def write_resolv_conf(resolv_conf_lines: list[str]):
    """
    Write a new resolv.conf, with the contents provided as a list of lines.
    """
    try:
        #resolv_conf_write_path = "/tmp/resolv.conf"
        resolv_conf_write_path = RESOLV_CONF_PATH
        with open(resolv_conf_write_path, "w", encoding='utf-8') as w_file:
            w_file.writelines(new_resolv_conf)
    except PermissionError:
        print(f"No permission to write to {resolv_conf_write_path}",
            file=sys.stderr)
        raise

def vpn_resolv_conf(dns_servers: Optional[list[bytes]]) -> Optional[list[str]]:
    """
    Create a new resolv.conf that adds in the DNS servers provided to search.
    Returns the lines of the new resolv.conf if the resolv.conf would be
    changed, otherwise None if resolv.conf already includes vpn nameservers.
    """
    _dns_servers = [str(dns_server, 'UTF-8') for dns_server in dns_servers]
    already_updated: bool = False
    existing_nameservers: list[str] = []
    with open(RESOLV_CONF_PATH, "r", encoding='utf-8') as r_file:
        resolv_conf: list[str] = r_file.readlines()
        r_file.close()

    for line in resolv_conf:
        search_match = re.match("\\s*search\\s\\s*", line)
        ns_match = re.match("\\s*nameserver\\s\\s*", line)
        if search_match:
            search_args = re.split("\\s", line[search_match.end():])
        if ns_match:
            nameserver = line[ns_match.end():].strip()
            if functools.reduce(lambda a, b: a or b,
                [nameserver.startswith(dns_server)
                for dns_server in _dns_servers]):
                already_updated = True
            if not nameserver.startswith("10."):
                existing_nameservers.append(nameserver)

    if already_updated:
        return None

    new_resolv_conf: list[str] = [ VPN_DNS_SEARCH_LINE + f" {' '.join(search_args)}\n" ]
    for nameserver in existing_nameservers + _dns_servers:
        new_resolv_conf.append(f"nameserver {nameserver}\n")
    return new_resolv_conf

def ping(hostname: str):
    """
    Ping a hostname, returning bool indicating success or failure.
    """
    return os.system(f"ping -c 1 -w 1 {hostname} >/dev/null") == 0


class VpnConnection:
    """
    Class that encapsulates information on a connection to the VPN.
    """
    def __init__(self) -> None:
        self._iface_name: bytes = b"tun0"

        try:
            self._tun_ip: Optional[str] = self._get_ip_addr()
        except OSError:
            self._tun_ip = None

    def _get_ip_addr(self) -> str:
        sock = socket(AF_INET, SOCK_DGRAM)
        return inet_ntoa(ioctl(
            sock.fileno(),
            0x8915, # SIOCGIFADDR
            struct.pack(b'256s', self._iface_name[:15])
        )[20:24])

    def dns_servers(self) -> list[bytes]:
        """
        Return the list of VPN DNS servers to use.
        """
        return VPN_DNS_SERVERS

    def ip_address(self) -> Optional[str]:
        """
        Return the IP address associated with the VPN network adapter.
        """
        return self._tun_ip

    def connected(self) -> bool:
        """
        Return boolean indicating whether or not connected to the VPN.
        """
        dns_reachable: list[bool] = [ping(str(dns, 'UTF-8')) for dns in VPN_DNS_SERVERS]
        all_dns_reachable: bool = functools.reduce(lambda a, b: a and b, dns_reachable)
        return all_dns_reachable

if __name__ == "__main__":
    conn = VpnConnection()
    if conn.connected():
        print("Connected to VPN")
        new_resolv_conf = vpn_resolv_conf(conn.dns_servers())
        if new_resolv_conf:
            if DEBUG:
                sys.stdout.writelines(new_resolv_conf)
            else:
                write_resolv_conf(new_resolv_conf)
                print("Updated /etc/resolv.conf.")
        else:
            print("/etc/resolv.conf was already updated, left unchanged.",
                file=sys.stderr)
    else:
        print("Not connected to VPN, doing nothing.", file=sys.stderr)
        sys.exit(0)
